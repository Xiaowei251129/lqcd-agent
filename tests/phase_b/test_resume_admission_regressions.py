"""Resume rejects changed admission facts without acquiring mutation authority."""
from dataclasses import replace

import pytest

from helpers.runtime_cases import run_files
from helpers.supplemental_cases import rows
from lqcd_agent.control.interfaces import ActorContext
from lqcd_agent.control.pause import CancelPauseRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from test_pause_control import control
from test_snapshot_loss_control import requests


@pytest.mark.parametrize("mutation", ["actor", "scope", "run", "pause", "payload_digest", "reason", "prepared", "terminal"])
def test_resume_admission_mismatch_preserves_all_authority(control, mutation):
    coordinator, plane, actor, locator = control
    inputs = requests(locator)
    if mutation == "prepared":
        def stop(name, side, value):
            if (name, side) == ("control.publish_pause.not_applicable.pause_opened_recorded", "before"):
                raise RuntimeError("prepared-only source")
        coordinator.observer = stop
        with pytest.raises(RuntimeError, match="prepared-only"):
            plane.publish_pause(inputs["publish"], actor=actor)
        coordinator.observer = None
    else:
        plane.publish_pause(inputs["publish"], actor=actor)
    request = inputs["resume"]
    if mutation == "actor":
        actor = ActorContext("operator", "agent", ("resume",))
    elif mutation == "scope":
        actor = ActorContext("operator", "human", ())
    elif mutation == "run":
        request = replace(request, run_locator={**locator, "run_id": "unknown"})
    elif mutation == "pause":
        request = replace(request, pause_id="pause_000002")
    elif mutation == "payload_digest":
        request = replace(request, input_digest="0" * 64)
    elif mutation == "reason":
        payload = {"producer_operation_id": "producer", "external_final_digest": "0" * 64}
        request = replace(request, input_kind="external_result", input_snapshot=payload, input_digest=digest(payload))
    elif mutation == "terminal":
        plane.cancel_pause(CancelPauseRequest(locator, "pause_000001", "cancel", "operator_cancel"), actor=actor)
    before, files = rows(coordinator), run_files(coordinator.root)
    for _ in range(2):
        with pytest.raises(ControlIntegrityError):
            plane.resume_run(request, actor=actor)
        assert rows(coordinator) == before and run_files(coordinator.root) == files
