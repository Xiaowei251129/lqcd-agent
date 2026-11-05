"""Validate the actual installed wheel and the operator-owned workspace boundary."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import venv
import zipfile

from lqcd_agent.settings import ApplicationSettings, child_environment, workspace_root


def test_operator_workspace_is_independent_of_installation_and_child_cwd(tmp_path, monkeypatch):
    root = tmp_path/'workspace'; root.mkdir()
    (root/'.env').write_text('OPENAI_API_KEY=private-test-value\n')
    (root/'.env').chmod(0o600)
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(root))
    monkeypatch.chdir(tmp_path)
    assert workspace_root() == root
    assert ApplicationSettings.load().api_key == 'private-test-value'
    assert child_environment()['LQCD_AGENT_WORKSPACE'] == str(root)
    assert 'private-test-value' not in json.dumps(child_environment())


def test_wheel_installs_and_runs_outside_source(tmp_path):
    source = Path(__file__).resolve().parents[1]
    build = tmp_path/'build'; build.mkdir()
    for name in ('pyproject.toml', 'setup.py', 'MANIFEST.in', 'README.md'):
        shutil.copyfile(source/name, build/name)
    for name in ('src', 'scripts'):
        shutil.copytree(source/name, build/name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.egg-info'))
    (build/'src/lqcd_agent/_build_manifest.json').write_text('{}')
    result = subprocess.run([sys.executable, '-B', '-c',
        'from setuptools.build_meta import build_wheel; build_wheel("wheels")'],
        cwd=build, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    wheel, = (build/'wheels').glob('*.whl')
    with zipfile.ZipFile(wheel) as bundle:
        manifest = json.loads(bundle.read('lqcd_agent/_build_manifest.json'))
        assert manifest['application_build']
        protocol = bundle.read('lqcd_agent/control/protocol.json')
        assert manifest['sources']['control/protocol.json'] == hashlib.sha256(protocol).hexdigest()
        assert all('lqcd_agent/workbench/static/'+name in bundle.namelist() for name in ('index.html','app.js','style.css'))
        entrypoints = bundle.read(next(name for name in bundle.namelist() if name.endswith('/entry_points.txt'))).decode()
        assert 'lqcd-agent-workbench = lqcd_agent.workbench.server:main' in entrypoints
        assert not any(n.startswith(('check-results/', '.env', 'raw_data/')) for n in bundle.namelist())
    environment = tmp_path/'environment'
    venv.EnvBuilder(with_pip=True).create(environment)
    python = str(environment/'bin/python')
    subprocess.run([python, '-m', 'pip', 'install', '--no-deps', '--no-index', str(wheel)],
                   capture_output=True, check=True, timeout=60)
    workspace = tmp_path/'workspace'; workspace.mkdir()
    # Reuse only locked third-party dependencies, not the editable application.
    env = {**os.environ, 'PYTHONPATH': sysconfig.get_path('purelib'), 'LQCD_AGENT_WORKSPACE': str(workspace)}
    check = subprocess.run([python, '-B', '-c',
        'import lqcd_agent,sys; assert lqcd_agent.__file__.startswith(sys.prefix); '
        'from lqcd_agent.cli import main; raise SystemExit(main(["doctor"]))'],
        cwd=workspace, env=env, capture_output=True, text=True, timeout=60)
    assert check.returncode == 0, check.stderr
    report = json.loads(check.stdout)
    assert report['passed'] and report['workspace'] == str(workspace)
    assert report['platform'] == 'Darwin' and report['scratch_parent'] == '/private/tmp'
    assert report['pragmas'] == {'journal_mode': 'wal', 'synchronous': 2, 'foreign_keys': 1}
    assert not report['live_api_called']

    (workspace/'case.json').write_text(json.dumps({'schema_version':'0.1', 'case_id':'wheel',
        'physics_goal':'Inspect installed capabilities.', 'source_kind':'synthetic_placeholder'}))
    run = subprocess.run([python, '-B', '-m', 'lqcd_agent', 'run', '--case-config', 'case.json', '--key', 'wheel'],
        cwd=workspace, env=env, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result['run_status'] == 'completed' and result['next_action'] == 'archive'
    assert result['active_pause'] is None
    from lqcd_agent.inspection import host_root
    from tests.support import own
    host = own(host_root(result['host']))
    locator = result['run_locator']
    index = json.loads((host/locator['case_id']/locator['run_id']/'artifact_index.json').read_text())
    terminal = json.loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_text())
    assert terminal['decision_origin'] == 'system' and terminal['authorization_decision'] is None
    assert index['current']['approval'] is None
    assert not (host/'example_repository').exists()
    assert not (host/'code_workspaces').exists()
