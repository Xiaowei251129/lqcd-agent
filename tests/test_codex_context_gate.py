"""Real loopback HTTP proves admission and streaming, without model spend."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
from urllib.parse import urlsplit

import pytest

from lqcd_agent.code_agent.context_gateway import CodingContextGateway
from lqcd_agent.settings import ApplicationSettings, INPUT_TOKEN_LIMIT, CODE_OUTPUT_TOKEN_LIMIT


@contextmanager
def upstream(respond, connections=None):
    received = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *_):
            pass
        def do_POST(self):
            if connections is not None:
                connections.add(self.client_address)
            raw = self.rfile.read(int(self.headers['Content-Length']))
            received.append((self.path, raw, self.headers['Authorization']))
            status, content, kind = respond(self.path, raw)
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
    class Server(ThreadingHTTPServer):
        def handle_error(self, *_): pass
    server = Server(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def count_response(tokens):
    return 200, json.dumps({'object': 'response.input_tokens', 'input_tokens': tokens}).encode(), 'application/json'


def call(gateway, body, *, path='/responses', headers=None, method='POST'):
    endpoint = urlsplit(gateway.base_url)
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    connection = HTTPConnection(endpoint.hostname, endpoint.port, timeout=3)
    try:
        connection.request(method, '/v1' + path, body=raw,
            headers=headers if headers is not None else {'Authorization': 'Bearer ' + gateway.token})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


@pytest.mark.parametrize('path', ['/responses', '/responses/compact', '/responses/input_tokens'])
def test_actual_input_count_admits_exact_boundary_and_preserves_wire(tmp_path, path):
    original = {'model': 'gpt-6.1-terra', 'input': [{'role': 'user', 'content': 'private-input-marker'}],
                'instructions': 'private-instructions', 'tools': [{'type': 'function', 'name': 'query',
                'parameters': {'type': 'object', 'properties': {}}}], 'tool_choice': 'auto',
                'parallel_tool_calls': True, 'text': {'format': {'type': 'json_object'}},
                'reasoning': {'effort': 'high'}, 'personality': 'pragmatic', 'truncation': 'disabled',
                'stream': True, 'store': False, 'client_metadata': {'run': 'test'}, 'include': []}
    if path == '/responses':
        original['max_output_tokens'] = CODE_OUTPUT_TOKEN_LIMIT
    raw = json.dumps(original, indent=2).encode()
    response_bytes = b'event: response.completed\ndata: {"usage":{"input_tokens":256000}}\n\n'
    def respond(route, body):
        return count_response(INPUT_TOKEN_LIMIT) if route.endswith('/input_tokens') else (200, response_bytes, 'text/event-stream')
    with upstream(respond) as (base, received):
        settings = ApplicationSettings(api_key='test-secret-key', coding_model='gpt-6.1-terra', api_base=base)
        with CodingContextGateway(settings, tmp_path) as gateway:
            status, data = call(gateway, raw, path=path)
        assert status == 200
        assert received[0][0] == '/v1/responses/input_tokens'
        assert json.loads(received[0][1]) == {key: original[key] for key in (
            'model', 'input', 'instructions', 'tools', 'tool_choice', 'parallel_tool_calls',
            'text', 'reasoning', 'personality', 'truncation')}
        assert all(row[2] == 'Bearer test-secret-key' for row in received)
        if path == '/responses/input_tokens':
            assert len(received) == 1 and json.loads(data)['input_tokens'] == INPUT_TOKEN_LIMIT
        else:
            assert data == response_bytes and len(received) == 2
            assert received[1][:2] == ('/v1' + path, raw)
    trace = (tmp_path / 'context_requests.jsonl').read_text()
    assert json.loads(trace) == {'path': '/v1' + path, 'model': settings.coding_model,
        'input_tokens': INPUT_TOKEN_LIMIT, 'admission': 'admitted', 'request_sha256': sha256(raw).hexdigest()}
    assert all(secret not in trace for secret in ('test-secret-key', gateway.token, 'private-input-marker', 'private-instructions'))
    assert (tmp_path / 'context_requests.jsonl').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('path', ['/responses', '/responses/compact'])
@pytest.mark.parametrize('fault', ['oversize', 'count_429', 'count_redirect', 'bad_json', 'negative', 'bool'])
def test_oversize_or_failed_count_never_forwards_inference(tmp_path, path, fault):
    def respond(route, body):
        assert route == '/v1/responses/input_tokens'
        if fault == 'oversize': return count_response(INPUT_TOKEN_LIMIT + 1)
        if fault == 'count_429': return 429, b'private provider error', 'application/json'
        if fault == 'count_redirect': return 302, b'redirect', 'application/json'
        if fault == 'bad_json': return 200, b'not json', 'application/json'
        return count_response(-1 if fault == 'negative' else True)
    with upstream(respond) as (base, received):
        with CodingContextGateway(ApplicationSettings(api_key='test-key', api_base=base), tmp_path) as gateway:
            status, data = call(gateway, {'model': 'gpt-6-luna', 'input': 'request'}, path=path)
            assert gateway.failed.is_set()
            repeated, _ = call(gateway, {'model': 'gpt-6-luna', 'input': 'request'}, path=path)
            assert repeated == 422
        assert status == (413 if fault == 'oversize' else 422)
        assert len(received) == 1 and 'private provider error' not in data.decode()
    trace = json.loads((tmp_path / 'context_requests.jsonl').read_text().splitlines()[0])
    assert trace['admission'] == ('context_input_token_limit_exceeded' if fault == 'oversize' else 'context_token_count_failed')


@pytest.mark.parametrize('fault', ['auth', 'model', 'path', 'query', 'get', 'websocket', 'previous',
    'conversation', 'prompt', 'truncation', 'reference', 'remote_image', 'duplicate_key', 'unknown_field'])
def test_no_transport_or_hidden_state_bypass(tmp_path, fault):
    def respond(*_):
        pytest.fail('Rejected request reached the upstream')
    with upstream(respond) as (base, received):
        with CodingContextGateway(ApplicationSettings(api_key='test-key', api_base=base), tmp_path) as gateway:
            body = {'model': 'gpt-6-luna', 'input': 'request'}
            options = {}
            if fault == 'auth': options['headers'] = {'Authorization': 'Bearer wrong'}
            elif fault == 'model': body['model'] = 'different-model'
            elif fault == 'path': options['path'] = '/chat/completions'
            elif fault == 'query': options['path'] = '/responses?bypass=true'
            elif fault == 'get': options['method'] = 'GET'
            elif fault == 'websocket': options['headers'] = {'Authorization': 'Bearer ' + gateway.token, 'Upgrade': 'websocket'}
            elif fault == 'previous': body['previous_response_id'] = 'resp_old'
            elif fault == 'conversation': body['conversation'] = {'id': 'conv_old'}
            elif fault == 'prompt': body['prompt'] = {'id': 'stored_prompt'}
            elif fault == 'truncation': body['truncation'] = 'auto'
            elif fault == 'reference': body['input'] = [{'type': 'item_reference', 'id': 'item_old'}]
            elif fault == 'remote_image': body['input'] = [{'role': 'user', 'content': [{'type': 'input_image', 'image_url': 'https://example.invalid/image'}]}]
            elif fault == 'duplicate_key': body = b'{"model":"gpt-6-luna","input":"one","input":"two"}'
            elif fault == 'unknown_field': body['new_input_field'] = 'uncounted'
            status, _ = call(gateway, body, **options)
            assert 400 <= status < 500
        assert received == []


def test_streaming_delivers_before_completion_and_shutdown_closes_inflight(tmp_path):
    release = threading.Event()
    stream_started = threading.Event()
    class StreamingHandler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *_): pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            if self.path.endswith('/input_tokens'):
                content = count_response(100)[1]
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(b'data: first\n\n')
            self.wfile.flush()
            stream_started.set()
            release.wait(5)
    server = ThreadingHTTPServer(('127.0.0.1', 0), StreamingHandler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    try:
        settings = ApplicationSettings(api_key='test-key', api_base=f'http://127.0.0.1:{server.server_port}/v1')
        with CodingContextGateway(settings, tmp_path) as gateway:
            endpoint = urlsplit(gateway.base_url)
            client = socket.create_connection((endpoint.hostname, endpoint.port), timeout=2)
            try:
                raw = b'{"model":"gpt-6-luna","input":"test","stream":true}'
                client.sendall((f'POST /v1/responses HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {gateway.token}\r\n'
                                f'Content-Length: {len(raw)}\r\n\r\n').encode() + raw)
                received = b''
                while b'data: first\n\n' not in received:
                    received += client.recv(4096)
                assert stream_started.is_set() and not release.is_set()
                # An open stream must not hold the admission lock for other requests.
                assert call(gateway, {'model': 'gpt-6-luna', 'input': 'parallel count'},
                            path='/responses/input_tokens')[0] == 200
                start = time.monotonic()
                gateway.close()
                assert client.recv(4096) == b'' and time.monotonic() - start < 2
                assert not gateway._thread.is_alive()
            finally:
                client.close()
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_concurrent_count_cannot_forward_after_another_request_closes_admission(tmp_path):
    count_started = threading.Event()
    release_count = threading.Event()
    def respond(route, raw):
        body = json.loads(raw)
        if route == '/v1/responses/input_tokens':
            if body['input'] == 'delayed count':
                count_started.set()
                assert release_count.wait(5)
                return count_response(100)
            return 429, b'count failed', 'application/json'
        return 200, b'{"unexpected":"generation"}', 'application/json'
    with upstream(respond) as (base, received):
        with CodingContextGateway(ApplicationSettings(api_key='test-key', api_base=base), tmp_path) as gateway:
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(call, gateway, {'model': 'gpt-6-luna', 'input': 'delayed count'})
                try:
                    assert count_started.wait(2)
                    assert call(gateway, {'model': 'gpt-6-luna', 'input': 'failed count'})[0] == 422
                    assert gateway.failed.is_set()
                finally:
                    release_count.set()
                assert pending.result(timeout=3)[0] == 422
        assert [row[0] for row in received] == ['/v1/responses/input_tokens'] * 2
    entries = [json.loads(row) for row in (tmp_path / 'context_requests.jsonl').read_text().splitlines()]
    assert all(entry['admission'] != 'admitted' for entry in entries)


@pytest.mark.parametrize('phase', ['count', 'generation'])
def test_upstream_failure_is_private_and_only_native_generation_can_retry(tmp_path, phase):
    private = b'private-upstream-body test-secret-key'
    failed = False
    def respond(route, raw):
        nonlocal failed
        if route.endswith('/input_tokens') and phase == 'generation':
            return count_response(20)
        if not failed:
            failed = True
            return 429 if phase == 'count' else 503, private, 'application/json'
        return 200, b'{}', 'application/json'
    with upstream(respond) as (base, received):
        with CodingContextGateway(ApplicationSettings(api_key='test-secret-key', api_base=base), tmp_path) as gateway:
            request = {'model': 'gpt-6-luna', 'input': 'private-input'}
            status, body = call(gateway, request)
            assert status == (422 if phase == 'count' else 503)
            assert gateway.failed.is_set() is (phase == 'count')
            repeated, _ = call(gateway, request)
            assert repeated == (422 if phase == 'count' else 200)
        assert len(received) == (1 if phase == 'count' else 4)
        if phase == 'generation':
            assert [route for route, _, _ in received] == ['/v1/responses/input_tokens','/v1/responses']*2
    trace = (tmp_path/'context_requests.jsonl').read_text()
    failure = next(json.loads(line) for line in trace.splitlines() if 'diagnostic' in json.loads(line))
    assert failure['diagnostic']['phase'] == phase
    assert failure['diagnostic']['upstream_status'] == (429 if phase == 'count' else 503)
    assert all(value not in trace + body.decode() for value in
        ('private-upstream-body', 'private-input', 'test-secret-key', gateway.token))


def test_worker_reuses_upstream_connection_across_count_and_generation(tmp_path):
    connections = set()
    def respond(route, raw):
        return count_response(20) if route.endswith('/input_tokens') else (200, b'{}', 'application/json')
    with upstream(respond, connections) as (base, received):
        with CodingContextGateway(ApplicationSettings(api_key='test-key', api_base=base), tmp_path) as gateway:
            for text in ('first', 'second'):
                assert call(gateway, {'model': 'gpt-6-luna', 'input': text})[0] == 200
        assert len(received) == 4 and len(connections) == 1
        assert gateway._client.is_closed


def test_shutdown_interrupts_upstream_before_response_headers(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def respond(route, raw):
        entered.set()
        release.wait(5)
        return count_response(20)
    with upstream(respond) as (base, received):
        with CodingContextGateway(ApplicationSettings(api_key='test-key', api_base=base), tmp_path) as gateway:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(call, gateway, {'model': 'gpt-6-luna', 'input': 'pending count'})
                try:
                    assert entered.wait(2)
                    start = time.monotonic()
                    gateway.close()
                    with pytest.raises((OSError, HTTPException)):
                        pending.result(timeout=2)
                    assert time.monotonic() - start < 2
                finally:
                    release.set()


@pytest.mark.parametrize('case', ['recover', 'exhaust', 'oversize', 'deadline'])
def test_only_read_only_count_retries_identical_input_within_its_deadline(tmp_path, case):
    counts = []
    def respond(route, raw):
        if route.endswith('/input_tokens'):
            counts.append(raw)
            if case in ('exhaust', 'deadline') or len(counts) == 1:
                raise ConnectionResetError('fixture closes before headers')
            return count_response(INPUT_TOKEN_LIMIT + 1 if case == 'oversize' else 20)
        return 200, b'{}', 'application/json'
    with upstream(respond) as (base, received):
        settings = ApplicationSettings(api_key='test-key', api_base=base,
            timeout_seconds=.05 if case == 'deadline' else 3)
        with CodingContextGateway(settings, tmp_path) as gateway:
            status, _ = call(gateway, {'model': 'gpt-6-luna', 'input': 'fixed input'})
            assert status == {'recover': 200, 'oversize': 413}.get(case, 422)
            assert gateway.failed.is_set() is (case != 'recover')
            if case != 'recover':
                assert call(gateway, {'model': 'gpt-6-luna', 'input': 'retry'})[0] == 422
        assert len(counts) == {'recover': 2, 'oversize': 2, 'exhaust': 3, 'deadline': 1}[case]
        assert all(raw == counts[0] for raw in counts)
        assert sum(route == '/v1/responses' for route, _, _ in received) == (case == 'recover')
    rows = [json.loads(line) for line in (tmp_path/'context_requests.jsonl').read_text().splitlines()]
    assert sum(row['admission'] == 'count_retry' for row in rows) == len(counts)-1


def test_count_deadline_stops_a_slow_stream_without_generation(tmp_path):
    stopped = threading.Event()
    requests = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *_): pass
        def do_POST(self):
            requests.append(self.path)
            self.rfile.read(int(self.headers['Content-Length']))
            body = count_response(20)[1]
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                for byte in body:
                    self.wfile.write(bytes([byte])); self.wfile.flush()
                    if stopped.wait(.02): break
            except OSError:
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    try:
        settings = ApplicationSettings(api_key='test-key', api_base=f'http://127.0.0.1:{server.server_port}/v1',
            timeout_seconds=.1)
        with CodingContextGateway(settings, tmp_path) as gateway:
            start = time.monotonic()
            with pytest.raises((OSError, HTTPException)):
                call(gateway, {'model': 'gpt-6-luna', 'input': 'pending count'})
            assert time.monotonic()-start < 1 and gateway.failed.is_set()
            assert requests == ['/v1/responses/input_tokens']
    finally:
        stopped.set(); server.shutdown(); server.server_close(); thread.join(2)


@pytest.fixture
def native_producer(tmp_path, monkeypatch):
    """A real fenced native producer with its worker replaced by an owned idle process."""
    import subprocess
    import sys
    from pathlib import Path
    from contextlib import closing
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
    from lqcd_agent.control.storage import execution_scratch_root
    from lqcd_agent.control.strict_json import digest, loads
    from lqcd_agent.examples import prepare_code, SyntheticAgent
    from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
    from tests.support import mkdtemp
    launch = subprocess.Popen
    def idle(argv, **kwargs):
        if isinstance(argv, (list, tuple)) and 'lqcd_agent.code_agent.codex_worker' in argv:
            return launch([sys.executable, '-I', '-S', '-c', 'import time;time.sleep(120)'], **kwargs)
        return launch(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', idle)
    workspace = tmp_path / 'operator'
    workspace.mkdir()
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(workspace))
    host = Path(mkdtemp(prefix='lqcd-agent-host-', dir=execution_scratch_root()))
    with closing(Coordinator(host)) as coordinator:
        code, analysis = prepare_code(coordinator, live=True, initialize=True)
        actor = ActorContext('operator', 'human', ('control.internal', 'resume', 'start'))
        runtime = CanonicalProductRuntime(coordinator, worker_id='quota-fixture', actor=actor,
            agent_port=SyntheticAgent(), code_host=code, analysis_handoff=analysis)
        inputs = {'root_goal': {'goal': 'Inspect native model admission.', 'workflow': 'code', 'live': True,
            'workspace': str(workspace), 'research_task': {'id': digest(str(host)),
                'limits': {'runs': 1, 'model_calls': 2, 'tokens': 1_000_000, 'seconds': 3600},
                'deadline': coordinator._time().monotonic_seconds + 60, 'parent': None}},
            'input_snapshot': {'kind': 'offline_quota_fixture'}}
        created = runtime.plane.start_run(StartRunRequest('case', inputs, digest(inputs), 'quota-fixture'), actor=actor)
        locator = created['result']['run_locator']
        runtime.run(locator)
        producer = loads(coordinator.connection.execute('SELECT value FROM external_operations').fetchone()[0])
        job = code.backend.job(producer['producer_operation_id'])
        request = json.loads((job / 'request.json').read_text())
        assert request['producer_authority'] == {key: producer[key] for key in ('worker_owner_id', 'lease_epoch')}
        try:
            yield coordinator, locator, producer, job, request
        finally:
            code.backend.stop(producer['producer_operation_id'])


@pytest.mark.parametrize('chunk_size', [1, 19, 4096])
def test_completed_sse_usage_is_read_from_chunked_private_records(chunk_size):
    from lqcd_agent.code_agent.context_gateway import _UsageReader
    event = {'type': 'response.completed', 'response': {'id': 'response-fixture',
        'object': 'response', 'status': 'completed',
        'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}}}
    raw = ('event: response.completed\ndata: ' + json.dumps(event) + '\n\n').encode()
    reader = _UsageReader('text/event-stream; charset=utf-8')
    for offset in range(0, len(raw), chunk_size):
        reader.feed(raw[offset:offset + chunk_size])
    assert reader.complete and reader.tokens == 120


def test_native_repeats_share_real_quota_and_failed_usage_is_not_refunded(native_producer):
    from lqcd_agent.control.research_budget import ResearchBudget
    coordinator, locator, producer, job, request = native_producer
    generations = []
    def respond(path, raw):
        if path.endswith('/input_tokens'):
            return count_response(100)
        generations.append(json.loads(raw))
        if len(generations) == 1:
            return 503, b'private failed body', 'application/json'
        result = {'type': 'response.completed', 'response': {'id': 'response-fixture',
            'object': 'response', 'status': 'completed', 'usage': {
                'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}}}
        return 200, ('event: response.completed\ndata: '+json.dumps(result)+'\n\n').encode(), 'text/event-stream'
    with upstream(respond) as (base, received):
        settings = ApplicationSettings(api_key='offline-key', api_base=base)
        with CodingContextGateway(settings, job, producer_authority=request['producer_authority'],
                task=request['task']) as gateway:
            assert call(gateway, {'model': settings.coding_model, 'input': 'fixture'})[0] == 503
            assert call(gateway, {'model': settings.coding_model, 'input': 'fixture'})[0] == 200
            assert call(gateway, {'model': settings.coding_model, 'input': 'fixture'})[0] == 422
            assert gateway.failed.is_set() and gateway.generation_usage_unknown.is_set()
        assert len(generations) == 2
        assert all(row['max_output_tokens'] == CODE_OUTPUT_TOKEN_LIMIT for row in generations)
        counts = [json.loads(raw) for path, raw, _ in received if path.endswith('/input_tokens')]
        assert len(counts) == 3 and all('max_output_tokens' not in row for row in counts)
    snapshot = ResearchBudget(coordinator, locator).snapshot()
    assert snapshot['model_calls'] == 2 and snapshot['unknown_requests'] == 1
    assert snapshot['charged_tokens'] == 100 + CODE_OUTPUT_TOKEN_LIMIT + 120
    assert 'private failed body' not in (job / 'context_requests.jsonl').read_text()


@pytest.mark.parametrize('fault', ['epoch', 'backend_deadline', 'task_deadline', 'missing_authority'])
def test_native_stale_authority_cannot_spend_quota_or_forward(native_producer, fault, monkeypatch):
    from lqcd_agent.control.research_budget import ResearchBudget
    from lqcd_agent.control.strict_json import canonical_bytes
    coordinator, locator, producer, job, request = native_producer
    if fault == 'task_deadline':
        from lqcd_agent.control import coordinator as coordinator_module
        from lqcd_agent.control.clock import Timestamp
        original_clock = coordinator.clock
        class LaterClock:
            epoch_id = original_clock.epoch_id
            def now(self):
                stamp = original_clock.now()
                return Timestamp(stamp.source, stamp.wall_seconds + 61, stamp.monotonic_seconds + 61)
        monkeypatch.setattr(coordinator_module, 'HostClock', LaterClock)
    elif fault != 'missing_authority':
        changed = dict(producer)
        if fault == 'epoch':
            changed['lease_epoch'] += 1
        else:
            changed['dispatch_started_at'] = (coordinator._time().monotonic_seconds -
                changed['prestart']['aggregate']['request']['timeout_seconds'] - 1)
        changed['phase_revision'] += 1
        with coordinator.transaction() as db:
            db.execute('UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=?',
                (changed['phase_revision'], canonical_bytes(changed), changed['producer_operation_id']))
    with upstream(lambda path, raw: count_response(100)) as (base, received):
        settings = ApplicationSettings(api_key='offline-key', api_base=base)
        with CodingContextGateway(settings, job,
                producer_authority=None if fault == 'missing_authority' else request['producer_authority'],
                task=request['task']) as gateway:
            assert call(gateway, {'model': settings.coding_model, 'input': 'fixture'})[0] == 422
            assert gateway.failed.is_set()
        assert received == []
    assert ResearchBudget(coordinator, locator).snapshot()['model_calls'] == 0


def test_native_producer_control_windows_reject_large_floats(native_producer):
    from copy import deepcopy
    from lqcd_agent.control.operations import ExternalControl
    from lqcd_agent.control.strict_json import ControlIntegrityError
    coordinator, _, producer, _, _ = native_producer
    external_id = producer['producer_operation_id']
    revision, raw = coordinator.connection.execute(
        'SELECT revision,value FROM external_operations WHERE external_operation_id=?', (external_id,)).fetchone()
    external = ExternalControl(coordinator)
    original = external.read(coordinator.connection, external_id)
    for path in (('hard_deadline',), ('worker_lease_expires_at',), ('dispatch_started_at',),
                 ('prestart', 'active_time', 'backend_maximum_seconds'),
                 ('prestart', 'active_time', 'attempt_maximum_seconds'),
                 ('prestart', 'active_time', 'recovery_expires_at')):
        changed = deepcopy(original)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = 1e100
        with coordinator.transaction() as db:
            db.execute('UPDATE external_operations SET value=? WHERE external_operation_id=?',
                (json.dumps(changed, sort_keys=True, separators=(',', ':')).encode(), external_id))
        try:
            with pytest.raises(ControlIntegrityError, match='out-of-range number'):
                external.read(coordinator.connection, external_id)
        finally:
            with coordinator.transaction() as db:
                db.execute('UPDATE external_operations SET value=? WHERE external_operation_id=?', (raw, external_id))
        assert external.read(coordinator.connection, external_id) == original
        assert coordinator.connection.execute('SELECT revision FROM external_operations WHERE external_operation_id=?',
            (external_id,)).fetchone()[0] == revision


@pytest.mark.parametrize('limit', [True, 0, -1, CODE_OUTPUT_TOKEN_LIMIT + 1])
def test_native_output_limit_is_a_real_pre_dispatch_bound(tmp_path, limit):
    with upstream(lambda path, raw: count_response(100)) as (base, received):
        settings = ApplicationSettings(api_key='offline-key', api_base=base)
        with CodingContextGateway(settings, tmp_path) as gateway:
            status, _ = call(gateway, {'model': settings.coding_model, 'input': 'fixture',
                                       'max_output_tokens': limit})
            assert status == 413 and gateway.failed.is_set()
        assert received == []


def test_native_compaction_is_charged_without_unsupported_output_field(native_producer):
    from lqcd_agent.control.research_budget import ResearchBudget
    coordinator, locator, producer, job, request = native_producer
    def respond(path, raw):
        if path.endswith('/input_tokens'):
            return count_response(100)
        assert 'max_output_tokens' not in json.loads(raw)
        result = {'object': 'response.compaction', 'usage': {
            'input_tokens': 100, 'output_tokens': 10, 'total_tokens': 110}, 'output': []}
        return 200, json.dumps(result).encode(), 'application/json'
    with upstream(respond) as (base, received):
        settings = ApplicationSettings(api_key='offline-key', api_base=base)
        with CodingContextGateway(settings, job, producer_authority=request['producer_authority'],
                task=request['task']) as gateway:
            assert call(gateway, {'model': settings.coding_model, 'input': []}, path='/responses/compact')[0] == 200
            assert not gateway.failed.is_set()
        assert len(received) == 2
    snapshot = ResearchBudget(coordinator, locator).snapshot()
    assert snapshot['model_calls'] == 1 and snapshot['charged_tokens'] == 110


@pytest.mark.parametrize('terminal_status', ['failed', 'cancelled'])
def test_native_terminal_failure_is_promptly_stopped_with_real_proof(native_producer, terminal_status):
    from lqcd_agent.code_agent.codex_backend import CodexCodingBackend
    from lqcd_agent.control.operations import ExternalControl
    from lqcd_agent.control.strict_json import loads
    from lqcd_agent.inspection import read_snapshot
    from lqcd_agent.workbench.worker import step
    coordinator, locator, producer, job, _ = native_producer
    state_path = job / 'state.json'
    state = json.loads(state_path.read_text())
    state.update(status=terminal_status, error='OfflineNativeFailure',
                 error_message='Owned test worker failed without a scientific result.', finished_at=time.monotonic())
    state_path.write_text(json.dumps(state))
    failed_bytes = state_path.read_bytes()
    assert coordinator._time().monotonic_seconds < (producer['dispatch_started_at'] +
        producer['prestart']['aggregate']['request']['timeout_seconds'])
    identifier = coordinator.root.name.removeprefix('lqcd-agent-host-')
    assert step(identifier, locator)
    snapshot = read_snapshot(coordinator.root, locator)
    assert snapshot.state['run_status'] == 'halted' and snapshot.state['active_pause'] is None
    current = loads((snapshot.root / 'artifact_index.json').read_bytes())['current']
    assert current['terminal'] is None  # No successful code or scientific report is fabricated.
    final, proof = ExternalControl(coordinator).final_evidence(coordinator.connection,
        producer['producer_operation_id'])
    assert final['resolution_owner'] == 'interrupt' and proof['proof_kind'] == 'safe_stop'
    trigger = loads((snapshot.root / ('watchdog_' + producer['producer_operation_id'] + '_trigger.json')).read_bytes())
    failure = trigger['backend_failure']
    assert failure['status'] == terminal_status and failure['state_sha256'] == sha256(failed_bytes).hexdigest()
    assert (snapshot.root / failure['state_reference']).read_bytes() == failed_bytes
    backend = CodexCodingBackend(coordinator.root / 'coding_jobs', coordinator.root / 'code_workspaces')
    assert backend.lookup(producer['producer_operation_id'])['status'] == 'cancelled'
    before = (snapshot.root / 'execution_history.jsonl').read_bytes()
    assert not step(identifier, locator)
    assert (snapshot.root / 'execution_history.jsonl').read_bytes() == before
