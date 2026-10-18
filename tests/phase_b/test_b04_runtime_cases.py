"""Each B04 publication case has an actual product process and original owner."""
import pytest
import os
from unittest.mock import patch

from helpers.b04_publication_cases import PUBLICATIONS, SPECS, exercise_invocation_case
from helpers.b04_control_cases import PUBLICATIONS as CONTROL_PUBLICATIONS, exercise_control_case
from helpers.b04_process_binding import PROBE_MODE, run_native_case
from harness.pytest_evidence import observe
from harness import pytest_evidence


CASES = tuple(case_id for case_id, spec in SPECS.items() if spec["failpoint_id"] in PUBLICATIONS or spec["failpoint_id"] in CONTROL_PUBLICATIONS)


@pytest.mark.parametrize("case_id", CASES)
def test_independent_case(case_id):
    formal = PROBE_MODE not in os.environ and pytest_evidence.ACTIVE is not None
    if PROBE_MODE not in os.environ and not formal:
        if os.environ.get("LQCD_C26_FULL") == "0.12":
            from helpers.b04_process_binding import run_fault_case
            run_fault_case(case_id)
        else:
            run_native_case(case_id)
        return
    from helpers.b04_fault_sources import SOURCE_MODE
    if formal:
        with patch.dict(os.environ, {SOURCE_MODE: "0.12"}):
            trace = (exercise_invocation_case if SPECS[case_id]["failpoint_id"] in PUBLICATIONS
                     else exercise_control_case)(case_id)
        from harness.pytest_evidence import observe_case
        observe("b04-runtime-" + case_id, {"kind": "boolean", "value": True},
                sorted(SPECS[case_id]["invariants"]), trace)
        observe_case(case_id, SPECS[case_id]["outcome"], sorted(SPECS[case_id]["invariants"]), trace)
        if case_id == "artifact.projection_publication.after.committed_result_replay":
            observe("B04-PUBLICATION", {"kind": "boolean", "value": True},
                    sorted(SPECS[case_id]["invariants"]), trace)
        return
    assert os.environ[PROBE_MODE] == case_id
    if SPECS[case_id]["failpoint_id"] in PUBLICATIONS:
        trace = exercise_invocation_case(case_id)
    else:
        trace = exercise_control_case(case_id)
    if SOURCE_MODE in os.environ:
        from harness.pytest_evidence import observe_case
        observe("B00C26-PROBE", {"kind": "boolean", "value": True}, sorted(SPECS[case_id]["invariants"]), trace)
        if os.environ.get("LQCD_C26_LOCAL_CONSUMERS") == case_id:
            observe_case(case_id, SPECS[case_id]["outcome"], sorted(SPECS[case_id]["invariants"]), trace)
    else:
        observe("B00C25-PROBE", {"kind": "boolean", "value": True}, sorted(SPECS[case_id]["invariants"]), trace)
