"""Portable evidence integrity, lifecycle admission and non-executing validation."""
from hashlib import sha256
import zipfile
import pytest
from lqcd_agent.archive import archive_run, verify_archive
from lqcd_agent.control.strict_json import ControlIntegrityError
from lqcd_agent.inspection import host_root
from tests.support import command
from tests.test_cli import arguments


def test_closed_archive_is_exact_idempotent_and_never_changes_source(tmp_path):
    result = command('start', '--key', 'archive')
    root = host_root(result['host'])
    before = {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    archived = command('archive', *arguments(result))
    assert command('archive', *arguments(result)) == archived
    verified = command('verify-archive', '--archive-path', archived['archive'])
    assert verified['valid'] and verified['sha256'] == archived['sha256']
    assert verified['execution_head'] == result['execution_head']
    assert before == {name:sha256((root/name).read_bytes()).hexdigest() for name in before}
    with zipfile.ZipFile(archived['archive']) as bundle:
        assert not any('.sqlite' in name or '.env' in name or 'auth.json' in name for name in bundle.namelist())
        members = [(info,bundle.read(info.filename)) for info in bundle.infolist()]
    tampered = tmp_path/'tampered.zip'
    with zipfile.ZipFile(tampered,'w') as bundle:
        for info,raw in members:
            bundle.writestr(info, raw+b'!' if info.filename == 'run/root_goal.json' else raw)
    with pytest.raises(ControlIntegrityError, match='digest mismatch'):
        verify_archive(tampered)


def test_scientific_archive_requires_closure_and_retains_hash_bound_domain(tmp_path, monkeypatch):
    import json
    case = tmp_path/'case.json'
    case.write_text(json.dumps({'schema_version':'0.1','case_id':'archive_science',
        'source_kind':'synthetic_placeholder','physics_goal':'Inspect mock scientific evidence.'}))
    from lqcd_agent.runtime import ApplicationRequest, advance, submit
    from tests.support import own
    admitted = submit(ApplicationRequest('run', case_config=str(case), key='archive-science')).status
    root = own(host_root(admitted['host']))
    assert admitted['run_status'] == 'running'
    with pytest.raises(ControlIntegrityError, match='Only a terminated Run'):
        archive_run(root, admitted['run_locator'])
    assert not (root/'archives').exists()
    closed = advance(admitted['host'], admitted['run_locator'])
    assert closed['run_status'] == 'completed' and closed['active_pause'] is None
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(tmp_path/'missing-workspace'))
    archived = archive_run(root, closed['run_locator'])
    assert verify_archive(archived['archive'])['valid']
    with zipfile.ZipFile(archived['archive']) as bundle:
        assert any(name.startswith('domain/') and name.endswith('run_result.json') for name in bundle.namelist())
    domain = next((root/'domain').rglob('run_result.json'))
    domain.write_bytes(domain.read_bytes()+b' ')
    with pytest.raises(ControlIntegrityError, match='Scientific archive source changed'):
        archive_run(root, closed['run_locator'])


@pytest.mark.parametrize('name,mode', [('../escape',0o100600),('/absolute',0o100600),('x\\y',0o100600),('link',0o120777)])
def test_verifier_rejects_traversal_and_symlink_members(tmp_path,name,mode):
    path=tmp_path/'unsafe.zip'
    with zipfile.ZipFile(path,'w') as bundle:
        info=zipfile.ZipInfo(name);info.create_system=3;info.external_attr=mode<<16
        bundle.writestr(info,b'unsafe')
    with pytest.raises(ControlIntegrityError):
        verify_archive(path)
    assert not (tmp_path/'escape').exists()
