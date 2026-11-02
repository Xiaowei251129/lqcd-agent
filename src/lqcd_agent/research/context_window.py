"""Count complete wire requests and compact working history under Host authority."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json

from agents.agent_output import AgentOutputSchema, AgentOutputSchemaBase
from agents.run_config import ModelInputData
from agents.usage import Usage
from openai import Omit

from lqcd_agent.llm.prompts import ContextLimitError
from .context_policy import INPUT_TOKEN_LIMIT, COMPACT_TOKEN_LIMIT


class ContextWindow:
    def __init__(self, client, model, hooks, pinned, *, request_timeout_seconds):
        self.client, self.model, self.hooks = client, model, hooks
        self.request_timeout_seconds = request_timeout_seconds
        self.pinned = deepcopy(pinned)
        self.original_prefix = self.replacement = None
        self.ordinal = 0

    def request(self, data):
        agent = data.agent
        schema = agent.output_type if isinstance(agent.output_type, AgentOutputSchemaBase) else AgentOutputSchema(agent.output_type)
        # Use the pinned SDK's own serializer, not an approximate character/token ratio.
        wire = self.model._build_response_create_kwargs(data.model_data.instructions,
            data.model_data.input, agent.model_settings, agent.tools, schema, [])
        supported = ('model', 'instructions', 'input', 'tools', 'text', 'tool_choice',
                     'parallel_tool_calls', 'reasoning', 'truncation')
        return {key: value for key, value in wire.items() if key in supported and not isinstance(value, Omit)}

    async def count(self, request):
        self.hooks.check_cancelled()
        self.ordinal += 1
        fields = {'tool_name': 'context_token_count', 'call_id': f'context-count-{self.ordinal}'}
        await self.hooks.emit('tool_start', **fields, arguments=json.dumps(request))
        self.hooks.active = ('tool', fields)
        async with asyncio.timeout(self.request_timeout_seconds):
            counted = await self.client.responses.input_tokens.count(**request)
        self.hooks.active = None
        await self.hooks.emit('tool_end', **fields, result={'input_tokens': counted.input_tokens})
        if type(counted.input_tokens) is not int or counted.input_tokens < 0:
            raise ContextLimitError('Invalid provider input token count')
        return counted.input_tokens

    async def __call__(self, data):
        self.hooks.check_cancelled()
        original = deepcopy(data.model_data.input)
        items = original
        if self.original_prefix is not None:
            if original[:len(self.original_prefix)] != self.original_prefix:
                raise ContextLimitError('SDK history changed after compaction')
            items = deepcopy(self.replacement) + original[len(self.original_prefix):]
        data.model_data = ModelInputData(input=items, instructions=data.model_data.instructions)
        request = self.request(data)
        count = await self.count(request)
        if count <= COMPACT_TOKEN_LIMIT:
            return data.model_data
        # Always keep scientific contracts, warnings, issues and the role's explicit task.
        if items[:len(self.pinned)] != self.pinned:
            raise ContextLimitError('Protected research state changed')
        if len(items) == len(self.pinned):
            if count > INPUT_TOKEN_LIMIT:
                raise ContextLimitError('Required research state exceeds the input token limit')
            await self.hooks.emit('context_pressure', input_tokens=count, reason='protected_state_only')
            return data.model_data
        if count > INPUT_TOKEN_LIMIT:
            # Do not dispatch even a compact model request beyond the allowed input ceiling.
            raise ContextLimitError('Working history exceeds the input limit; reduce the next tool page')
        compact_request = {'model': request['model'], 'input': request['input'],
                           'instructions': request.get('instructions', '')}
        fields = await self.hooks.start_model(operation='compact', **compact_request)
        async with asyncio.timeout(self.request_timeout_seconds):
            compacted = await self.client.responses.compact(**compact_request)
        output = [item.model_dump(mode='json') for item in compacted.output]
        carriers = [{key: item[key] for key in ('type', 'id', 'encrypted_content')}
                    for item in output if item['type'] == 'compaction']
        if not carriers:
            raise ContextLimitError('Provider returned no compaction state')
        usage = compacted.usage.model_dump(mode='json') if compacted.usage else None
        normalized = Usage(requests=1, input_tokens=(usage or {}).get('input_tokens', 0),
                           output_tokens=(usage or {}).get('output_tokens', 0),
                           total_tokens=(usage or {}).get('total_tokens', 0))
        self.hooks.usage.add(normalized)
        self.hooks.active = None
        await self.hooks.emit('model_end', **fields, usage=normalized, raw_usage=usage,
                              response_id=compacted.id, output=output)
        replacement = deepcopy(self.pinned) + carriers
        data.model_data = ModelInputData(input=replacement, instructions=data.model_data.instructions)
        after = await self.count(self.request(data))
        if after >= count or after > COMPACT_TOKEN_LIMIT:
            raise ContextLimitError('Compaction did not create usable context headroom')
        self.original_prefix, self.replacement = original, replacement
        await self.hooks.emit('context_compacted', input_tokens_before=count, input_tokens_after=after,
            source_sha256=sha256(json.dumps(items, sort_keys=True).encode()).hexdigest(),
            protected_items=len(self.pinned), output=output)
        return data.model_data
