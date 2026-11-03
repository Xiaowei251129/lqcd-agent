"""Scientific entry uses the canonical durable engine."""
import json
import pytest
from pathlib import Path
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.strict_json import ControlIntegrityError
from tests.support import command
from tests.test_cli import persisted

def test_scientific_case_uses_canonical_engine(tmp_path):
    config=tmp_path/"case.json"
    config.write_text(json.dumps({"schema_version":"0.1","case_id":"science","source_kind":"synthetic_placeholder","physics_goal":"Exercise mock observables."}))
    result=command("run","--case-config",str(config),"--key","science")
    assert result["run_status"] == "completed"
    root,execution,index=persisted(result)
    assert execution.values[0]["schema_version"]=="0.4"
    for slot,field in [("plan","method_plan_path"),("analysis","run_result_path"),("review","scientific_review_report_path")]:
        pointer=index["current"][slot]
        assert pointer is not None
        value=json.loads(Path(pointer["state_paths"][field]).read_text())
        assert value["domain_result"]
    analysis=json.loads(Path(index["current"]["analysis"]["state_paths"]["run_result_path"]).read_text())["domain_result"]
    assert analysis["run_success"] is True
    assert index['current']['approval'] is None
    terminal = index['current']['terminal']
    assert terminal is not None
    conclusion = json.loads(Path(terminal['state_paths']['memory_update_path']).read_text())
    assert conclusion['scientific_outcome'] in ('supported', 'qualified', 'inconclusive')
    assert conclusion['decision_origin'] == 'system'
    assert conclusion['authorization_decision'] is None
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in execution.values)
    decision=json.loads(Path(index['current']['decision']['state_paths']['decision_log_path']).read_text())
    assert decision['risk_level'] == 'low'

    prefix = parse_ledger(b'\n'.join(execution.records[:-1]) + b'\n')
    before = prefix.canonical
    record = execution.values[-1]
    extended = prefix.append(record)
    assert extended.canonical == execution.canonical
    record['previous_execution_head'] = '0' * 64
    assert prefix.canonical == before and extended.canonical == execution.canonical
    with pytest.raises(ControlIntegrityError):
        prefix.append(record)
    with pytest.raises(ControlIntegrityError):
        parse_ledger(before[:-1])
