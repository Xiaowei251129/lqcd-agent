"""Build provenance and CI evidence must not depend on private runtime details."""
import json
import ast
import os
import re
import yaml
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from scripts import check


def test_ci_evidence_keeps_outcomes_without_runtime_or_failure_content(tmp_path):
    secret = 'private-runtime-value'
    report = {'mode': 'integration', 'passed': False, 'selected': 1,
              'source_sha256': 'a' * 64, 'elapsed_seconds': 2.5,
              'root': '/private/' + secret, 'error': secret, 'selection': [secret]}
    row = ET.fromstring('<testcase name="case" classname="suite" time="1.5" file="private">'
                        '<failure message="private">private</failure>'
                        '<system-out>private</system-out></testcase>')
    row.find('failure').text = secret
    check.write_ci_evidence(tmp_path, report, [row])
    summary = json.loads((tmp_path/'ci-summary.json').read_text())
    assert summary['passed'] is False and summary['source_sha256'] == 'a' * 64
    assert not {'root', 'error', 'selection'} & summary.keys()
    public = ET.parse(tmp_path/'ci-junit.xml').find('testcase')
    assert public.attrib == {'name': 'case', 'classname': 'suite', 'time': '1.5'}
    assert public.find('failure') is not None and public.find('system-out') is None
    assert secret not in (tmp_path/'ci-summary.json').read_text() + (tmp_path/'ci-junit.xml').read_text()


def test_build_and_ci_inputs_participate_in_source_identity(tmp_path, monkeypatch):
    for name in ('pyproject.toml', 'requirements.lock', 'setup.py', 'MANIFEST.in', '.github/workflows/check.yml'):
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('original')
    monkeypatch.setattr(check, 'ROOT', tmp_path)
    previous = check.identity()
    metadata = tmp_path/'src/.DS_Store'
    metadata.parent.mkdir()
    for content in (b'finder-view-state', b'updated-finder-view-state'):
        metadata.write_bytes(content)
        assert check.identity() == previous
    for name in ('setup.py', 'MANIFEST.in', '.github/workflows/check.yml'):
        (tmp_path/name).write_text('changed')
        current = check.identity()
        assert current != previous
        previous = current


def test_pure_contracts_and_numerical_kernel_need_no_authority_or_site_packages(tmp_path):
    source = Path(__file__).resolve().parents[1]/'src'
    script = f'''
import sys
sys.path.insert(0, {str(source)!r})
from lqcd_agent.control.identity import stable_attempt_id, stable_cycle_id, canonical_attempt_kind
from lqcd_agent.control.lifecycle import validate_execution_index_sequence
from lqcd_agent.artifacts.contracts import STATE_FIELDS_BY_SLOT, slots_for_target
from lqcd_agent.benchmark import run_benchmark
assert stable_attempt_id(1) == 'attempt_000001' and stable_cycle_id(1) == 'cycle_0001'
assert canonical_attempt_kind('human_approval_gate') == 'human_gate'
assert len(STATE_FIELDS_BY_SLOT['code']) == 4
assert slots_for_target('memory_report', new_human_request=False) == ('terminal',)
for identities in ([('attempt_000001', True)], [('attempt_000001', 1), ('attempt_000003', 3)],
                   [('attempt_000001', 1), ('attempt_000001', 1)]):
    try:
        validate_execution_index_sequence(identities, label='attempt', prefix='attempt')
    except ValueError:
        pass
    else:
        raise AssertionError('Malformed lifecycle identities were accepted')
assert run_benchmark()['passed']
assert not {{'lqcd_agent.control.storage', 'lqcd_agent.control.coordinator',
             'lqcd_agent.artifacts.registry', 'lqcd_agent.graph.state', 'langgraph'}} & sys.modules.keys()
'''
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', script], capture_output=True,
        text=True, timeout=15, env={'PATH': os.defpath, 'TMPDIR': str(tmp_path/'unavailable')})
    assert result.returncode == 0, result.stderr


def test_control_contract_consumers_do_not_depend_on_graph_modules():
    source = Path(__file__).resolve().parents[1]/'src'
    violations = []
    for path in (source/'lqcd_agent/control').glob('*.py'):
        parent = list(path.relative_to(source).parent.parts)
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.ImportFrom):
                modules = ['.'.join(parent[:len(parent)-node.level+1] + [node.module or ''])
                           if node.level else node.module or '']
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            if any(module == 'lqcd_agent.graph' or module.startswith('lqcd_agent.graph.') for module in modules):
                violations.append((str(path), node.lineno))
    assert not violations


def test_workflow_job_environment_uses_only_pre_runner_contexts():
    source = Path(__file__).resolve().parents[1]/'.github/workflows/check.yml'
    workflow = yaml.load(source.read_text(), Loader=yaml.BaseLoader)
    allowed = {'github', 'needs', 'strategy', 'matrix', 'vars', 'secrets', 'inputs'}
    for job in workflow['jobs'].values():
        for value in job.get('env', {}).values():
            contexts = re.findall(r'\$\{\{\s*([a-zA-Z_]+)\.', value)
            assert set(contexts) <= allowed
