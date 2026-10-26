"""Scientific reuse binds both the registered result and its workspace members."""
import hashlib
import json
import pytest
from lqcd_agent.science import ScientificAgent
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes


def test_changed_scientific_member_is_rejected(tmp_path):
    member = tmp_path / 'domain' / 'result.json'
    member.parent.mkdir()
    member.write_bytes(b'{"mass":1}')
    root = tmp_path / 'case' / 'run'
    artifact = root / 'attempts' / 'attempt_000001' / 'run_result.json'
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(canonical_bytes({'domain_result': {'member_digests': {'domain/result.json': hashlib.sha256(member.read_bytes()).hexdigest()}}}))
    context = {'identity': {'case_id': 'case', 'run_id': 'run'}, 'current_evidence': [
        {'member': str(artifact.relative_to(root)), 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}]}
    agent = ScientificAgent(tmp_path, {})
    assert agent._artifact(context, 'run_result.json')['domain_result']
    member.write_bytes(b'{"mass":9}')
    with pytest.raises(ControlIntegrityError, match='Scientific workspace member changed'):
        agent._artifact(context, 'run_result.json')
