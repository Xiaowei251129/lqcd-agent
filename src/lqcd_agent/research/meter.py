"""Bind every SDK model/tool effect to the existing Host resource authority."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from lqcd_agent.control.budget import BudgetExhausted, resource_scope, settle_resource_failure
from lqcd_agent.control.strict_json import digest, require
from lqcd_agent.control.research_budget import ResearchBudget
from lqcd_agent.settings import INPUT_TOKEN_LIMIT, CODE_OUTPUT_TOKEN_LIMIT


class ResearchMeter:
    def __init__(self, port, *, node, context, output_dir, request_timeout_seconds, model, max_output_tokens):
        require(request_timeout_seconds > 0, 'A research request needs a positive timeout')
        self.port, self.node, self.context = port, node, context
        self.request_timeout_seconds = request_timeout_seconds
        self.path = Path(output_dir)/'research_events.jsonl'
        self.model, self.max_output_tokens = model, max_output_tokens
        self.events, self.active = [], None
        self.ordinal, self.model_calls = 0, 0
        self.counted_input = INPUT_TOKEN_LIMIT
        self.ticket = None
        self.research_budget = ResearchBudget.for_run(port.leases.coordinator,
            {key: context['identity'][key] for key in ('case_id', 'run_id')})

    def _fence(self, db):
        self.port.leases._effect_authority(db, self.port.capability_id, self.port.worker, self.port.epoch)

    @contextmanager
    def write_scope(self):
        """Fence immediate library publication in the existing writer transaction."""
        with self.port.leases.coordinator.transaction() as db:
            self._fence(db)
            if self.research_budget is not None and self.port.leases.coordinator._time().monotonic_seconds >= self.research_budget.binding['deadline']:
                raise BudgetExhausted('Research task deadline exhausted before publication')
            yield

    def remaining_seconds(self):
        # The lease, not the SDK, owns the ultimate dispatch window.
        _, invocation = self.port.leases.get(self.port.capability_id)
        now = self.port.leases.coordinator._time().monotonic_seconds
        # Keep the graph's existing 30-second settlement allowance inside the
        # original Host window; an HTTP timeout is not an attempt deadline.
        deadline = min(invocation['deadline'], invocation['expires_at'])
        if self.research_budget is not None:
            deadline = min(deadline, self.research_budget.binding['deadline'])
        remaining = deadline - now - 30
        if remaining <= 0:
            raise BudgetExhausted('Research attempt deadline exhausted')
        return remaining

    def _record(self, event):
        self.events.append(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, sort_keys=True, allow_nan=False)+'\n')

    def __call__(self, event):
        kind = event['event']
        if kind in ('model_start', 'tool_start'):
            require(self.active is None, 'Research effects must execute sequentially')
            self.ordinal += 1
            model_call = kind == 'model_start'
            if model_call:
                self.model_calls += 1
            first = model_call and self.model_calls == 1
            identifier = ('domain-diagnosis' if first else
                          f"research-{self.ordinal:03d}-{event['role']}-{kind.removesuffix('_start')}")
            config = ({'node': self.node, 'structured_output': True} if first else
                      {'node': self.node, 'role': event['role'], 'model': self.model,
                       'max_output_tokens': self.max_output_tokens, 'tool_name': event.get('tool_name')})
            recorded = {**event, 'resource_id': identifier, 'model': self.model,
                        'config_digest': digest(config)}
            self._record(recorded)
            scope = resource_scope(self.port, resource_kind='llm_call' if model_call else 'tool_call',
                resource_id=identifier, input_digest=digest(self.context if first else event),
                config_digest=digest(config),
                timeout_seconds=min(self.request_timeout_seconds, self.remaining_seconds()))
            settle = scope.__enter__()
            self.active = (identifier, scope, settle)
            if model_call and self.research_budget is not None:
                try:
                    self.ticket = self.research_budget.reserve(
                        digest([self.port.capability_id, identifier]), self.counted_input,
                        CODE_OUTPUT_TOKEN_LIMIT if event.get('operation') == 'compact' else self.max_output_tokens,
                        fence=self._fence)
                except BaseException as error:
                    self.fail_active(error)
                    raise
        elif kind in ('model_end', 'tool_end'):
            require(self.active is not None, 'An ended research effect has no Host reservation')
            identifier, scope, settle = self.active
            self._record({**event, 'resource_id': identifier})
            raw = event.get('raw_usage')
            tokens = raw.get('total_tokens') if type(raw) is dict else None
            # SDK-normalized zeroes do not establish that the provider measured zero.
            if type(tokens) is not int or tokens < 0:
                tokens = None
            try:
                settle(event, tokens=tokens)
            except BaseException as error:
                scope.__exit__(type(error), error, error.__traceback__)
                self.active = None
                settle_resource_failure(self.port, resource_id=identifier, error=error)
                raise
            scope.__exit__(None, None, None)
            self.active = None
            if self.ticket is not None:
                self.research_budget.settle(self.ticket, tokens, fence=self._fence)
                self.ticket = None
            if event.get('tool_name') == 'context_token_count':
                self.counted_input = event['result']['input_tokens']
        elif kind in ('model_error', 'tool_error'):
            self._record(event)
            self.fail_active(RuntimeError(event['error_type']))
        else:
            self._record(event)

    def fail_active(self, error):
        """Call only after the SDK runner and its active effect have finished cleanup."""
        if self.active is not None:
            identifier, scope, _ = self.active
            self.active = None
            self.ticket = None
            scope.__exit__(type(error), error, error.__traceback__)
            settle_resource_failure(self.port, resource_id=identifier, error=error)
