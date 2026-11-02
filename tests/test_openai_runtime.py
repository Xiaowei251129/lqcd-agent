"""Application credentials and the bounded Codex SDK lifecycle."""
import asyncio
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from lqcd_agent.settings import ApplicationSettings, child_environment, read_env


def test_application_env_is_private_and_not_inherited(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('OPENAI_API_KEY=private-test-value\nOPENAI_MODEL=gpt-6-luna\n')
    path.chmod(0o600)
    settings = ApplicationSettings.load(path)
    assert settings.api_key == 'private-test-value' and 'private-test-value' not in repr(settings)
    monkeypatch.setenv('OPENAI_API_KEY','personal-test-value')
    runtime = settings.research_runtime()
    try:
        assert runtime._client.api_key == 'private-test-value'
        assert runtime.model.model == 'gpt-6-luna'
        assert runtime._client.max_retries == 0
    finally:
        asyncio.run(runtime.aclose())
    assert runtime._client.is_closed()
    assert os.environ['OPENAI_API_KEY'] == 'personal-test-value'
    monkeypatch.setenv('CODEX_HOME','/personal/codex')
    assert 'OPENAI_API_KEY' not in child_environment() and 'CODEX_HOME' not in child_environment()
    path.chmod(0o644)
    with pytest.raises(ValueError, match='private regular file'):
        read_env(path)
    path.chmod(0o600)
    alias=tmp_path/'alias'; alias.symlink_to(path)
    with pytest.raises(OSError):
        read_env(alias)


@pytest.mark.parametrize('network',[True,False])
def test_sdk_worker_enables_tools_and_review_with_task_network_policy(tmp_path, monkeypatch,network):
    from lqcd_agent.code_agent import codex_worker
    import openai_codex
    settings=ApplicationSettings(api_key='private-test-value')
    monkeypatch.setattr(codex_worker.ApplicationSettings, 'load', lambda: settings)
    monkeypatch.setenv('TMPDIR','/private/tmp')
    monkeypatch.setattr(codex_worker, 'workspace_root', lambda: Path(__file__).resolve().parents[1])
    workspace=tmp_path/'workspace';workspace.mkdir()
    task={'write_paths':['sample.py'],'requirements':['Return 2'],'acceptance_criteria':['value()==2'],
          'network_policy':{'enabled':network},'tool_policy':[{'timeout_seconds':240}]}
    (tmp_path/'request.json').write_text(json.dumps({'task':task,'manifest':{},'workspace':str(workspace),'base_paths':['sample.py']}))
    (tmp_path/'state.json').write_text('{"status":"accepted"}')
    observed={}
    result=NS(status=NS(value='completed',__str__=lambda _: 'completed'),
        final_response=json.dumps({'files':[{'path':'sample.py','content':'def value():\n    return 2\n'}]}),usage=None,items=[])
    item={'id':'command-1','type':'commandExecution','command':'python --version','status':'completed'}
    event_item=NS(model_dump=lambda **_:item)
    compact_item=NS(model_dump=lambda **_:{'id':'compact-1','type':'contextCompaction'})
    usage=NS(model_dump=lambda **_:{'modelContextWindow':243200,'last':{'inputTokens':400}})
    events=([NS(method=name,payload=NS(turn_id='turn',item=compact_item))
             for name in ('item/started','item/completed')] +
            [NS(method='thread/tokenUsage/updated',payload=NS(turn_id='turn',token_usage=usage))] +
            [NS(method=name,payload=NS(turn_id='turn',item=event_item))
             for name in ('item/started','item/completed')])
    def collect(stream, *, turn_id):
        assert turn_id=='turn' and len(list(stream))==5
        result.items=[event_item]
        return result
    monkeypatch.setattr('openai_codex._run._collect_turn_result',collect)
    class FakeCodex:
        def __init__(self, config): observed['config']=config
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def login_api_key(self,key): observed['key']=key
        def account(self): return NS(account=NS(root=NS(type='apiKey')))
        def thread_start(self, **kwargs):
            observed['thread']=kwargs
            def turn(prompt, **kwargs):
                assert 'Existing workspace files (read with tools as needed): ["sample.py"]' in prompt
                return NS(id='turn',stream=lambda:iter(events),interrupt=lambda:None)
            return NS(id='thread', turn=turn)
    monkeypatch.setattr(openai_codex,'Codex',FakeCodex)
    before=signal.getsignal(signal.SIGTERM),signal.getsignal(signal.SIGINT)
    try:
        assert codex_worker.run(tmp_path)==0
    finally:
        signal.signal(signal.SIGTERM,before[0]);signal.signal(signal.SIGINT,before[1])
    config=observed['config']; overrides=config.config_overrides
    assert observed['key'] != settings.api_key and config.codex_bin is None
    assert any(entry.startswith('openai_base_url="http://127.0.0.1:') for entry in overrides)
    assert config.env['CODEX_HOME']==str(tmp_path/'codex-home')
    temporary=tmp_path/'codex-home/tmp'
    assert config.env['TMPDIR']==str(temporary) and temporary.stat().st_mode & 0o777==0o700
    assert 'cli_auth_credentials_store="ephemeral"' in overrides
    assert 'permissions.lqcd.network.enabled='+str(network).lower() in overrides and 'default_permissions="lqcd"' in overrides
    assert not any(entry.startswith(('features.','tools.')) for entry in overrides)
    assert 'web_search='+json.dumps('live' if network else 'disabled') in overrides and 'project_doc_max_bytes=0' in overrides
    import tomllib
    tool_overrides=[entry for entry in overrides if entry.startswith('shell_environment_policy.')]
    assert len(tool_overrides)==1 and tool_overrides[0].startswith('shell_environment_policy.set=')
    tool_environment=tomllib.loads(tool_overrides[0])['shell_environment_policy']['set']
    assert tool_environment=={'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(temporary),
                             'TMPPREFIX':str(temporary/'zsh'),'RUFF_CACHE_DIR':str(temporary/'ruff')}
    assert 'OPENAI_API_KEY' not in config.env and observed['thread']['approval_mode']==openai_codex.ApprovalMode.auto_review
    (workspace/'sample.py').write_text('def value():\n    return 2\n')
    environment={**config.env,**tool_environment}
    # Exercise the production profile with the pinned native sandbox, without a model call.
    from codex_cli_bin import bundled_codex_path
    sentinel=tmp_path/'host-sentinel.txt';sentinel.write_text('owned-public-sentinel')
    command=[str(bundled_codex_path())]
    for entry in overrides:
        command.extend(['--config',entry])
    script="""set -eu
printf '\n' >> "$1/sample.py"
/bin/cat > "$2/tool-scratch" <<'HERE'
temporary
HERE
if /bin/cat "$3" >/dev/null 2>&1; then exit 31; fi
if (printf changed > "$3") 2>/dev/null; then exit 32; fi
"$4" check sample.py
"""
    command.extend(['sandbox','--permission-profile','lqcd','--cd',str(workspace),'--',
                    '/bin/zsh','-fc',script,'probe',str(workspace),str(temporary),str(sentinel),
                    str(Path(sys.executable).with_name('ruff'))])
    checked=subprocess.run(command,cwd=workspace,env=environment,capture_output=True,text=True,timeout=10)
    assert checked.returncode==0, checked.stderr
    assert sentinel.read_text()=='owned-public-sentinel'
    assert (temporary/'tool-scratch').read_text()=='temporary\n'
    assert (workspace/'sample.py').read_text()=='def value():\n    return 2\n\n'
    subprocess.run([sys.executable,'-c','import sample; assert sample.value()==2'],
        cwd=workspace,env=environment,capture_output=True,check=True,timeout=10)
    assert sorted(p.name for p in workspace.iterdir())==['sample.py']
    assert (temporary/'ruff').is_dir()
    state=json.loads((tmp_path/'state.json').read_text())
    assert state['status']=='completed' and state['tool_count']==1
    assert len(state['tool_events'])==1
    assert [(entry['id'],entry['event']) for entry in state['context_compactions']]==[
        ('compact-1','item/started'),('compact-1','item/completed')]
    assert state['usage']=={'modelContextWindow':243200,'last':{'inputTokens':400}}
    assert json.loads((tmp_path/'proposal.json').read_text())['items']==[item]
    assert all('private-test-value' not in p.read_text() for p in tmp_path.rglob('*.json'))


def test_sdk_tool_count_is_available_before_delivery(tmp_path):
    from lqcd_agent.code_agent.codex_backend import CodexCodingBackend,ProcessContainment
    backend=CodexCodingBackend(tmp_path/'jobs',tmp_path/'workspaces')
    job=backend.job('operation');job.mkdir()
    (job/'state.json').write_text(json.dumps({'status':'running','tool_count':3}))
    containment=ProcessContainment(backend)
    containment.start('operation','workspace')
    assert containment.observed_tool_count('operation')==3
    containment.record_tool('operation')
    assert containment.observed_tool_count('operation')==4


@pytest.mark.parametrize('fault',[None,'missing_completion','unobserved','changed_hash'])
def test_sdk_abandoned_tool_is_charged_without_fabricated_completion(fault):
    from hashlib import sha256
    from lqcd_agent.code_agent.codex_backend import sdk_tool_audit
    from lqcd_agent.control.strict_json import ControlIntegrityError
    item={'id':'done','type':'commandExecution','status':'completed'}
    events=[{'id':'done','start_at':1,'end_at':2,'sha256':sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()},
            {'id':'abandoned','start_at':1.5,'sha256':'a'*64}]
    items=[item]
    if fault=='missing_completion':items=[]
    elif fault=='unobserved':events.pop(0)
    elif fault=='changed_hash':events[0]['sha256']='b'*64
    args=({'task_id':'task','tool_policy':[{'spec_id':'sdk','argv':['codex:task']}]},
          {'workspace_id':'workspace'},events,items)
    if fault:
        with pytest.raises(ControlIntegrityError):sdk_tool_audit(*args,stopped_at=3)
    else:
        audit=sdk_tool_audit(*args,stopped_at=3)
        assert [r['status'] for r in audit]==['completed','failed']
        assert audit[1]['end_at']==3 and sum(r['resource_usage']['tool_calls'] for r in audit)==2


def test_real_backend_stop_verifies_pid_and_drains_group(tmp_path):
    from lqcd_agent.code_agent.codex_backend import CodexCodingBackend, process_identity, group_members
    from lqcd_agent.control.clock import host_boot_id
    backend=CodexCodingBackend(tmp_path/'jobs',tmp_path/'workspaces')
    job=backend.job('operation');job.mkdir()
    script = '''import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-I', '-S', '-c',
    'import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print(os.getpid(),flush=True); time.sleep(120)'],
    stdout=subprocess.PIPE, text=True)
print(child.stdout.readline().strip(), flush=True)
time.sleep(120)
'''
    process=subprocess.Popen([sys.executable,'-I','-S','-c',script], start_new_session=True,
        stdout=subprocess.PIPE, text=True)
    backend.children['operation']=process
    child_pid = int(process.stdout.readline())
    identity={'pid':process.pid,'start_ticks':process_identity(process.pid),'boot_id':host_boot_id()}
    (job/'process.json').write_text(json.dumps(identity))
    try:
        assert child_pid in group_members(process.pid)
        backend.stop('operation')
        assert process.poll() is not None and not group_members(process.pid)
    finally:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait()
        process.stdout.close()


def test_host_clock_epoch_survives_fresh_cli_process():
    from lqcd_agent.control.clock import HostClock
    child = subprocess.check_output([sys.executable, '-B', '-c',
        'from lqcd_agent.control.clock import HostClock; print(HostClock().epoch_id)'], text=True, timeout=30)
    assert child.strip() == HostClock().epoch_id


@pytest.mark.parametrize('field,value,message', [('start_ticks', 'foreign', 'PID identity changed'),
    ('boot_id', 'foreign', 'Foreign backend Host')])
def test_backend_stop_rejects_foreign_identity_before_signalling(tmp_path, field, value, message):
    from lqcd_agent.code_agent.codex_backend import CodexCodingBackend, process_identity
    from lqcd_agent.control.clock import host_boot_id
    from lqcd_agent.control.strict_json import ControlIntegrityError
    backend = CodexCodingBackend(tmp_path/'jobs', tmp_path/'workspaces')
    job = backend.job('operation'); job.mkdir()
    process = subprocess.Popen([sys.executable, '-I', '-S', '-c', 'import time;time.sleep(120)'], start_new_session=True)
    identity = {'pid': process.pid, 'start_ticks': process_identity(process.pid), 'boot_id': host_boot_id()}
    (job/'process.json').write_text(json.dumps({**identity, field: value}))
    try:
        with pytest.raises(ControlIntegrityError, match=message):
            backend.stop('operation')
        assert process.poll() is None
    finally:
        os.killpg(process.pid, signal.SIGKILL); process.wait()


@pytest.mark.parametrize('source,valid', [('def value(): return 2',True),
    ('import os\ndef value(): return 2',False),('def value(): return 3',False)])
def test_sample_analysis_validates_structure_before_execution(tmp_path, source, valid):
    from lqcd_agent.examples import SAMPLE_ANALYSIS_COMMAND
    (tmp_path/'sample.py').write_text(source)
    result=subprocess.run([sys.executable,'-I','-S','-c',SAMPLE_ANALYSIS_COMMAND],cwd=tmp_path,
        env={'PATH':os.defpath},capture_output=True,timeout=10)
    assert (result.returncode==0)==valid
    if valid:assert result.stdout.strip()==b'2'


def test_backend_dispatch_is_idempotent_conflicts_fail_and_cancel_stops(tmp_path, monkeypatch):
    from lqcd_agent.code_agent import codex_backend as module
    from lqcd_agent.control.strict_json import digest, ControlIntegrityError
    monkeypatch.setattr(module,'validate_task',lambda task:NS(value=task))
    monkeypatch.setattr(module,'validate_manifest',lambda manifest,task:NS(value=manifest))
    workspace_root=tmp_path/'workspaces';workspace=workspace_root/'workspace';workspace.mkdir(parents=True)
    (workspace/'sample.py').write_text('def value(): return 1\n#' + 'large base source ' * 20000)
    backend=module.CodexCodingBackend(tmp_path/'jobs',workspace_root)
    task={'producer_operation_id':'operation','coding_backend_kind':'codex','backend_version':backend.version,
          'task_id':'task','task_digest':digest('task')}
    manifest={'workspace_id':'workspace','manifest_digest':digest('manifest')}
    launch=subprocess.Popen; calls=[]
    def worker(argv, **kwargs):
        if argv[1:4] != ['-B', '-m', 'lqcd_agent.code_agent.codex_worker']:
            return launch(argv, **kwargs)
        assert argv[3]=='lqcd_agent.code_agent.codex_worker' and 'OPENAI_API_KEY' not in kwargs['env']
        calls.append(argv)
        return launch([sys.executable,'-I','-S','-c','import time;time.sleep(120)'],**kwargs)
    monkeypatch.setattr(module.subprocess,'Popen',worker)
    try:
        receipt=backend.dispatch(task,manifest,'operation')
        request=json.loads((backend.job('operation')/'request.json').read_text())
        assert request['base_paths']==['sample.py'] and 'base_files' not in request
        assert 'large base source' not in json.dumps(request)
        assert backend.dispatch(task,manifest,'operation')==receipt and len(calls)==1
        with pytest.raises(ControlIntegrityError,match='Conflicting Codex dispatch'):
            backend.dispatch({**task,'task_digest':digest('different')},manifest,'operation')
        assert backend.cancel('operation','operator_cancel')['status']=='cancelled'
        assert backend.children['operation'].poll() is not None
    finally:
        backend.stop('operation')


def test_sdk_worker_redacts_both_upstream_and_local_credentials(tmp_path, monkeypatch):
    from lqcd_agent.code_agent import codex_worker
    import openai_codex
    settings = ApplicationSettings(api_key='private-upstream-test-value')
    monkeypatch.setattr(codex_worker.ApplicationSettings, 'load', lambda: settings)
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    request = {'task': {'network_policy': {'enabled': False}}, 'manifest': {}, 'workspace': str(workspace)}
    (tmp_path / 'request.json').write_text(json.dumps(request))
    (tmp_path / 'state.json').write_text('{"status":"accepted"}')
    observed = {}
    class FailingCodex:
        def __init__(self, config): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def login_api_key(self, token):
            observed['token'] = token
            raise RuntimeError('credential echo ' + token + ' ' + settings.api_key)
    monkeypatch.setattr(openai_codex, 'Codex', FailingCodex)
    before = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
    try:
        assert codex_worker.run(tmp_path) == 1
    finally:
        signal.signal(signal.SIGTERM, before[0]); signal.signal(signal.SIGINT, before[1])
    state = (tmp_path / 'state.json').read_text()
    assert settings.api_key not in state and observed['token'] not in state
    assert json.loads(state)['status'] == 'failed' and '[REDACTED]' in state
