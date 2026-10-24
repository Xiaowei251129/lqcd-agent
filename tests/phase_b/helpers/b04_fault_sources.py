"""Opt-in native preflight for the frozen B04 fault-source capture contract."""
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from functools import wraps
from pathlib import Path
import inspect
import os

from harness import pytest_evidence
from harness.strict_json import keys, read, require, write_new
from harness.trace import normalize
from harness.fault_source_trace import anchor_directory, capture_snapshot, exclusive, source_roots, save_evidence
from harness.strict_json import canonical, sha
from helpers.b04_process_binding import nodeid
from helpers.trace_sources import current_binding
from helpers.host_identity_fixture import HostIdentities
from lqcd_agent.control.strict_json import loads


SOURCE_MODE = "LQCD_C26_FAULT_SOURCE"


def before_fault(coordinator, output, request, process, raw, collector):
    """Validate S0 eligibility before introducing the new snapshot resolver."""
    if SOURCE_MODE not in os.environ:
        return
    version = "0.13" if request.get("schema_version") == "0.2" else "0.12"
    require(os.environ[SOURCE_MODE] == version, "fault_capture", "explicit_version")
    writer = pytest_evidence.ACTIVE
    binding = current_binding()
    require(writer is not None and writer.nodeid == nodeid(request["case_id"]) and
            request["nodeid"] == writer.nodeid and binding["invocation_token"] != "unit-only-not-acceptance",
            "fault_capture", "native_node")
    require(request["process_token"] in pytest_evidence.CONSUMED_PROCESS_RECEIPTS and
            process.exitcode == 97 and not process.is_alive(), "fault_capture", "consumed_child")
    receipt = read(Path(request["receipt_path"]))
    source = loads((coordinator.root / "process-source.json").read_bytes())
    keys(receipt, {"request", "process_id", "hook_ref"}, "fault_receipt")
    require(receipt["request"] == request and receipt["process_id"] == source["process_id"] == process.pid and
            receipt["hook_ref"] == request["hook_ref"] and source["binding"] == binding and
            source["case_id"] == request["case_id"], "fault_capture", "original_source")
    require(raw["schema_version"] == "0.10" and raw["proof"]["schema_version"] == "0.7",
            "fault_capture", "original_version")
    registered = {(row["value"].get("case_id"), row["value"].get("run_id"), row["value"].get("attempt_id"))
                  for row in raw["proof"]["objects"] if row["value"].get("event") == "registered" and
                  row["value"].get("slot") == "code"}
    unconsumed = []
    for (stored,) in coordinator.connection.execute("SELECT value FROM external_operations"):
        producer = loads(stored)
        identity = producer["run_locator"]["case_id"], producer["run_locator"]["run_id"], producer["attempt_id"]
        if producer["terminal_evidence_digest"] is not None and producer["consumption_release"] is None and identity not in registered:
            unconsumed.append(producer["producer_operation_id"])
    require(not unconsumed, "fault_capture", "nonempty_unconsumed_requires_original_collector")
    candidate = deepcopy(raw)
    candidate["schema_version"] = "0.11"
    candidate["proof"].update(schema_version="0.8", unconsumed_code_sources=[])
    normalized = normalize(candidate, binding=binding)
    from helpers.b04_process_binding import PROBE_MODE
    name = ("c26-s0-eligibility.json" if PROBE_MODE in os.environ
            else "b04-s0-" + sha(request["case_id"].encode()) + ".json")
    if version == "0.13":
        name = "b04-s0-" + request["pytest_request"]["sha256"] + "-" + sha(request["case_id"].encode()) + ".json"
    destination = writer.output.parent / name
    write_new(destination, {"case_id": request["case_id"], "binding": binding,
                           "source_root": str(coordinator.root), "output": str(output),
                           "request": request, "raw": candidate, "normalized": normalized,
                           "unconsumed_proven_empty": True})
    return NativeCapture(coordinator, output, request, process, candidate, collector)


class NativeCapture:
    """Retain actual stage bytes outside every original production source tree."""

    def __init__(self, coordinator, output, request, process, raw, collector):
        self.coordinator, self.collector = coordinator, collector
        self.initial_event_count = len(collector.events)
        self.durable_initial_phases = {(row["operation_id"], row["phase_revision"], row["lease_epoch"])
            for row in raw["events"] if row["event"].startswith("control.")}
        self.request, self.raw = deepcopy(request), deepcopy(raw)
        self.binding = current_binding()
        self.pytest_request = request.get("pytest_request")
        self.directory = anchor_directory(self.binding, request["case_id"], pytest_request=self.pytest_request)
        self.directory.parent.mkdir(parents=True, exist_ok=True)
        self.directory.mkdir()
        self.records, self.manifests, self.calls, self.contenders = [], [], [], []
        self.identities = HostIdentities("b00c27-parent-recovery:" + request["case_id"])
        source = (coordinator.root / "process-source.json").read_bytes()
        original = loads(source)
        self.roots = source_roots(raw, original)
        if "operation_id" in original:
            producer = {"kind": "control", "value": coordinator.get(original["operation_id"])}
        else:
            row, = [(key, revision, loads(value)) for key, revision, value in coordinator.connection.execute(
                "SELECT capability_id,revision,value FROM invocation_capabilities") if loads(value)["state"] == "started"]
            producer = {"kind": "invocation", "capability_id": row[0], "revision": row[1], "value": row[2],
                        "operation": coordinator.get(row[2]["authorization"]["producer_operation_id"])}
        files = {"request.json": canonical(request), "receipt.json": Path(request["receipt_path"]).read_bytes(),
                 "process-source.json": source, "before-raw.json": canonical(raw),
                 "original-before-raw.json": (Path(output) / "before-raw.json").read_bytes()}
        if self.pytest_request is not None:
            files["pytest-request.json"] = Path(self.pytest_request["path"]).read_bytes()
        for name, content in files.items():
            save_evidence(self.directory, name, content)
        self.common = {"schema_version": "0.1", "binding": self.binding, "case_id": request["case_id"],
            "nodeid": request["nodeid"], "collector_pid": os.getpid(), "child_pid": process.pid,
            "process_request_sha256": sha(files["request.json"]), "process_receipt_sha256": sha(files["receipt.json"]),
            "process_source_sha256": sha(source), "producer": producer}
        self.stage("S0", {"raw_sha256": sha(files["before-raw.json"]), "validated_version": "0.11"})

    def stage(self, name, observation):
        require(name == ("S0", "S1", "S2", "S3")[len(self.records)], "fault_capture", "stage_order")
        observation = {**observation, "source": self.post_source(name)} if name != "S0" else observation
        observation["host_identities"] = self.identity_state()
        snapshot, manifest = capture_snapshot(self.directory, name, self.roots, self.request)
        previous = None if not self.records else sha((self.directory / (("S0", "S1", "S2")[len(self.records) - 1] + ".json")).read_bytes())
        record = {**self.common, "stage": name, "previous_stage_sha256": previous,
                  "snapshot": snapshot, "observation": deepcopy(observation)}
        exclusive(self.directory / (name + ".json"), canonical(record))
        self.records.append(record)
        self.manifests.append(manifest)

    def post_source(self, stage):
        candidate = None
        try:
            from helpers.control_traces import ControlTrace
            # Reject unreadable original indexes before the prefix collector
            # writes a derived snapshot from those invalid source bytes.
            producer = self.common["producer"]
            locator = producer["value"]["request"]["run_locator"] if producer["kind"] == "control" else (
                producer["value"]["authorization"]["identity"])
            loads((self.coordinator.root / locator["case_id"] / locator["run_id"] / "artifact_index.json").read_bytes())
            captured = ControlTrace(self.collector.output, version="0.10", ordinary_sources=self.collector.ordinary_sources)
            # S0 already proved which child callbacks survived transaction rollback.
            # Later takeover must not reinterpret a rolled-back callback at the
            # same revision as an observation of the new owner's committed phase.
            captured.events = deepcopy([row for position, row in enumerate(self.collector.events)
                if position >= self.initial_event_count or not row["event"].startswith("control.") or
                (row["operation_id"], row["phase_revision"], row["lease_epoch"]) in self.durable_initial_phases])
            captured.observed_records = set(self.collector.observed_records)
            candidate = deepcopy(captured.finish(self.coordinator))
            require(candidate["schema_version"] == "0.10" and candidate["proof"]["schema_version"] == "0.7",
                    "fault_capture", "post_source_version")
            registered = {(row["value"].get("case_id"), row["value"].get("run_id"), row["value"].get("attempt_id"))
                          for row in candidate["proof"]["objects"] if row["value"].get("event") == "registered" and
                          row["value"].get("slot") == "code"}
            for (stored,) in self.coordinator.connection.execute("SELECT value FROM external_operations"):
                producer = loads(stored)
                identity = producer["run_locator"]["case_id"], producer["run_locator"]["run_id"], producer["attempt_id"]
                require(producer["terminal_evidence_digest"] is None or producer["consumption_release"] is not None or
                        identity in registered, "fault_capture", "post_unconsumed_source")
            candidate["schema_version"] = "0.11"
            candidate["proof"].update(schema_version="0.8", unconsumed_code_sources=[])
            normalize(candidate, binding=self.binding)
        except Exception as error:
            import traceback
            exclusive(self.directory / (stage + "-source-error.txt"), traceback.format_exc().encode())
            if candidate is not None:
                save_evidence(self.directory, stage + "-rejected-raw.json", canonical(candidate))
            return {"raw_sha256": None, "rejection": {"type": type(error).__name__, "message": str(error)}}
        content = canonical(candidate)
        save_evidence(self.directory, stage + "-raw.json", content)
        return {"raw_sha256": sha(content), "rejection": None}

    def identity_state(self):
        return {"namespace": self.identities.scenario_id, "ordinals": dict(self.identities.ordinals),
                "allocations": deepcopy(self.identities.allocations)}

    def observe(self, call):
        @wraps(call)
        def actual(*args, **kwargs):
            function = getattr(call, "func", call)
            bound = inspect.signature(function).bind(*getattr(call, "args", ()), *args,
                **{**(getattr(call, "keywords", None) or {}), **kwargs})
            bound.apply_defaults()
            request = {key: asdict(value) if is_dataclass(value) else deepcopy(value)
                       for key, value in bound.arguments.items()}
            instance = getattr(function, "__self__", None)
            owner = {"worker_id": getattr(instance, "worker_id", getattr(instance, "worker", request.get("worker_id"))),
                "capability_id": getattr(instance, "capability_id", request.get("capability_id")),
                "invocation_epoch": getattr(instance, "epoch", request.get("epoch"))}
            position = len(self.calls)
            before, _ = capture_snapshot(self.directory, "call-" + str(position) + "-before", self.roots, self.request)
            observation = {"entry": function.__qualname__, "request": request, "owner": owner,
                "before_snapshot": before, "after_snapshot": None,
                "identities_before": self.identity_state(), "identities_after": None,
                "return": None, "exception": None}
            self.calls.append(observation)
            with self.identities.installed():
                try:
                    result = call(*args, **kwargs)
                except Exception as error:
                    observation["exception"] = {"type": type(error).__name__, "message": str(error)}
                    raise
                else:
                    observation["return"] = deepcopy(result)
                    return result
                finally:
                    observation["identities_after"] = self.identity_state()
                    observation["after_snapshot"], _ = capture_snapshot(self.directory,
                        "call-" + str(position) + "-after", self.roots, self.request)
        return actual

    def after_fault(self):
        self.stage("S1", {"injector_pid": os.getpid()})

    def recovered(self, *, contenders=None):
        observed = [] if contenders is None else [{**value, "call": call} for value, call in zip(contenders, self.contenders)]
        require(len(observed) == len(contenders or []), "fault_capture", "all_contenders")
        self.stage("S2", {"calls": self.calls, "contenders": observed})

    def repeated(self):
        self.stage("S3", {"calls": self.calls})
        anchor = {key: self.common[key] for key in ("schema_version", "binding", "case_id", "nodeid",
            "process_request_sha256", "process_receipt_sha256", "process_source_sha256")}
        anchor["stage_heads"] = [sha((self.directory / (name + ".json")).read_bytes()) for name in ("S0", "S1", "S2", "S3")]
        exclusive(self.directory / "anchor.json", canonical(anchor))
        from harness.fault_source_trace import verify_repeat
        verify_repeat(self.directory, self.records, self.manifests)

    def finish(self):
        from harness.fault_source_trace import source_bundle
        binding = pytest_evidence.ACTIVE.value if self.pytest_request is not None else self.binding
        bundle = source_bundle(self.directory, binding, self.request["case_id"], pytest_request=self.pytest_request)
        result = deepcopy(bundle["source"])
        result["schema_version"] = "0.13" if self.pytest_request is not None else "0.12"
        result["proof"].update(schema_version="0.10" if self.pytest_request is not None else "0.9",
                               fault_sources=[bundle["declaration"]])
        if self.pytest_request is not None:
            result["proof"]["pytest_request"] = self.pytest_request
        return result
