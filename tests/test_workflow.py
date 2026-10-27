"""Scientific entry uses the canonical durable engine."""
import json
from pathlib import Path
from tests.support import command
from tests.test_cli import persisted

def test_scientific_case_uses_canonical_engine(tmp_path):
    config=tmp_path/"case.json"
    config.write_text(json.dumps({"schema_version":"0.1","case_id":"science","source_kind":"synthetic_placeholder","physics_goal":"Exercise mock observables."}))
    result=command("run","--case-config",str(config),"--key","science")
    assert result["run_status"] == "paused"
    root,execution,index=persisted(result)
    assert execution.values[0]["schema_version"]=="0.4"
    for slot,field in [("plan","method_plan_path"),("analysis","run_result_path"),("review","scientific_review_report_path")]:
        pointer=index["current"][slot]
        assert pointer is not None
        value=json.loads(Path(pointer["state_paths"][field]).read_text())
        assert value["domain_result"]
    analysis=json.loads(Path(index["current"]["analysis"]["state_paths"]["run_result_path"]).read_text())["domain_result"]
    assert analysis["run_success"] is True
    assert index['current']['approval']['status'] == 'pending'
    assert index['current']['terminal'] is None
    decision=json.loads(Path(index['current']['decision']['state_paths']['decision_log_path']).read_text())
    assert decision['risk_level'] == 'high'
