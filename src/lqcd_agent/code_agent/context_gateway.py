"""Private HTTP admission boundary for the single Codex worker, not a Code backend.

Native compaction is advisory. Count each actual wire input before forwarding it;
never estimate tokens, truncate a request, or reuse a count for a different body.
"""
from contextlib import contextmanager
from hashlib import sha256
import hmac
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import socket
import threading
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
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(2)

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _request(self, path, raw, *, input_tokens=None):
        if self.failed.is_set():
            raise _Rejected(422, 'context_gateway_failed')
        kind = HTTPSConnection if self.upstream.scheme == 'https' else HTTPConnection
        connection = kind(self.upstream.hostname, self.upstream.port, timeout=min(self.settings.timeout_seconds, 10))
        wire = None
        try:
            connection.connect()
            wire = connection.sock
            wire.settimeout(self.settings.timeout_seconds)
            self._add_socket(wire)
            # Serialize only admission and the request write with failure latching.
            # Responses/streams remain concurrent; close() uses a separate lock so
            # cancellation can shut sockets even during a blocked request write.
            with self._admission:
                if self.failed.is_set():
                    raise _Rejected(422, 'context_gateway_failed')
                if input_tokens is not None:
                    self._trace('/v1' + path, raw, input_tokens, 'admitted')
                connection.request('POST', self.upstream.path + path, body=raw,
                    headers={'Authorization': 'Bearer ' + self.settings.api_key, 'Content-Type': 'application/json',
                             'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            try:
                yield response
            finally:
                response.close()
        finally:
            connection.close()
            if wire is not None:
                self._discard_socket(wire)

    def _trace(self, path, raw, tokens, admission):
        value = {'path': path, 'model': self.settings.coding_model, 'input_tokens': tokens,
                 'admission': admission, 'request_sha256': sha256(raw).hexdigest()}
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
            try:
                with self._request('/responses/input_tokens', json.dumps(count_body).encode()) as response:
                    if response.status != 200:
                        raise ValueError('Invalid count status')
                    counted = loads(response.read(65537), canonical=False)
                tokens = counted['input_tokens']
                if counted.get('object') != 'response.input_tokens' or type(tokens) is not int or tokens < 0:
                    raise ValueError('Invalid count')
            except (OSError, HTTPException, ValueError, KeyError, TypeError):
                tokens = None
                raise _Rejected(422, 'context_token_count_failed') from None
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
            with self._request(handler.path.removeprefix('/v1'), raw, input_tokens=tokens) as response:
                traced = True
                if not 200 <= response.status < 300:
                    # Never pass redirect locations or provider error bodies to Codex.
                    raise _Rejected(422, 'context_upstream_request_failed')
                handler.close_connection = True
                handler.send_response(response.status)
                handler.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
                handler.send_header('Connection', 'close')
                handler.end_headers()
                response_started = True
                while chunk := response.read1(65536):
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
        except _Rejected as error:
            if error.message in ('context_token_count_failed', 'context_input_token_limit_exceeded',
                                 'context_upstream_request_failed'):
                self._fail(error.message)
            if raw is not None and not traced:
                self._trace(handler.path, raw, tokens, error.message)
            if not response_started:
                self._error(handler, error.code, error.message)
        except (OSError, HTTPException):
            self._fail('context_upstream_request_failed')
            if not response_started:
                self._error(handler, 422, 'context_upstream_request_failed')
