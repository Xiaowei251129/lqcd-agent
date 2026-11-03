"""Owned service sentinels exercise the native command/network boundary without APIs."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import sys
import threading


@contextmanager
def operator_service(directory):
    """Expose only synthetic tokens, including a writable-root Unix target."""
    hits = []
    class HTTP(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            hits.append('http')
            body = b'{"token":"synthetic-operator-sentinel"}'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    path = directory/'operator.sock'
    http = ThreadingHTTPServer(('127.0.0.1', 0), HTTP)
    thread = threading.Thread(target=http.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    unix = None
    try:
        # A relative bind avoids macOS's short sockaddr_un limit without an alias
        # or changing the parent process cwd/shared sandbox roots.
        script = ("import socket\n"
                  "s=socket.socket(socket.AF_UNIX);s.bind('operator.sock');s.listen(1)\n"
                  "print('ready',flush=True)\n"
                  "c,_=s.accept();c.sendall(b'synthetic-operator-sentinel');c.close()\n")
        from lqcd_agent.settings import child_environment
        unix = subprocess.Popen([sys.executable, '-I', '-S', '-c', script], cwd=directory,
            env=child_environment(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        assert unix.stdout.readline() == 'ready\n', 'Synthetic Unix listener did not start'
        yield http.server_port, str(path), hits
    finally:
        http.shutdown(); http.server_close(); thread.join()
        if unix is not None:
            if unix.poll() is None:
                unix.terminate()
            unix.communicate(timeout=5)
        path.unlink(missing_ok=True)


def network_probe(port, unix_path, *, managed):
    """A proxy-aware client and a deliberate bypass must both miss local authority."""
    return f"""import os,socket,urllib.request,urllib.error,urllib.parse
port={port!r}
path={unix_path!r}
managed={managed!r}
url='http://127.0.0.1:'+str(port)+'/api/session'
request=urllib.request.Request(url,headers={{'Host':'127.0.0.1:'+str(port),'Origin':'http://127.0.0.1:'+str(port)}})
openers=[urllib.request.build_opener(urllib.request.ProxyHandler({{}}))]
if managed:
 proxy=os.environ['HTTP_PROXY']
 parsed=urllib.parse.urlsplit(proxy)
 assert parsed.hostname=='127.0.0.1' and parsed.port>0
 openers.append(urllib.request.build_opener(urllib.request.ProxyHandler({{'http':proxy}})))
for opener in openers:
 try: opener.open(request,timeout=3).read()
 except urllib.error.HTTPError as error: assert managed and error.code==403
 except urllib.error.URLError as error: assert isinstance(error.reason,PermissionError)
 else: raise AssertionError('Command reached local operator service')
os.chdir(os.path.dirname(path))
s=socket.socket(socket.AF_UNIX)
try: s.connect(os.path.basename(path))
except PermissionError: pass
else: raise AssertionError('Command reached local Unix service')
finally: s.close()
"""


def _responses_stream(item):
    import json
    from openai.types.responses import Response
    response = Response(id='response-fixture', created_at=0, model='gpt-6.1-terra', object='response',
        output=[item], parallel_tool_calls=True, tool_choice='auto', tools=[], status='completed',
        usage={'input_tokens':100, 'output_tokens':20, 'total_tokens':120,
               'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},
               'output_tokens_details':{'reasoning_tokens':0}}).model_dump(mode='json', exclude_none=True)
    item = response['output'][0]
    events = [{'type':'response.created', 'response':{**response,'status':'in_progress','output':[]}},
        {'type':'response.output_item.added','output_index':0,'item':{**item,'status':'in_progress',
            **({'arguments':''} if item['type']=='function_call' else {'content':[]})}}]
    if item['type'] == 'function_call':
        events += [{'type':'response.function_call_arguments.delta','item_id':item['id'],
                    'output_index':0,'delta':item['arguments']},
                   {'type':'response.function_call_arguments.done','item_id':item['id'],
                    'output_index':0,'arguments':item['arguments']}]
    else:
        part = item['content'][0]
        common = {'item_id':item['id'],'output_index':0,'content_index':0}
        events += [{'type':'response.content_part.added',**common,'part':{**part,'text':''}},
                   {'type':'response.output_text.delta',**common,'delta':part['text']},
                   {'type':'response.output_text.done',**common,'text':part['text'],'logprobs':[]},
                   {'type':'response.content_part.done',**common,'part':part}]
    events += [{'type':'response.output_item.done','output_index':0,'item':item},
               {'type':'response.completed','response':response}]
    return b''.join(('event: '+event['type']+'\ndata: '+json.dumps({**event,'sequence_number':i})+
                     '\n\n').encode() for i,event in enumerate(events))


def test_pinned_sdk_rejects_scope_escalation_before_command_execution(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    import signal
    from lqcd_agent.code_agent import codex_worker
    from lqcd_agent.settings import ApplicationSettings
    from tests.test_codex_context_gate import upstream, count_response
    workspace = tmp_path/'workspace'; workspace.mkdir()
    (workspace/'analysis.py').write_text('print(1)\n')
    job = tmp_path/'job'; job.mkdir()
    forbidden = tmp_path/'forbidden-permission-sentinel'
    task = {'write_paths':['analysis.py'],'forbidden_paths':['.git'],
        'requirements':['Return the existing analysis.py path.'], 'acceptance_criteria':['No scope expansion.'],
        'network_policy':{'enabled':True},'tool_policy':[{'timeout_seconds':45}]}
    (job/'request.json').write_text(json.dumps({'task':task,'manifest':{},'workspace':str(workspace),
                                             'base_paths':['analysis.py']}))
    (job/'state.json').write_text('{"status":"accepted"}')
    requests = []
    def respond(route, raw):
        if route.endswith('/input_tokens'):
            return count_response(100)
        body = json.loads(raw); requests.append(body)
        if len(requests) == 1:
            assert any(tool.get('name') == 'exec_command' for tool in body['tools'])
            item = {'id':'escalation-fixture','type':'function_call','name':'exec_command',
                'call_id':'escalation-call','status':'completed','arguments':json.dumps({
                    'cmd':'touch '+str(forbidden),'sandbox_permissions':'require_escalated',
                    'justification':'Synthetic authorization-boundary probe'})}
        else:
            assert len(requests) == 2
            item = {'id':'final-fixture','type':'message','role':'assistant','status':'completed',
                'content':[{'type':'output_text','text':json.dumps({'files':[{'path':'analysis.py'}]}),
                            'annotations':[],'logprobs':[]}]}
        return 200,_responses_stream(item),'text/event-stream'
    with upstream(respond) as (base, received):
        monkeypatch.setattr(codex_worker.ApplicationSettings, 'load', lambda:
            ApplicationSettings(api_key='offline-test',api_base=base,coding_model='gpt-6.1-terra'))
        monkeypatch.setattr(codex_worker,'workspace_root',lambda:Path(__file__).resolve().parents[1])
        previous = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
        try:
            assert codex_worker.run(job) == 0
        finally:
            signal.signal(signal.SIGTERM,previous[0]); signal.signal(signal.SIGINT,previous[1])
    assert len(requests) == 2
    refused = [item for item in requests[1]['input'] if item.get('type') == 'function_call_output']
    assert len(refused) == 1 and 'approval policy is Never' in refused[0]['output']
    assert not forbidden.exists() and (workspace/'analysis.py').read_text() == 'print(1)\n'
    assert json.loads((job/'state.json').read_text())['status'] == 'completed'
    assert json.loads((job/'state.json').read_text()).get('tool_count',0) == 0
    assert [route for route,_,_ in received] == ['/v1/responses/input_tokens','/v1/responses']*2
