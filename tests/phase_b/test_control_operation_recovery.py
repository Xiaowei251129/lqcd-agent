"""B02 execution diagnostics; these are not acceptance-matrix passing evidence."""
from pathlib import Path
import tempfile

from lqcd_agent.artifacts.registry import ARTIFACT_SLOTS
from lqcd_agent.control.execution import replay
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.projections import attach_checkpoint, bounded_projection, checkpoint_manifest
from lqcd_agent.control.strict_json import canonical_bytes
from harness.trace import compare, event, normalize
from harness.strict_json import Invalid
from test_execution_0_4_foundation import bootstrap, DIGEST, POLICY


def validated_fresh_root():
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-trace-", dir="/private/tmp"))
    ledger = bootstrap(root)
    execution = replay(ledger.records)
    index = {"schema_version": "0.1", "run_id": "run", "case_id": "case", "revision": 0, "last_event_id": None,
             "current": {slot: None for slot in ARTIFACT_SLOTS}, "managed_projections": {},
             "execution_head": execution.projection.value["execution_head"], "artifact_head": None}
    core = bounded_projection(execution, artifact_index=index, artifact_head=None, artifact_event_index=0)
    manifest = checkpoint_manifest(execution, artifact_head=None, artifact_event_index=0, checkpoint_id="checkpoint_1",
                                   checkpoint_digest=DIGEST, state_digest=core.digest).value
    projection = attach_checkpoint(core, execution, manifest).value
    (root / "execution_history.jsonl").write_bytes(b"\n".join(execution.records) + b"\n")
    (root / "artifact_history.jsonl").write_bytes(b"")
    (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    (root / "budget_policy.json").write_bytes(canonical_bytes(POLICY))
    validate_run_root(root, manifest=manifest, projection=projection)
    return root, ledger, projection


def test_fresh_root_changes_digest_after_current_trace_normalization():
    """Reproduce the unresolved raw-digest/ephemeral-root acceptance boundary."""
    import pytest

    roots = [validated_fresh_root(), validated_fresh_root()]
    assert roots[0][0] != roots[1][0]
    assert roots[0][1].records[0]["created_at"] == roots[1][1].records[0]["created_at"]
    traces = [{"schema_version": "0.1", "events": [event(
        "bootstrap_validated", run_id=value["run_id"], execution_head=value["execution_head"],
        checkpoint_head=value["checkpoint_head"], ephemeral={"output_root": str(root)})]}
        for root, _, value in roots]
    assert normalize(traces[0]) != normalize(traces[1])
    with pytest.raises(Invalid, match="invalid_evidence:trace:exact"):
        compare(traces[0], traces[1])


def test_source_bound_trace_resolves_fresh_root_diagnostic():
    """B00C01 fixes the evidence prerequisite, not B02 durable execution."""
    from harness.contracts import ROOT
    from harness.strict_json import read
    from helpers.trace_sources import current_binding, fresh_trace

    expected = read(ROOT / "tests/phase_b/expected_traces/trace_source_bound.json")
    for trace in (fresh_trace(), fresh_trace(time_offset=500)):
        compare(trace, expected, binding=current_binding())
