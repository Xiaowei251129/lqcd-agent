"""Application credentials, Responses wire contract and bounded SDK lifecycle."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest
from lqcd_agent.settings import ApplicationSettings, child_environment, read_env
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest
from lqcd_agent.llm.openai_client import OpenAIResponsesProvider, LiveProviderError


def provider(reply=None, error=None):
    calls = []
    def create(**options):
        calls.append(options)
        if error:
            raise error
        return reply
    config = LLMProviderConfig('0.1', 'openai', api_base='https://api.openai.com/v1', default_model='gpt-6-luna')
    return OpenAIResponsesProvider(config, api_key='private-test-value', enabled=True,
        client=NS(responses=NS(create=create))), calls


def test_responses_schema_usage_and_no_unsupported_temperature():
    reply = NS(status='completed', output_text='{"ok":true}', model='gpt-6-luna',
               usage=NS(model_dump=lambda: {'total_tokens': 12}))
    p, calls = provider(reply)
    schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False}
    result = p.generate(LLMRequest([{'role':'user','content':'Return JSON'}], 'json_schema', schema, max_tokens=32))
    assert result.usage == {'total_tokens':12} and result.content == '{"ok":true}'
    assert calls == [{'model':'gpt-6-luna', 'input':[{'role':'user','content':'Return JSON'}],
        'max_output_tokens':32, 'store':False, 'text':{'format':{'type':'json_schema','name':'agent_output','schema':schema,'strict':True}}}]


@pytest.mark.parametrize('status,content,code', [('incomplete','partial','response_incomplete'),
    ('failed','','response_incomplete'), ('completed','','response_missing_text')])
def test_responses_rejects_incomplete_and_refusal(status, content, code):
    p, _ = provider(NS(status=status,output_text=content))
    with pytest.raises(LiveProviderError) as failure:
        p.generate(LLMRequest([{'role':'user','content':'JSON'}]))
    assert failure.value.code == code


def test_provider_errors_do_not_persist_credentials():
    from openai import APIConnectionError
    import httpx
    p, _ = provider(error=APIConnectionError(message='private-test-value', request=httpx.Request('POST','https://api.openai.com/v1/responses')))
    with pytest.raises(LiveProviderError) as failure:
        p.generate(LLMRequest([{'role':'user','content':'JSON'}]))
    assert 'private-test-value' not in json.dumps(failure.value.as_error())


def test_application_env_is_private_and_not_inherited(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('OPENAI_API_KEY=private-test-value\nOPENAI_MODEL=gpt-6-luna\n')
    path.chmod(0o600)
    settings = ApplicationSettings.load(path)
    assert settings.api_key == 'private-test-value' and 'private-test-value' not in repr(settings)
    monkeypatch.setenv('OPENAI_API_KEY','personal-test-value')
    monkeypatch.setenv('CODEX_HOME','/personal/codex')
    assert 'OPENAI_API_KEY' not in child_environment() and 'CODEX_HOME' not in child_environment()
    path.chmod(0o644)
    with pytest.raises(ValueError, match='private regular file'):
        read_env(path)
    path.chmod(0o600)
    alias=tmp_path/'alias'; alias.symlink_to(path)
    with pytest.raises(OSError):
        read_env(alias)


def test_sdk_worker_uses_private_auth_and_retains_permissions(tmp_path, monkeypatch):
    from lqcd_agent.code_agent import codex_worker
    import openai_codex
    settings=ApplicationSettings(api_key='private-test-value')
    monkeypatch.setattr(codex_worker.ApplicationSettings, 'load', lambda: settings)
    monkeypatch.setenv('TMPDIR',str(tmp_path))
    workspace=tmp_path/'workspace';workspace.mkdir()
    task={'write_paths':['sample.py'],'requirements':['Return 2'],'acceptance_criteria':['value()==2']}
    (tmp_path/'request.json').write_text(json.dumps({'task':task,'manifest':{},'workspace':str(workspace),'base_files':{}}))
    (tmp_path/'state.json').write_text('{"status":"accepted"}')
    observed={}
    result=NS(status=NS(value='completed',__str__=lambda _: 'completed'),
        final_response=json.dumps({'files':[{'path':'sample.py','content':'def value():\n    return 2\n'}]}),usage=None,items=[])
    class FakeCodex:
        def __init__(self, config): observed['config']=config
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def login_api_key(self,key): observed['key']=key
        def account(self): return NS(account=NS(root=NS(type='apiKey')))
        def thread_start(self, **kwargs):
            observed['thread']=kwargs
            return NS(id='thread', turn=lambda *_,**kw:NS(id='turn',run=lambda:result,interrupt=lambda:None))
    monkeypatch.setattr(openai_codex,'Codex',FakeCodex)
    before=signal.getsignal(signal.SIGTERM),signal.getsignal(signal.SIGINT)
    try:
        assert codex_worker.run(tmp_path)==0
    finally:
        signal.signal(signal.SIGTERM,before[0]);signal.signal(signal.SIGINT,before[1])
    config=observed['config']; overrides=config.config_overrides
    assert observed['key']==settings.api_key and config.codex_bin is None
    assert config.env['CODEX_HOME']==str(tmp_path/'codex-home')
    assert 'cli_auth_credentials_store="ephemeral"' in overrides
    assert 'permissions.lqcd.network.enabled=false' in overrides and 'default_permissions="lqcd"' in overrides
    assert 'features.shell_tool=false' in overrides and 'project_doc_max_bytes=0' in overrides
    assert 'OPENAI_API_KEY' not in config.env and observed['thread']['approval_mode']==openai_codex.ApprovalMode.deny_all
    assert all('private-test-value' not in p.read_text() for p in tmp_path.rglob('*.json'))


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


def test_provider_factory_keeps_dotenv_out_of_process_environment(tmp_path, monkeypatch):
    from lqcd_agent.llm.provider_factory import create_provider_from_config_path
    path=tmp_path/'.env'; path.write_text('OPENAI_API_KEY=private-test-value\nOPENAI_MODEL=gpt-6-luna\n');path.chmod(0o600)
    config=tmp_path/'provider.yaml';config.write_text('schema_version: "0.1"\nprovider: openai\napi_base: https://api.openai.com/v1\n')
    monkeypatch.setenv('OPENAI_API_KEY','personal-test-value')
    p=create_provider_from_config_path(config,env_path=path)
    assert p._credentials()==('private-test-value','gpt-6-luna')
    assert os.environ['OPENAI_API_KEY']=='personal-test-value' and not p.readiness().live_enabled


@pytest.mark.parametrize('source,valid', [('def value(): return 2',True),
    ('import os\ndef value(): return 2',False),('def value(): return 3',False)])
def test_sample_analysis_validates_structure_before_execution(tmp_path, source, valid):
    from lqcd_agent.runtime import SAMPLE_ANALYSIS_COMMAND
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
    (workspace/'sample.py').write_text('def value(): return 1')
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
        assert backend.dispatch(task,manifest,'operation')==receipt and len(calls)==1
        with pytest.raises(ControlIntegrityError,match='Conflicting Codex dispatch'):
            backend.dispatch({**task,'task_digest':digest('different')},manifest,'operation')
        assert backend.cancel('operation','operator_cancel')['status']=='cancelled'
        assert backend.children['operation'].poll() is not None
    finally:
        backend.stop('operation')
