"""Ledger entry points preserve strict input checks and detached snapshots."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json

import pytest

from lqcd_agent.control.execution import ExecutionReplay, append_record_bytes, parse_ledger, replay
from lqcd_agent.control.records import validate_record
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes
from test_execution_0_4_foundation import bootstrap


def test_replay_snapshots_are_detached_from_inputs_and_each_other():
    records = bootstrap().records
    expected = b"".join(canonical_bytes(row) + b"\n" for row in records)
    execution = replay(records)
    projection = execution.projection.canonical
    first, second = execution.values, execution.values
    assert first == second == records and first is not second
    assert first[0] is not second[0] and first[0]["created_at"] is not second[0]["created_at"]
    records[0]["created_at"]["wall_seconds"] += 1
    first[0]["root_goal_reference"]["sha256"] = "f" * 64
    second.pop()
    assert b"\n".join(execution.records) + b"\n" == expected
    assert execution.values == [json.loads(line) for line in expected.splitlines()]
    assert execution.projection.canonical == projection
    with pytest.raises(FrozenInstanceError):
        execution.records = ()


def test_parse_replay_and_append_preserve_exact_canonical_bytes():
    records = bootstrap().records
    expected = b"".join(canonical_bytes(row) + b"\n" for row in records)
    parsed, direct = parse_ledger(expected), replay(tuple(records))
    assert parsed.records == direct.records
    assert parsed.projection.canonical == direct.projection.canonical
    assert parsed.values == direct.values == records
    encoded = b""
    for row in records:
        encoded = append_record_bytes(encoded, row)
    assert encoded == expected


@pytest.mark.parametrize("raw", [b"", b"\n", b"{}", b"{}\n\n", b'{"x":1,"x":2}\n',
    b'{"x":NaN}\n', b'{"x":Infinity}\n', b'{"x":9007199254740992}\n', b'{ "x":1}\n',
    b'null\n', b'[]\n', b'"text"\n', b'\xff\n'])
def test_external_ledger_bytes_remain_strict(raw):
    with pytest.raises(ControlIntegrityError):
        parse_ledger(raw)


@pytest.mark.parametrize("fault", ["schema", "field", "type", "chain", "identity", "clock", "payload"])
def test_replay_rejects_tampering_without_mutating_input(fault):
    records = bootstrap().records
    if fault == "schema": records[0]["schema_version"] = "0.3"
    elif fault == "field": records[0]["unexpected"] = True
    elif fault == "type": records[0]["event_index"] = True
    elif fault == "chain": records[-1]["previous_execution_head"] = "f" * 64
    elif fault == "identity": records[-1]["run_id"] = "foreign"
    elif fault == "clock": records[-1]["created_at"]["monotonic_seconds"] = -1
    else: records[1]["payload"]["policy"]["limits"]["cycles_per_run"] += 1
    before = deepcopy(records)
    with pytest.raises(ControlIntegrityError):
        replay(records)
    assert records == before


def test_direct_snapshot_values_still_validate_untrusted_record_bytes():
    execution = replay(bootstrap().records)
    changed = execution.values[0]
    changed["schema_version"] = "0.3"
    for raw in (canonical_bytes(changed), b'{"x":1,"x":2}', b'{"x":NaN}'):
        with pytest.raises(ControlIntegrityError):
            ExecutionReplay((raw,), execution.projection).values
    with pytest.raises(ControlIntegrityError):
        validate_record(changed)


def test_append_revalidates_a_changed_prefix():
    records = bootstrap().records
    prefix = b"".join(canonical_bytes(row) + b"\n" for row in records[:-1])
    assert append_record_bytes(prefix, records[-1]) == b"".join(canonical_bytes(row) + b"\n" for row in records)
    for changed in (prefix[:-1], prefix.replace(b'"run_id":"run"', b'"run_id":"foreign"', 1)):
        with pytest.raises(ControlIntegrityError):
            append_record_bytes(changed, records[-1])
