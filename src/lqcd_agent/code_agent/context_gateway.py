"""Private HTTP admission boundary for the single Codex worker, not a Code backend.

Native compaction is advisory. Count each actual wire input before forwarding it;
never estimate tokens, truncate a request, or reuse a count for a different body.
"""
from contextlib import ExitStack, closing, contextmanager
from hashlib import sha256
import hmac
import httpx
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import socket
import sqlite3
import threading
import time
from urllib.parse import urlsplit

from lqcd_agent.control.strict_json import canonical_bytes, closed, digest, loads, require
from lqcd_agent.settings import INPUT_TOKEN_LIMIT, CODE_OUTPUT_TOKEN_LIMIT

# The pinned Responses input_tokens API's input-bearing fields. Keep values exact.
COUNT_FIELDS = frozenset({'model', 'input', 'instructions', 'parallel_tool_calls',
    'personality', 'reasoning', 'text', 'tool_choice', 'tools', 'truncation'})
# Known non-input fields used by Responses and the pinned native Codex client.
TRANSPORT_FIELDS = frozenset({'stream', 'store', 'include', 'metadata', 'client_metadata',
    'max_output_tokens', 'temperature', 'top_p', 'service_tier', 'prompt_cache_key',
    'prompt_cache_retention', 'prompt_cache_options', 'safety_identifier', 'user',
    'stream_options', 'max_tool_calls', 'previous_response_id', 'conversation', 'background'})
ROUTES = frozenset({'/v1/responses', '/v1/responses/compact', '/v1/responses/input_tokens'})
MAX_WIRE_BYTES = 64 * 1024 * 1024


class _Rejected(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def _validate(body, model):
    if not isinstance(body, dict) or body.get('model') != model:
        raise _Rejected(400, 'context_model_mismatch')
    if set(body) - COUNT_FIELDS - TRANSPORT_FIELDS:
        raise _Rejected(400, 'context_unsupported_request_field')
    if (body.get('previous_response_id') is not None or body.get('conversation') is not None or
            body.get('background') not in (None, False) or body.get('truncation', 'disabled') != 'disabled'):
        raise _Rejected(400, 'context_implicit_state_forbidden')
    # References and mutable remote URLs could resolve to different input at count
    # and inference time. Codex sends its transcript and local image bytes inline.
    def inspect(value):
        if isinstance(value, dict):
            if value.get('type') == 'item_reference':
                raise _Rejected(400, 'context_implicit_state_forbidden')
            for key, item in value.items():
                if key in ('image_url', 'file_url') and isinstance(item, str) and not item.startswith('data:'):
                    raise _Rejected(400, 'context_mutable_input_forbidden')
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
    inspect(body.get('input'))


class _NativeCheck(ValueError):
    """Only constant Host diagnostics, never provider content or tool arguments."""


def _native_check(condition, reason):
    if not condition:
        raise _NativeCheck(reason)


def _native_response(raw, content_type):
    events = []
    if content_type.split(';', 1)[0] == 'text/event-stream':
        for line in raw.splitlines():
            if not line or line.startswith((b'event:', b':', b'id:', b'retry:')):
                continue
            _native_check(line.startswith(b'data:'), 'Unsupported native response framing')
            data = line[5:].strip()
            if data == b'[DONE]':
                continue
            event = loads(data, canonical=False)
            _native_check(type(event) is dict and type(event.get('type')) is str, 'Invalid native response event')
            events.append(event)
        completed = [event for event in events if event['type'] == 'response.completed']
        _native_check(len(completed) == 1 and completed[0] is events[-1], 'Missing or conflicting final completion')
        response = completed[0].get('response')
        _native_check(type(response) is dict and all(
            type(event.get('response')) is dict and event['response'].get('id') == response.get('id') for event in events
            if event['type'] in ('response.created', 'response.queued', 'response.in_progress')),
            'Native lifecycle response identity changed')
        _native_check(not any(event['type'] in ('response.failed','response.incomplete') for event in events),
                      'Conflicting native terminal events')
    else:
        response = loads(raw, canonical=False)
    _native_check(type(response) is dict and response.get('status') == 'completed', 'Incomplete native response')
    return response, events


def _validate_effect(item, final, *, sealed):
    kind = final.get('type')
    if kind not in ('function_call', 'custom_tool_call', 'web_search_call'):
        return
    _native_check(all(item.get(key) == final.get(key) for key in ('call_id','namespace','name')),
                  'Native tool identity changed')
    field = {'function_call':'arguments','custom_tool_call':'input','web_search_call':'action'}[kind]
    argument = item.get(field)
    _native_check(argument == final.get(field) or not sealed and argument in (None, ''),
                  'Native tool effect changed')
    if sealed:
        _native_check(item.get('status') in (None, 'completed') and final.get('status') in (None, 'completed'),
                      'Incomplete native executable item')


def _response_tools(response, events):
    """Bind every executable item before native receives any response bytes."""
    output = response.get('output')
    # The pinned Responses protocol may omit the duplicate terminal output array.
    # Only completed stream items can supply it; an explicitly empty array stays empty.
    finished = {}
    for event in events:
        if event['type'] != 'response.output_item.done':
            continue
        position, item = event.get('output_index'), event.get('item')
        _native_check(type(position) is int and position >= 0 and position not in finished and type(item) is dict,
                      'Invalid or repeated completed native output position')
        finished[position] = item
    ordered = [finished[index] for index in sorted(finished)]
    if output is None and events:
        output = ordered
    _native_check(type(output) is list and (not events or len(output) == len(ordered)),
                  'Native streamed items missing from final output')
    # Responses may enrich completed snapshots with non-executable metadata
    # (including reasoning records). Bind effect-bearing fields, not presentation.
    for streamed, final in zip(ordered, output):
        _native_check(type(final) is dict and streamed.get('id') == final.get('id')
                      and streamed.get('type') == final.get('type'), 'Final native output identity changed')
        _validate_effect(streamed, final, sealed=True)
    indexed = {}
    tools = []
    for item in output:
        _native_check(type(item) is dict and type(item.get('id')) is str and bool(item['id'])
                      and item['id'] not in indexed, 'Native item identity missing or repeated')
        indexed[item['id']] = item
        kind = item.get('type')
        if kind in ('message', 'reasoning', 'compaction'):
            continue
        _native_check(kind in ('function_call', 'custom_tool_call', 'web_search_call'),
                      'Unrecognized executable native response item')
        _native_check(item.get('status') in (None, 'completed'), 'Incomplete native executable item')
        identity = {key: item.get(key) for key in ('id', 'type', 'call_id', 'name', 'namespace')}
        if kind in ('function_call', 'custom_tool_call'):
            _native_check(type(item.get('call_id')) is str and bool(item['call_id']),
                          'Native executable call identity missing')
        if kind == 'function_call':
            _native_check(type(item.get('arguments')) is str, 'Native tool arguments missing')
            identity['arguments_sha256'] = digest(loads(item['arguments'], canonical=False))
        elif kind == 'custom_tool_call':
            _native_check(type(item.get('input')) is str, 'Native custom tool input missing')
            identity['arguments_sha256'] = digest(item['input'])
        else:
            identity['arguments_sha256'] = digest(item.get('action'))
        tools.append(identity)
    call_ids = [item['call_id'] for item in tools if item['call_id']]
    _native_check(len(call_ids) == len(set(call_ids)), 'Native response repeated a tool call identity')
    added, closed_positions, deltas = set(), set(), {}
    argument_events = {'response.function_call_arguments.delta': ('function_call', 'arguments'),
                       'response.function_call_arguments.done': ('function_call', 'arguments'),
                       'response.custom_tool_call_input.delta': ('custom_tool_call', 'input'),
                       'response.custom_tool_call_input.done': ('custom_tool_call', 'input')}
    for event in events:
        kind = event['type']
        position = event.get('output_index')
        if kind in ('response.created', 'response.queued', 'response.in_progress'):
            # The SDK can replace even an already completed item from a lifecycle snapshot.
            snapshot = event['response'].get('output')
            if snapshot is None:
                continue
            _native_check(type(snapshot) is list, 'Invalid native lifecycle output')
            for index, item in enumerate(snapshot):
                expected = finished.get(index)
                _native_check(type(item) is dict and expected is not None and
                              item.get('type') == expected.get('type') and
                              (item.get('id') == expected.get('id') or index not in closed_positions and
                               item.get('id') is None and item.get('type') in ('function_call', 'custom_tool_call')),
                              'Unbound native lifecycle output')
                _validate_effect(item, expected, sealed=index in closed_positions)
            continue
        if kind == 'response.output_item.added' and event.get('item') is None:
            continue
        if kind not in ('response.output_item.added','response.output_item.done') and kind not in argument_events:
            continue
        _native_check(type(position) is int and position in finished and position not in closed_positions,
                      'Unbound or closed native output position')
        expected = finished[position]
        if kind == 'response.output_item.added':
            item = event.get('item')
            _native_check(type(item) is dict and position not in added and
                          all(item.get(key) == expected.get(key) for key in ('type','call_id','name','namespace'))
                          and (item.get('id') == expected['id'] or item.get('id') is None and
                               item['type'] in ('function_call', 'custom_tool_call')),
                          'Native streamed tool identity changed')
            if expected['type'] in ('function_call', 'custom_tool_call'):
                field = 'arguments' if expected['type'] == 'function_call' else 'input'
                initial = item.get(field)
                if initial:
                    _native_check(type(initial) is str, 'Invalid initial native tool arguments')
                    deltas[position] = [initial]
            added.add(position)
        elif kind == 'response.output_item.done':
            closed_positions.add(position)
        else:
            tool_kind, field = argument_events[kind]
            _native_check(expected['type'] == tool_kind and event.get('item_id') == expected['id'],
                          'Unbound native tool arguments')
            if kind.endswith('.delta'):
                chunk = event.get('delta')
                _native_check(type(chunk) is str, 'Invalid native argument delta')
                deltas.setdefault(position, []).append(chunk)
            else:
                _native_check(event.get(field) == expected[field], 'Native completed tool arguments changed')
    for position, chunks in deltas.items():
        item = finished[position]
        _native_check(''.join(chunks) == item['arguments' if item['type'] == 'function_call' else 'input'],
                      'Native streamed tool arguments changed')
    return tools


def _usage_tokens(value):
    usage = value.get('usage')
    if type(usage) is dict:
        fields = [usage.get(key) for key in ('input_tokens', 'output_tokens', 'total_tokens')]
        if all(type(n) is int and n >= 0 for n in fields) and fields[0] + fields[1] == fields[2]:
            return fields[2]


def _compact_usage(raw, content_type):
    # The pinned compact endpoint returns one JSON object, with optional status.
    # Only a complete transport body can settle the reservation at known usage.
    _native_check(content_type.split(';', 1)[0] == 'application/json', 'Invalid native compact response type')
    value = loads(raw, canonical=False)
    _native_check(type(value) is dict and value.get('object') == 'response.compaction' and
                  ('status' not in value or value['status'] == 'completed'), 'Incomplete native compaction')
    return _usage_tokens(value)


class CodingContextGateway:
    """Own the loopback endpoint and all its sockets for exactly one worker run."""
    def __init__(self, settings, job, *, producer_authority=None, task=None):
        self.settings, self.job = settings, job
        self.producer_authority, self.task = producer_authority, task
        self.numerical_trials = None
        self.token = secrets.token_urlsafe(32)
        self.upstream = urlsplit(settings.api_base.rstrip('/'))
        if (self.upstream.scheme not in ('http', 'https') or not self.upstream.hostname or
                self.upstream.username or self.upstream.password or self.upstream.query or self.upstream.fragment):
            raise ValueError('Invalid application API base URL')
        self._lock = threading.Lock()
        self._admission = threading.Lock()
        self._sockets = set()
        self._closed = False
        self.failed = threading.Event()
        self.failure_reason = None
        self.generation_usage_unknown = threading.Event()
        self._client = httpx.Client(follow_redirects=False,
            timeout=httpx.Timeout(settings.timeout_seconds, connect=min(settings.timeout_seconds, 10)))

    def __enter__(self):
        gateway = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_):
                pass
            def setup(self):
                super().setup()
                self.connection.settimeout(gateway.settings.timeout_seconds)
                gateway._add_socket(self.connection)
            def finish(self):
                try:
                    super().finish()
                finally:
                    gateway._discard_socket(self.connection)
            def do_POST(self):
                gateway._handle(self)
            def do_GET(self):
                gateway._error(self, 405, 'context_route_forbidden')
            do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_CONNECT = do_GET
        class Server(ThreadingHTTPServer):
            daemon_threads = True
            def handle_error(self, *_):
                # Request bytes and headers must never appear in worker logs.
                pass
        self.server = Server(('127.0.0.1', 0), Handler)
        self.base_url = f'http://127.0.0.1:{self.server.server_port}/v1'
        self._thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
        self._thread.start()
        return self

    def _add_socket(self, connection):
        with self._lock:
            if self._closed:
                connection.close()
                raise _Rejected(503, 'context_gateway_closed')
            self._sockets.add(connection)

    def _discard_socket(self, connection):
        with self._lock:
            self._sockets.discard(connection)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            sockets = tuple(self._sockets)
        for connection in sockets:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        if self.numerical_trials is not None:
            self.numerical_trials.close()
        self._client.close()
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(2)

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _model_budget(self):
        """One SQLite connection per HTTP thread, fenced by the original producer."""
        from lqcd_agent.control.coordinator import Coordinator
        from lqcd_agent.control.research_budget import ResearchBudget
        from .external_operation import ExternalDispatch
        if self.producer_authority is None:
            if (self.job.parent.parent / '.lqcd/control_operations.sqlite').exists():
                raise _Rejected(422, 'context_producer_authority_missing')
            yield None, None
            return
        try:
            closed(self.producer_authority, ('worker_owner_id', 'lease_epoch'))
            require(type(self.producer_authority['worker_owner_id']) is str and
                    bool(self.producer_authority['worker_owner_id']) and
                    type(self.producer_authority['lease_epoch']) is int and
                    self.producer_authority['lease_epoch'] > 0, 'Invalid native dispatch owner')
            require(self.task is not None and self.task['coding_backend_kind'] == 'codex' and
                    self.job.name == self.task['producer_operation_id'] and
                    self.job == self.job.resolve(), 'Native job identity changed')
            host = self.job.parent.parent
            require((host / '.lqcd/control_operations.sqlite').is_file(), 'Original native Host is absent')
            with closing(Coordinator(host)) as coordinator:
                locator = {key: self.task[key] for key in ('case_id', 'run_id')}
                budget = ResearchBudget.for_run(coordinator, locator)
                require(budget is not None, 'Application Native producer lacks its research quota')
                dispatch = ExternalDispatch(coordinator, self.task['producer_operation_id'],
                    self.producer_authority['worker_owner_id'], self.producer_authority['lease_epoch'],
                    None, None, None, None)
                def fence(db):
                    require(coordinator._time().monotonic_seconds < budget.binding['deadline'],
                            'Research task deadline exhausted before native model egress')
                    _, _, _, task, _ = dispatch.model_authority(db)
                    require(task == self.task, 'Native model task changed')
                yield budget, fence
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
            raise _Rejected(422, 'context_research_authority_or_quota_failed') from None

    def _admit_tools(self, budget, fence, ticket, tools):
        from .external_operation import ExternalDispatch
        dispatch = ExternalDispatch(budget.coordinator, self.task['producer_operation_id'],
            self.producer_authority['worker_owner_id'], self.producer_authority['lease_epoch'],
            None, None, None, None)
        with budget.coordinator.transaction() as db:
            fence(db)
            value, _, _, task, _ = dispatch.model_authority(db)
            intents = value.setdefault('native_tool_intents', [])
            _native_check(not any(entry['ticket'] == ticket for entry in intents), 'Native tool response replayed')
            _native_check(not ({entry['id'] for entry in intents} & {entry['id'] for entry in tools}) and
                    not ({entry['call_id'] for entry in intents if entry['call_id']} &
                         {entry['call_id'] for entry in tools if entry['call_id']}), 'Native tool item replayed')
            maximum = value['prestart']['aggregate']['request']['maximum_charge']['tool_calls']
            _native_check(len(intents) + len(tools) + len(task['write_paths']) <= maximum,
                    'Native response exceeds original Code tool allowance')
            intents.extend({**item, 'ticket': ticket} for item in tools)
            previous = value['phase_revision']
            value['phase_revision'] += 1
            _native_check(db.execute('UPDATE external_operations SET revision=?,value=? '
                'WHERE external_operation_id=? AND revision=?', (value['phase_revision'], canonical_bytes(value),
                    value['producer_operation_id'], previous)).rowcount == 1, 'Native tool admission CAS lost')

    @contextmanager
    def _request(self, path, raw, *, timeout_seconds, input_tokens=None, admit=None):
        if self.failed.is_set() or self._closed:
            raise _Rejected(422, 'context_gateway_failed')
        writing = False
        def observe(event, info):
            nonlocal writing
            # Retain pooled sockets so shutdown also interrupts reused connections
            # and requests still waiting for headers. HTTPX does not retry effects.
            if event in ('connection.connect_tcp.complete', 'connection.start_tls.complete',
                         'proxy.start_tls.complete'):
                self._add_socket(info['return_value'].get_extra_info('socket'))
            elif event == 'http11.send_request_headers.started' and info['request'].method == b'POST':
                self._admission.acquire()
                if self.failed.is_set() or self._closed:
                    self._admission.release()
                    raise _Rejected(422, 'context_gateway_failed')
                writing = True
                if admit is not None:
                    admit()
                if input_tokens is not None:
                    self._trace('/v1' + path, raw, input_tokens, 'admitted')
            elif writing and event in ('http11.send_request_body.complete', 'http11.send_request_body.failed',
                                        'http11.send_request_headers.failed'):
                writing = False
                self._admission.release()
        request = self._client.build_request('POST', self.settings.api_base.rstrip('/') + path, content=raw,
            headers={'Authorization': 'Bearer ' + self.settings.api_key, 'Content-Type': 'application/json',
                     'Accept-Encoding': 'identity'}, extensions={'trace': observe},
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10)))
        try:
            response = self._client.send(request, stream=True)
        finally:
            if writing:
                self._admission.release()
        try:
            yield response
        finally:
            response.close()

    def _trace(self, path, raw, tokens, admission, *, diagnostic=None):
        value = {'path': path, 'model': self.settings.coding_model, 'input_tokens': tokens,
                 'admission': admission, 'request_sha256': sha256(raw).hexdigest()}
        if diagnostic is not None:
            value['diagnostic'] = diagnostic
        with self._lock:
            descriptor = os.open(self.job / 'context_requests.jsonl',
                                 os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(json.dumps(value, separators=(',', ':')) + '\n')
                stream.flush()
                os.fsync(stream.fileno())

    def _fail(self, reason):
        with self._admission:
            if not self.failed.is_set():
                self.failure_reason = reason
                self.failed.set()

    @staticmethod
    def _error(handler, code, message):
        raw = json.dumps({'error': {'message': message, 'type': 'invalid_request_error', 'code': message}}).encode()
        handler.close_connection = True
        handler.send_response(code)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(raw)))
        handler.send_header('Connection', 'close')
        handler.end_headers()
        handler.wfile.write(raw)

    def _handle(self, handler):
        response_started = False
        raw = None
        tokens = None
        traced = False
        phase = upstream_status = error_type = native_reason = None
        resources = ExitStack()
        try:
            authorization = handler.headers.get_all('Authorization', [])
            if len(authorization) != 1 or not hmac.compare_digest(
                    authorization[0].encode(), ('Bearer ' + self.token).encode()):
                raise _Rejected(401, 'context_authentication_required')
            trial_route = handler.path == '/mcp' and self.numerical_trials is not None
            if ((handler.path not in ROUTES and not trial_route) or handler.headers.get('Upgrade') or
                    'upgrade' in handler.headers.get('Connection', '').lower()):
                raise _Rejected(400, 'context_route_forbidden')
            lengths = handler.headers.get_all('Content-Length', [])
            if (len(lengths) != 1 or not lengths[0].isdigit() or handler.headers.get('Transfer-Encoding') or
                    handler.headers.get('Content-Encoding', 'identity') != 'identity'):
                raise _Rejected(400, 'context_invalid_transport')
            size = int(lengths[0])
            if not 0 < size <= MAX_WIRE_BYTES:
                raise _Rejected(413, 'context_wire_size_exceeded')
            raw = handler.rfile.read(size)
            if len(raw) != size:
                raise _Rejected(400, 'context_incomplete_request')
            try:
                body = loads(raw, canonical=False)
            except ValueError:
                raise _Rejected(400, 'context_invalid_json') from None
            if trial_route:
                try:
                    reply = self.numerical_trials.rpc(body)
                except (ValueError, TypeError, KeyError):
                    self._fail('numerical_trial_integrity_or_authority_failed')
                    raise _Rejected(422, 'numerical_trial_integrity_or_authority_failed') from None
                encoded = b'' if reply is None else json.dumps(reply).encode()
                handler.send_response(202 if reply is None else 200)
                handler.send_header('Content-Type', 'application/json')
                handler.send_header('Content-Length', str(len(encoded)))
                handler.end_headers()
                response_started = True
                handler.wfile.write(encoded)
                return
            _validate(body, self.settings.coding_model)
            output_limit = CODE_OUTPUT_TOKEN_LIMIT
            if handler.path == '/v1/responses':
                output_limit = body.get('max_output_tokens', CODE_OUTPUT_TOKEN_LIMIT)
                if type(output_limit) is not int or not 0 < output_limit <= CODE_OUTPUT_TOKEN_LIMIT:
                    raise _Rejected(413, 'context_output_token_limit_exceeded')
                if 'max_output_tokens' not in body:
                    body['max_output_tokens'] = output_limit
                    raw = json.dumps(body, separators=(',', ':'), ensure_ascii=False).encode()
            budget, fence = resources.enter_context(self._model_budget())
            def count_admit():
                if budget is not None:
                    try:
                        with budget.coordinator.transaction() as db:
                            fence(db)
                    except (ValueError, OSError, sqlite3.Error):
                        raise _Rejected(422, 'context_research_authority_or_quota_failed') from None
            count_body = {key: value for key, value in body.items() if key in COUNT_FIELDS}
            phase = 'count'
            def expire_count():
                self._fail('context_token_count_failed')
                self.close()
            count_timer = threading.Timer(self.settings.timeout_seconds, expire_count)
            count_timer.daemon = True
            count_timer.start()
            try:
                try:
                    count_deadline = time.monotonic() + self.settings.timeout_seconds
                    # Only this read-only measurement may retry a broken connection.
                    # All attempts use the same body and original request deadline.
                    for attempt in range(1, 4):
                        upstream_status = None
                        try:
                            remaining = count_deadline - time.monotonic()
                            if remaining <= 0:
                                raise httpx.ReadTimeout('Input count deadline exhausted')
                            with self._request('/responses/input_tokens', json.dumps(count_body).encode(),
                                               timeout_seconds=remaining, admit=count_admit) as response:
                                upstream_status = response.status_code
                                if response.status_code != 200:
                                    raise ValueError('Invalid count status')
                                content = bytearray()
                                for chunk in response.iter_raw():
                                    content.extend(chunk)
                                    if len(content) > 65536:
                                        raise ValueError('Count response is too large')
                                counted = loads(bytes(content), canonical=False)
                            break
                        except (httpx.NetworkError, httpx.RemoteProtocolError, httpx.TimeoutException) as error:
                            delay = .25 * attempt
                            if attempt == 3 or time.monotonic() + delay >= count_deadline:
                                raise
                            self._trace(handler.path, raw, None, 'count_retry', diagnostic={
                                'phase': 'count', 'upstream_status': upstream_status,
                                'error_type': type(error).__name__, 'attempt': attempt})
                            time.sleep(delay)
                    tokens = counted['input_tokens']
                    if counted.get('object') != 'response.input_tokens' or type(tokens) is not int or tokens < 0:
                        raise ValueError('Invalid count')
                except (OSError, httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                    error_type = type(error).__name__
                    tokens = None
                    raise _Rejected(422, 'context_token_count_failed') from None
            finally:
                count_timer.cancel()
                count_timer.join()
            if tokens > INPUT_TOKEN_LIMIT:
                raise _Rejected(413, 'context_input_token_limit_exceeded')
            if handler.path == '/v1/responses/input_tokens':
                self._trace(handler.path, raw, tokens, 'admitted')
                traced = True
                # Counting cannot trigger inference; return the count already obtained.
                encoded = json.dumps(counted).encode()
                handler.close_connection = True
                handler.send_response(200)
                handler.send_header('Content-Type', 'application/json')
                handler.send_header('Content-Length', str(len(encoded)))
                handler.send_header('Connection', 'close')
                handler.end_headers()
                response_started = True
                handler.wfile.write(encoded)
                return
            phase, upstream_status = 'generation', None
            ticket, settled = None, False
            def admit():
                nonlocal ticket
                if budget is not None:
                    try:
                        ticket = budget.reserve(self.task['producer_operation_id'] + ':' + secrets.token_hex(16),
                            tokens, output_limit, fence=fence)
                    except (ValueError, OSError, sqlite3.Error):
                        raise _Rejected(422, 'context_research_authority_or_quota_failed') from None
            def settle(usage, *, check_authority=True):
                nonlocal settled
                if ticket is not None and not settled:
                    if usage is None:
                        self.generation_usage_unknown.set()
                    try:
                        budget.settle(ticket, usage, fence=fence if check_authority else None)
                    except (ValueError, OSError, sqlite3.Error):
                        raise _Rejected(422, 'context_research_authority_or_quota_failed') from None
                    settled = True
            try:
                with self._request(handler.path.removeprefix('/v1'), raw, input_tokens=tokens,
                                   timeout_seconds=self.settings.timeout_seconds, admit=admit) as response:
                    upstream_status = response.status_code
                    traced = True
                    if not 200 <= response.status_code < 300:
                        # Never pass redirect locations or provider error bodies to Codex.
                        raise _Rejected(response.status_code if response.status_code in (408, 409, 429) or
                                        response.status_code >= 500 else 422, 'context_upstream_request_failed')
                    content_type = response.headers.get('Content-Type', 'application/json')
                    # Hold metered responses until EOF. A prefix cannot prove usage, and
                    # native may execute tools immediately on receipt of a streamed item.
                    buffered = None
                    if budget is not None:
                        body_bytes = bytearray()
                        try:
                            for chunk in response.iter_raw():
                                body_bytes.extend(chunk)
                                _native_check(len(body_bytes) <= MAX_WIRE_BYTES, 'Native response is oversized')
                            buffered = bytes(body_bytes)
                            phase = 'native_response_validation'
                            if handler.path == '/v1/responses':
                                final, events = _native_response(buffered, content_type)
                                settle(_usage_tokens(final))
                                tools = _response_tools(final, events)
                                phase = 'native_tool_reservation'
                                self._admit_tools(budget, fence, ticket, tools)
                            else:
                                settle(_compact_usage(buffered, content_type))
                        except (ValueError, TypeError, KeyError, sqlite3.Error) as error:
                            error_type = type(error).__name__
                            native_reason = str(error) if isinstance(error, _NativeCheck) else None
                            raise _Rejected(422, 'context_native_tool_admission_failed') from None
                    handler.close_connection = True
                    handler.send_response(response.status_code)
                    handler.send_header('Content-Type', content_type)
                    handler.send_header('Connection', 'close')
                    handler.end_headers()
                    response_started = True
                    for chunk in ([buffered] if buffered is not None else response.iter_raw()):
                        handler.wfile.write(chunk)
                        handler.wfile.flush()
            finally:
                if ticket is not None and not settled:
                    self.generation_usage_unknown.set()
                    settle(None, check_authority=False)
        except _Rejected as error:
            retryable = (error.message == 'context_upstream_request_failed' and
                         (error.code in (408, 409, 429) or error.code >= 500))
            if retryable:
                self.generation_usage_unknown.set()
            if error.message in ('context_token_count_failed', 'context_input_token_limit_exceeded',
                    'context_output_token_limit_exceeded', 'context_producer_authority_missing',
                    'context_research_authority_or_quota_failed', 'context_native_tool_admission_failed') or (
                    error.message == 'context_upstream_request_failed' and not retryable):
                self._fail(error.message)
            if raw is not None and (not traced or error.message in
                    ('context_upstream_request_failed', 'context_native_tool_admission_failed')):
                diagnostic = ({'phase': phase, 'upstream_status': upstream_status,
                    'error_type': error_type or type(error).__name__} if error.message in
                    ('context_token_count_failed', 'context_upstream_request_failed', 'context_native_tool_admission_failed') else None)
                if native_reason is not None:
                    diagnostic['check'] = native_reason
                self._trace(handler.path, raw, tokens, error.message, diagnostic=diagnostic)
            if not response_started:
                self._error(handler, error.code, error.message)
        except (OSError, httpx.HTTPError) as error:
            # Codex owns retries inside the original operation; this gateway never
            # redispatches generation. A repeated request must be counted anew.
            retryable = phase == 'generation' and isinstance(error, httpx.HTTPError)
            if retryable:
                self.generation_usage_unknown.set()
            else:
                self._fail('context_upstream_request_failed')
            if raw is not None:
                self._trace(handler.path, raw, tokens, 'context_upstream_request_failed', diagnostic={
                    'phase': phase, 'upstream_status': upstream_status, 'error_type': type(error).__name__})
            if not response_started:
                self._error(handler, 502 if retryable else 422, 'context_upstream_request_failed')
        finally:
            resources.close()
