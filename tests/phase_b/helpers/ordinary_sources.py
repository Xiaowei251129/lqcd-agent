"""Passive C10 boundary observations; these bytes grant no runtime authority."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads


def captured_source(profile, value):
    raw = canonical_bytes(value)
    return {"schema_version": "0.1", "profile": profile, "sha256": sha256(raw).hexdigest(), "content": raw.decode()}


class OrdinarySources:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.calls = []

    def begin(self, capability_id, input_value, config_value, *, profile):
        authorization = deepcopy(InvocationLeases(self.coordinator).get(capability_id)[1]["authorization"])
        identity = authorization["identity"]
        root = self.coordinator.root / identity["case_id"] / identity["run_id"]
        records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        reservation = records[-1]
        assert reservation["event"] == "resource_reserved"
        assert reservation["payload"]["resource_operation_id"].startswith(capability_id + ":")
        assert reservation["payload"]["input_digest"] == digest(input_value)
        assert reservation["payload"]["config_digest"] == digest(config_value)
        row = {"schema_version": "0.1", "profile": profile, "reservation_head": digest(reservation),
               "capability_id": capability_id, "authorization": authorization,
               "producer": deepcopy(self.coordinator.get(authorization["producer_operation_id"])),
               "input": captured_source("input", deepcopy(input_value)),
               "config": captured_source("config", deepcopy(config_value)),
               "outcome": None, "exception": None}
        self.calls.append(row)
        return row

    def invoke(self, capability_id, input_value, config_value, effect, *, profile="primitive"):
        row = self.begin(capability_id, input_value, config_value, profile=profile)
        try:
            result = effect()
        except BaseException as error:
            row["exception"] = {"type": type(error).__name__, "message": str(error)}
            raise
        row["outcome"] = captured_source("outcome", deepcopy(result))
        return result

    def resource(self, port, *, input_value, config_value, resource_kind, resource_id, timeout_seconds, effect):
        return port.run_resource(resource_kind=resource_kind, resource_id=resource_id,
            input_digest=digest(input_value), config_digest=digest(config_value), timeout_seconds=timeout_seconds,
            effect=lambda: self.invoke(port.capability_id, input_value, config_value, effect))

    def agent(self, delegate):
        captured = self

        class Agent:
            def run(self, node, context, *, timeout_seconds):
                caps = [(row[0], loads(row[1])) for row in captured.coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")]
                selected = [(key, value) for key, value in caps if value["authorization"]["identity"] ==
                            {k: context["identity"][k] for k in ("case_id", "run_id", "attempt_id", "attempt_kind")}]
                assert len(selected) == 1
                capability_id = selected[0][0]
                return captured.invoke(capability_id, context, {"node": node, "structured_output": True},
                    lambda: delegate.run(node, context, timeout_seconds=timeout_seconds), profile="scoped_llm")

        return Agent()

    def finish(self, trace):
        proof = trace["proof"]
        proof.update(schema_version="0.3", ordinary_calls=deepcopy(self.calls), ordinary_members=[])
        registered = [row for row in proof["objects"] if row["kind"] == "canonical_json" and
                      row["value"].get("event") == "registered" and row["value"].get("slot") != "code"]
        registered.extend(row for row in proof["objects"] if row["kind"] == "canonical_json" and
                          row["value"].get("event") == "protected_snapshot_registered" and
                          row["value"].get("protected_kind") == "human_response")
        for row in registered:
            value = row["value"]
            root = next(Path(item["path"]) for item in proof["output_roots"] if
                        (item["case_id"], item["run_id"]) == (value["case_id"], value["run_id"]))
            for member in value["members"]:
                raw = (root / member["canonical_path"]).read_bytes()
                assert sha256(raw).hexdigest() == member["sha256"] and len(raw) == member["size_bytes"]
                proof["ordinary_members"].append({"schema_version": "0.1", "registration_head": row["sha256"],
                    "member": member["logical_name"], "sha256": member["sha256"], "content": raw.decode()})
        return trace
