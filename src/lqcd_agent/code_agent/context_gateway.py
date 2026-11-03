"""Private HTTP admission boundary for the single Codex worker, not a Code backend.

Native compaction is advisory. Count each actual wire input before forwarding it;
never estimate tokens, truncate a request, or reuse a count for a different body.
"""
from contextlib import contextmanager
from hashlib import sha256
import hmac
import httpx
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit

from lqcd_agent.control.strict_json import loads
from lqcd_agent.research.context_policy import INPUT_TOKEN_LIMIT

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


class CodingContextGateway:
    """Own the loopback endpoint and all its sockets for exactly one worker run."""
    def __init__(self, settings, job):
        self.settings, self.job = settings, job
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
        self._client.close()
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(2)

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _request(self, path, raw, *, timeout_seconds, input_tokens=None):
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
        phase = upstream_status = error_type = None
        try:
            authorization = handler.headers.get_all('Authorization', [])
            if len(authorization) != 1 or not hmac.compare_digest(
                    authorization[0].encode(), ('Bearer ' + self.token).encode()):
                raise _Rejected(401, 'context_authentication_required')
            if (handler.path not in ROUTES or handler.headers.get('Upgrade') or
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
            _validate(body, self.settings.coding_model)
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
                                               timeout_seconds=remaining) as response:
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
            with self._request(handler.path.removeprefix('/v1'), raw, input_tokens=tokens,
                               timeout_seconds=self.settings.timeout_seconds) as response:
                upstream_status = response.status_code
                traced = True
                if not 200 <= response.status_code < 300:
                    # Never pass redirect locations or provider error bodies to Codex.
                    raise _Rejected(response.status_code if response.status_code in (408, 409, 429) or
                                    response.status_code >= 500 else 422, 'context_upstream_request_failed')
                handler.close_connection = True
                handler.send_response(response.status_code)
                handler.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                handler.send_header('Connection', 'close')
                handler.end_headers()
                response_started = True
                for chunk in response.iter_raw():
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
        except _Rejected as error:
            retryable = (error.message == 'context_upstream_request_failed' and
                         (error.code in (408, 409, 429) or error.code >= 500))
            if retryable:
                self.generation_usage_unknown.set()
            if error.message in ('context_token_count_failed', 'context_input_token_limit_exceeded') or (
                    error.message == 'context_upstream_request_failed' and not retryable):
                self._fail(error.message)
            if raw is not None and (not traced or error.message == 'context_upstream_request_failed'):
                diagnostic = ({'phase': phase, 'upstream_status': upstream_status,
                    'error_type': error_type or type(error).__name__} if error.message in
                    ('context_token_count_failed', 'context_upstream_request_failed') else None)
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
