"""B02 child bootstrap: immutable source proofs, one coordinator, fresh authority."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import uuid

from .budget import policy
from .checkpoints import persist_checkpoint, verify_checkpoint, verify_source_checkpoint
from .coordinator import boundary, component, exclusive_directory, read_regular
from .execution import parse_ledger
from .integrity import validate_run_root
from .pause import runtime_fingerprint, validate_fingerprint
from .protocol import PROTOCOL, operation_variant
from .strict_json import ControlIntegrityError, canonical_bytes, closed, digest, digest_value, loads, number, require, text


SOURCE_CONTRACT = next(row for row in PROTOCOL["evidence_unions"] if row["union_id"] == "SourceSnapshotProof")


def validate_source_fingerprint(value, source_schema, creation_reason):
    """Historical absence is a source-only fact, never a runnable fingerprint."""
    if source_schema == "0.2":
        closed(value, ("availability", "reason"))
        require(creation_reason == "replay_of" and value == {
            "availability": "not_recorded", "reason": "legacy_schema_0_2"}, "Invalid legacy source fingerprint")
    else:
        require(source_schema in ("0.3", "0.4"), "Unsupported source fingerprint schema")
        validate_fingerprint(value)
        require(value["execution_schema"] == source_schema, "Source fingerprint schema mismatch")


def validate_source_proof(proof, creation_reason):
    require(type(proof) is dict, "Missing SourceSnapshotProof")
    tag = "replay_root" if creation_reason == "replay_of" else "fork_head"
    variant = next(row for row in SOURCE_CONTRACT["variants"] if row["tag"] == tag)
    closed(proof, (SOURCE_CONTRACT["tag_field"], *variant["required_fields"]))
    combination = {key: proof[key] for key in ("source_snapshot_kind", "source_schema", "source_control_revision_proof")}
    require(any(combination == dict(row) for row in SOURCE_CONTRACT["valid_schema_revision_combinations"]),
            "Unsupported source schema/revision proof")
    require(proof["source_snapshot_kind"] == tag, "Wrong source proof variant")
    closed(proof["source_run_identity"], ("case_id", "run_id"))
    for value in proof["source_run_identity"].values():
        component(value)
    if tag == "replay_root":
        closed(proof["immutable_root_input"], ("root_goal", "input_snapshot"))
        require(digest(proof["immutable_root_input"]) == proof["root_input_digest"], "Source root digest mismatch")
        validate_source_fingerprint(proof["runtime_fingerprint"], proof["source_schema"], creation_reason)
    else:
        require(proof["source_run_status"] in SOURCE_CONTRACT["fork_head_run_status_contract"]["allowed_values"], "Ineligible fork status")
        number(proof["source_control_revision"], integer=True, minimum=1)
        closed(proof["source_latest_heads"], ("execution_head", "artifact_head", "checkpoint_head"))
        for key, value in proof["source_latest_heads"].items():
            digest_value(value, nullable=key == "artifact_head")
        require(proof["source_revision_cas"] == digest({"source_run_identity": proof["source_run_identity"],
                                                       "revision": proof["source_control_revision"],
                                                       "heads": proof["source_latest_heads"]}), "Fork revision binding mismatch")
        require(type(proof["eligible_artifact_snapshot"]) is list, "Invalid fork evidence snapshot")
    return proof


@dataclass(frozen=True)
class ReplayRunRequest:
    source_run_locator: dict
    idempotency_key: str
    source_root_input_digest: str


@dataclass(frozen=True)
class ForkRunRequest:
    source_run_locator: dict
    idempotency_key: str
    source_head_digest: str
    artifact_ids: tuple[str, ...] = ()
    profile_id: str = "balanced_v1"


@dataclass(frozen=True)
class HistoricalSourceRead:
    """A trusted historical reader's normalized result, never a public payload.

    The reader validates its original 0.3 representation. The control consumer
    independently checks immutable bytes, historical fingerprint, checkpoint,
    domain owners, and the current source revision in the shared transaction.
    """

    root_inputs: dict
    runtime_fingerprint: dict
    validated_projection: dict | None
    eligible_artifact_snapshot: tuple
    evidence_files: dict


class ChildOperations:
    def __init__(self, coordinator, worker, lease_seconds, source_adapter=None):
        self.coordinator, self.worker, self.lease_seconds = coordinator, worker, lease_seconds
        self.source_adapter = source_adapter

    def create(self, request, actor):
        require(type(request) in (ReplayRunRequest, ForkRunRequest), "Expected typed child request")
        fork = type(request) is ForkRunRequest
        operation_type = "fork_run" if fork else "replay_run"
        identity = actor.authorize("fork" if fork else "replay")
        if fork:
            actor.authorize("policy.select")
            digest_value(request.source_head_digest)
            require(type(request.artifact_ids) is tuple and request.artifact_ids == tuple(sorted(set(request.artifact_ids))),
                    "Non-canonical fork evidence selection")
        else:
            digest_value(request.source_root_input_digest)
        text(request.idempotency_key)
        closed(request.source_run_locator, ("case_id", "run_id"))
        for item in request.source_run_locator.values():
            component(item)
        canonical = {**asdict(request), "actor": identity}
        canonical.pop("idempotency_key")
        if fork:
            canonical["artifact_ids"] = list(request.artifact_ids)
        coordinator = self.coordinator
        with coordinator.transaction() as db:
            old = coordinator.lookup_key("public_control", request.idempotency_key, db=db)
            if old is not None:
                require(old["request_digest"] == digest({"operation_type": operation_type, "operation_variant": "not_applicable", "request": canonical}),
                        "Same-key request conflict")
                operation = old
            else:
                try:
                    proof, source_inputs, fingerprint, source_policy, classification = self._source(db, request)
                except (OSError, UnicodeError, KeyError, TypeError) as error:
                    raise ControlIntegrityError("Source input evidence is unavailable") from error
                selected = policy(request.profile_id).value if fork else source_policy
                child = {"creation_reason": "fork_of" if fork else "replay_of", "source_run_identity": request.source_run_locator,
                         "root_inputs": source_inputs, "source_runtime_fingerprint": fingerprint, "target_runtime_fingerprint": runtime_fingerprint()}

                def reserve(operation_id, stamp):
                    value = {"reserved_child_run_locator": {"case_id": request.source_run_locator["case_id"], "run_id": "run_" + uuid.uuid4().hex},
                             "source_snapshot_proof": proof, "canonical_child_policy_bytes": canonical_bytes(selected).decode(),
                             "child_policy_digest": selected["policy_digest"], "child_policy_profile": selected["profile_id"],
                             "child_policy_version": selected["schema_version"],
                             "child_policy_selection_authority": "authenticated_host_profile_selection" if fork else "validated_source_policy",
                             "initial_invocation_capability_inputs": {"attempt_id": "attempt_000001", "target_kind": "method_planner"}}
                    if not fork:
                        value["source_policy_classification_proof"] = classification
                    return value

                def snapshot(operation):
                    from .interfaces import _bootstrap_snapshot
                    return {**_bootstrap_snapshot(coordinator.root, operation, child=child), "child": child}

                operation = coordinator.reserve_in_transaction(db, operation_type, "not_applicable", "public_control",
                                                               request.idempotency_key, canonical, self.worker, reserve,
                                                               lease_seconds=self.lease_seconds, build_snapshot=snapshot)
                if fork:
                    boundary(coordinator.observer, "child.source_revision_cas", "before", operation)
                    row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (digest(request.source_run_locator),)).fetchone()
                    require(row is not None and row["revision"] == proof["source_control_revision"] and
                            {key: loads(row["value"])["projection"][key] for key in proof["source_latest_heads"]} == proof["source_latest_heads"],
                            "Fork source revision CAS lost")
                    boundary(coordinator.observer, "child.source_revision_cas", "after", operation)
        from .operations import TerminalOperations
        terminal = TerminalOperations(coordinator, self.worker, self.lease_seconds)
        if operation["status"] != "in_progress" and operation["error"] is not None and "close_operation_id" in operation["error"]:
            terminal.continue_close(operation["error"]["close_operation_id"])
        try:
            return self._materialize(operation)
        except (ControlIntegrityError, OSError) as error:
            terminal.fail_bootstrap(operation, error)
            return coordinator.get(operation["operation_id"])

    def _source(self, db, request):
        """Read replay roots without consuming current heads; fork consumes a stable head."""
        from .records import validate_record

        locator = request.source_run_locator
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        require(root == root.resolve() and root.is_dir(), "Missing or escaped source root")
        raw = read_regular(root / "execution_history.jsonl")
        require(b"\n" in raw, "Source has no complete Run record")
        boundary(self.coordinator.observer, "ingress.source_record", "before")
        try:
            created = loads(raw.split(b"\n", 1)[0], canonical=False)
            require(type(created) is dict, "Invalid source creation record")
            if created.get("schema_version") == "0.2":
                return self._legacy_source(db, request, root, raw, created)
            if created.get("schema_version") == "0.3":
                return self._historical_source(db, request, root, raw, created)
            loads(raw.split(b"\n", 1)[0])
            require(created.get("schema_version") == "0.4", "Source requires a supported immutable-root validator")
            validate_record(created)
        finally:
            boundary(self.coordinator.observer, "ingress.source_record", "after")
        require(created["record_type"] == "run" and created["event_index"] == 1 and created["previous_execution_head"] is None and
                created["canonical_output_root"] == str(root) and {k: created[k] for k in locator} == locator, "Source identity mismatch")
        inputs = {}
        for name in ("root_goal", "input_snapshot"):
            reference = created[name + "_reference"]
            path = root / reference["reference"]
            require(path == path.resolve() and path.is_relative_to(root), "Source reference escaped Run")
            data = read_regular(path)
            require(sha256(data).hexdigest() == reference["sha256"], "Source input bytes changed")
            inputs[name] = loads(data)
        sources = []
        for row in db.execute("SELECT operation_id FROM control_operations WHERE operation_type IN ('start_run','replay_run','fork_run')"):
            operation = self.coordinator.get(row[0], db=db)
            target = operation["reservation"].get("reserved_run_locator", operation["reservation"].get("reserved_child_run_locator"))
            if target == locator:
                sources.append(self.coordinator.snapshot(operation["operation_id"], db=db))
        require(len(sources) == 1 and sources[0]["records"][0] == created, "Source creation proof is unavailable")
        fingerprint = sources[0]["runtime_fingerprint"]
        validate_source_fingerprint(fingerprint, "0.4", "fork_of" if type(request) is ForkRunRequest else "replay_of")
        saved = loads(read_regular(root / "budget_policy.json"))
        selected = policy(saved["profile_id"]).value
        require(saved == selected and created["policy_digest"] == selected["policy_digest"], "Unsupported source policy")
        if type(request) is ReplayRunRequest:
            require(digest(inputs) == request.source_root_input_digest, "Replay source root input digest changed")
            proof = {"source_snapshot_kind": "replay_root", "source_run_identity": locator,
                     "immutable_root_input": inputs, "root_input_digest": digest(inputs), "source_schema": "0.4",
                     "runtime_fingerprint": fingerprint, "source_control_revision_proof": "versioned_control_revision_not_consumed_for_root_replay"}
        else:
            row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()
            require(row is not None, "Unknown source control revision")
            control = loads(row["value"])
            require(control["projection"] is not None, "Source checkpoint unavailable")
            verify_source_checkpoint(self.coordinator, db, root, control["manifest"])
            state = validate_run_root(root, manifest=control["manifest"], projection=control["projection"]).value
            require(state["execution_head"] == request.source_head_digest, "Fork source head changed")
            from .operations import TerminalOperations
            closure = TerminalOperations(self.coordinator, self.worker, self.lease_seconds).closure(locator, db=db)
            if state["run_status"] == "paused":
                pause = state.get("active_pause")
                require(pause is not None and pause["status"] == "opened" and closure is None, "Source Pause is not stable")
                owner = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (digest(locator), pause["pause_id"])).fetchone()
                require(owner is not None and loads(owner[0])["owner"] is None and loads(owner[0])["status"] == "opened", "Source Pause was claimed")
            else:
                require(state["run_status"] in ("completed", "failed", "halted") and closure is not None and
                        closure["terminal_closure"] == "committed" and closure["run_status"] == state["run_status"], "Source is not a committed terminal head")
            index = loads(read_regular(root / "artifact_index.json"))
            pointers = {pointer["artifact_id"]: pointer for pointer in index["current"].values() if pointer is not None}
            require(set(request.artifact_ids) <= set(pointers), "Selected fork evidence is not current validated evidence")
            evidence = [{"source_run_identity": locator, "pointer": pointers[item]} for item in request.artifact_ids]
            heads = {key: state[key] for key in ("execution_head", "artifact_head", "checkpoint_head")}
            proof = {"source_snapshot_kind": "fork_head", "source_run_identity": locator, "source_schema": "0.4",
                     "source_run_status": state["run_status"], "source_latest_heads": heads, "source_control_revision": row["revision"],
                     "source_control_revision_proof": "exact_source_control_revision",
                     "source_revision_cas": digest({"source_run_identity": locator, "revision": row["revision"], "heads": heads}),
                     "eligible_artifact_snapshot": evidence}
            inputs = {"root_goal": inputs["root_goal"], "input_snapshot": {"source_provenance": locator, "immutable_evidence": evidence}}
        validate_source_proof(proof, "fork_of" if type(request) is ForkRunRequest else "replay_of")
        classification = {"classification": "supported", "source_run_identity": locator, "source_schema": "0.4",
                          "canonical_policy_bytes": canonical_bytes(selected).decode(), "policy_digest": selected["policy_digest"],
                          "profile_id": selected["profile_id"], "policy_version": selected["schema_version"],
                          "supported_set_digest": digest([policy(name).value for name in ("balanced_v1", "phase_b_test")])}
        return proof, inputs, fingerprint, selected, classification

    def _historical_source(self, db, request, root, raw, created):
        """Consume original 0.3 validation without migrating or inventing authority."""
        from .operations import TerminalOperations
        locator = request.source_run_locator
        fork = type(request) is ForkRunRequest
        require(self.source_adapter is not None and hasattr(self.source_adapter, "read_source"),
                "Schema 0.3 requires its trusted historical source reader")
        require(raw.endswith(b"\n"), "Incomplete historical execution evidence")
        records = [loads(line, canonical=False) for line in raw.splitlines()]
        require(all(type(r) is dict and r.get("schema_version") == "0.3" and all(r.get(k) == v for k, v in locator.items()) for r in records),
                "Mixed historical schema or source identity")
        require(created.get("record_type") == "run" and created.get("event") == "created" and
                created.get("canonical_output_root") == str(root) and sum(r.get("record_type") == "run" for r in records) == 1,
                "Historical Run creation mismatch")
        require(not (root / "budget_policy.json").exists() and not (root / "budget_policy.json").is_symlink() and
                not any(r.get("record_type") == "budget" or any(k.startswith("policy_") for k in r) for r in records),
                "Historical source is not authoritatively pre-A06")
        row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone() if fork else None
        control = loads(row["value"]) if row else None
        view = {"source_run_identity": locator, "source_schema": "0.3", "creation_reason": "fork_of" if fork else "replay_of",
                "selected_artifact_ids": list(request.artifact_ids) if fork else [], "source_control": control}
        read = self.source_adapter.read_source(root, loads(canonical_bytes(view)))
        require(type(read) is HistoricalSourceRead, "Untyped historical source validation")
        closed(read.root_inputs, ("root_goal", "input_snapshot"))
        require(type(read.evidence_files) is dict and "execution_history.jsonl" in read.evidence_files,
                "Historical reader omitted source bytes")
        for name, expected in read.evidence_files.items():
            relative = Path(name)
            path = root / relative
            require(not relative.is_absolute() and relative.parts and all(part not in (".", "..") for part in relative.parts) and
                    relative.as_posix() == name and path == path.resolve() and path.is_relative_to(root), "Historical evidence escaped Run")
            digest_value(expected)
            require(sha256(read_regular(path)).hexdigest() == expected, "Historical evidence bytes changed")
        require(read.evidence_files["execution_history.jsonl"] == sha256(raw).hexdigest(), "Historical reader changed its source")
        for name in ("root_goal", "input_snapshot"):
            reference = created[name + "_reference"]
            closed(reference, ("reference", "sha256"))
            require(reference["reference"] in read.evidence_files and read.evidence_files[reference["reference"]] == reference["sha256"],
                    "Historical immutable input reference mismatch")
            require(loads(read_regular(root / reference["reference"]), canonical=False) == read.root_inputs[name],
                    "Historical input normalization changed its value")
        fingerprint = read.runtime_fingerprint
        validate_source_fingerprint(fingerprint, "0.3", "fork_of" if fork else "replay_of")
        require(any(r.get("runtime_fingerprint") == fingerprint for r in records), "Historical fingerprint was not recorded")
        selected = policy("balanced_v1").value
        inputs = read.root_inputs
        if not fork:
            require(read.validated_projection is None and not read.eligible_artifact_snapshot, "Replay reader consumed mutable source heads")
            require(digest(inputs) == request.source_root_input_digest, "Replay source root input digest changed")
            proof = {"source_snapshot_kind": "replay_root", "source_run_identity": locator, "immutable_root_input": inputs,
                     "root_input_digest": digest(inputs), "source_schema": "0.3", "runtime_fingerprint": fingerprint,
                     "source_control_revision_proof": "versioned_control_revision_not_consumed_for_root_replay"}
        else:
            require(row is not None and control is not None and control.get("projection") is not None and
                    read.validated_projection == control["projection"], "Historical source lacks its real control revision")
            state = read.validated_projection
            require("budget" not in state and all(state.get(k) == v for k, v in locator.items()), "Historical projection identity/policy mismatch")
            heads = {k: state[k] for k in ("execution_head", "artifact_head", "checkpoint_head")}
            require(heads["execution_head"] == request.source_head_digest == digest(records[-1]), "Historical source head changed")
            checkpoint_state = verify_source_checkpoint(self.coordinator, db, root, control["manifest"])
            require(all(checkpoint_state[k] == state[k] for k in checkpoint_state) and control["manifest"]["checkpoint_head"] == heads["checkpoint_head"],
                    "Historical public checkpoint changed")
            closure = TerminalOperations(self.coordinator, self.worker, self.lease_seconds).closure(locator, db=db)
            if state["run_status"] == "paused":
                pause = state.get("active_pause")
                latest = next((r for r in reversed(records) if r["record_type"] == "pause"), None)
                require(pause is not None and latest is not None and latest["status"] == pause["status"] == "opened" and
                        latest["pause_id"] == pause["pause_id"] and closure is None, "Historical Pause is not stable")
                owner = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (digest(locator), pause["pause_id"])).fetchone()
                require(owner is not None and loads(owner[0])["owner"] is None and loads(owner[0])["status"] == "opened" and
                        loads(owner[0])["opened_head"] == digest(latest), "Historical Pause was claimed")
            else:
                require(state["run_status"] in ("completed", "failed", "halted") and records[-1]["record_type"] == "run_lifecycle" and
                        records[-1]["to_status"] == state["run_status"] and closure is not None and closure["terminal_closure"] == "committed" and
                        closure["run_status"] == state["run_status"], "Historical source is not a committed terminal head")
            require(type(read.eligible_artifact_snapshot) is tuple, "Untyped historical artifact evidence")
            evidence = list(read.eligible_artifact_snapshot)
            require(sorted(e["pointer"]["artifact_id"] for e in evidence) == list(request.artifact_ids) and
                    all(e["source_run_identity"] == locator for e in evidence), "Historical artifact selection mismatch")
            index = loads(read_regular(root / "artifact_index.json"))
            require(index["execution_head"] == heads["execution_head"] and index["artifact_head"] == heads["artifact_head"], "Historical artifact heads changed")
            pointers = {p["artifact_id"]: p for p in index["current"].values() if p is not None}
            for entry in evidence:
                pointer = entry["pointer"]
                require(pointers.get(pointer["artifact_id"]) == pointer, "Historical fork artifact is not current")
                for member in pointer["members"]:
                    require(read.evidence_files.get(member["canonical_path"]) == member["sha256"], "Historical artifact bytes are unverified")
            proof = {"source_snapshot_kind": "fork_head", "source_run_identity": locator, "source_schema": "0.3",
                     "source_run_status": state["run_status"], "source_latest_heads": heads, "source_control_revision": row["revision"],
                     "source_control_revision_proof": "exact_source_control_revision",
                     "source_revision_cas": digest({"source_run_identity": locator, "revision": row["revision"], "heads": heads}),
                     "eligible_artifact_snapshot": evidence}
            inputs = {"root_goal": inputs["root_goal"], "input_snapshot": {"source_provenance": locator, "immutable_evidence": evidence}}
        validate_source_proof(proof, "fork_of" if fork else "replay_of")
        absence = {"tag": "absent_before_a06", "source_creation_digest": digest(created),
                   "source_ledger_bytes_digest": sha256(raw).hexdigest(), "source_schema": "0.3"}
        classification = {"classification": "pre_a06", "source_run_identity": locator, "source_schema": "0.3",
                          "canonical_policy_bytes": absence, "policy_digest": absence, "profile_id": absence,
                          "policy_version": absence, "authoritative_policy_absence_proof": absence,
                          "supported_set_digest": digest([policy(name).value for name in ("balanced_v1", "phase_b_test")])}
        return proof, inputs, fingerprint, selected, classification

    def _legacy_source(self, db, request, root, raw, created):
        """Read the original 0.2 format without importing its execution authority."""
        require(type(request) is ReplayRunRequest, "Legacy source permits replay only")
        locator = request.source_run_locator
        closed(created, ("schema_version", "record_type", "event", "run_id", "case_id", "parent_run_id",
                         "creation_reason", "root_goal_reference", "input_snapshot_reference", "canonical_output_root",
                         "checkpoint_thread_id", "status", "created_at"))
        require(created["record_type"] == "run" and created["event"] == "created" and created["status"] == "running" and
                created["canonical_output_root"] == str(root) and {k: created[k] for k in locator} == locator and
                created["checkpoint_thread_id"] == f"{locator['case_id']}:{locator['run_id']}", "Legacy source identity mismatch")
        text(created["parent_run_id"], nullable=True)
        require(created["creation_reason"] in ("initial", "replay", "fork"), "Unsupported legacy creation reason")
        text(created["created_at"])
        require(raw.endswith(b"\n"), "Incomplete legacy source evidence")
        records = [loads(line, canonical=False) for line in raw.splitlines()]
        for row in records:
            require(type(row) is dict and row.get("schema_version") == "0.2" and
                    all(row.get(k) == v for k, v in locator.items()) and
                    row.get("record_type") in ("run", "cycle", "attempt", "transition", "human_request", "human_response") and
                    not any("fingerprint" in k or k.startswith("policy_") for k in row), "Conflicting legacy source evidence")
        require(sum(row["record_type"] == "run" for row in records) == 1, "Ambiguous legacy source creation")
        require(db.execute("SELECT 1 FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone() is None,
                "Versioned authority cannot be classified as legacy")
        for item in db.execute("SELECT reservation FROM control_operations WHERE operation_type IN ('start_run','replay_run','fork_run')"):
            reservation = loads(item[0])
            require(reservation.get("reserved_run_locator", reservation.get("reserved_child_run_locator")) != locator,
                    "Versioned bootstrap cannot be classified as legacy")
        policy_path = root / "budget_policy.json"
        require(not policy_path.exists() and not policy_path.is_symlink(), "Legacy source contains policy evidence")
        state = loads(read_regular(root / "graph_state.json"), canonical=False)
        require(type(state) is dict and all(state.get(k) == v for k, v in locator.items()), "Legacy state identity mismatch")
        goal = state.get("user_goal")
        text(goal)
        goal_ref = created["root_goal_reference"]
        closed(goal_ref, ("kind", "field", "sha256"))
        require(goal_ref["kind"] == "state_field" and goal_ref["field"] == "user_goal" and
                sha256(goal.encode()).hexdigest() == goal_ref["sha256"], "Legacy root goal digest mismatch")
        reference = created["input_snapshot_reference"]
        closed(reference, ("kind", "path", "exists", "sha256"))
        require(reference["kind"] == "file" and reference["exists"] is True, "Legacy input snapshot unavailable")
        text(reference["path"])
        project = Path(__file__).resolve().parents[3]
        path = Path(reference["path"])
        path = path if path.is_absolute() else project / path
        allowed = (project / "configs/cases", project / "evaluation/cases", self.coordinator.root / "_generated_case_configs")
        require(path == path.resolve() and any(path.is_relative_to(base) for base in allowed) and
                path.suffix in (".json", ".yaml", ".yml") and not any(part.startswith(".") for part in path.parts),
                "Legacy config is outside trusted case inputs")
        config_raw = read_regular(path)
        require(sha256(config_raw).hexdigest() == reference["sha256"], "Legacy input bytes changed")
        if path.suffix == ".json":
            config = loads(config_raw, canonical=False)
        else:
            from lqcd_agent.agents.analysis_engineer import _parse_scalar
            config, list_key = {}, None
            for line in config_raw.decode().splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if line.strip().startswith("- ") and list_key is not None:
                    config[list_key].append(_parse_scalar(line.strip()[2:].strip()))
                else:
                    require(not line.startswith(" ") and ":" in line, "Unsupported legacy config syntax")
                    name, value = line.split(":", 1)
                    name, value = name.strip(), value.strip()
                    require(bool(name) and name not in config, "Duplicate legacy config key")
                    config[name] = _parse_scalar(value) if value else []
                    list_key = None if value else name
        require(type(config) is dict and bool(config), "Missing legacy input object")
        inputs = {"root_goal": {"goal": goal}, "input_snapshot": config}
        require(digest(inputs) == request.source_root_input_digest, "Replay source root input digest changed")
        fingerprint = {"availability": "not_recorded", "reason": "legacy_schema_0_2"}
        proof = {"source_snapshot_kind": "replay_root", "source_run_identity": locator, "source_schema": "0.2",
                 "immutable_root_input": inputs, "root_input_digest": digest(inputs), "runtime_fingerprint": fingerprint,
                 "source_control_revision_proof": "legacy_control_revision_not_applicable"}
        validate_source_proof(proof, "replay_of")
        absence = {"tag": "absent_before_a06", "source_creation_digest": digest(created),
                   "source_ledger_bytes_digest": sha256(raw).hexdigest(), "source_schema": "0.2"}
        classification = {"classification": "pre_a06", "source_run_identity": locator, "source_schema": "0.2",
                          "canonical_policy_bytes": absence, "policy_digest": absence, "profile_id": absence,
                          "policy_version": absence, "authoritative_policy_absence_proof": absence,
                          "supported_set_digest": digest([policy(name).value for name in ("balanced_v1", "phase_b_test")])}
        return proof, inputs, fingerprint, policy("balanced_v1").value, classification

    def _materialize(self, operation):
        from .capabilities import prepare_capability
        from .interfaces import ControlPlane

        coordinator = self.coordinator
        if operation["status"] != "in_progress":
            return operation
        if coordinator._time().monotonic_seconds >= operation["lease_expires"]:
            operation = coordinator.acquire(operation["operation_id"], self.worker, lease_seconds=self.lease_seconds)
        elif operation["worker_owner_id"] != self.worker:
            return operation
        with coordinator.failure_context(operation):
            snapshot = coordinator.snapshot(operation["operation_id"])
        reserved = operation["reservation"]
        locator = reserved["reserved_child_run_locator"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        records, manifest = snapshot["records"], snapshot["manifest"]
        ledger = lambda count: b"".join(canonical_bytes(row) + b"\n" for row in records[:count])
        plans = {
            "child_run_root_created": [(name + ".json", canonical_bytes(value), None) for name, value in snapshot["child"]["root_inputs"].items()],
            "child_policy_published": [("budget_policy.json", reserved["canonical_child_policy_bytes"].encode(), None)],
            "child_run_ledger_started": [("execution_history.jsonl", ledger(1), b"")],
            "child_lineage_recorded": [("execution_history.jsonl", ledger(2), ledger(1))],
            "child_bootstrap_records_complete": [("execution_history.jsonl", ledger(7), ledger(2)), ("artifact_history.jsonl", b"", None)],
            "child_running_lifecycle_recorded": [("execution_history.jsonl", ledger(8), ledger(7))],
            "child_checkpoint_committed": [("artifact_index.json", canonical_bytes(snapshot["artifact_index"]), None),
                                           ("checkpoints/" + manifest["checkpoint_id"] + ".json", canonical_bytes(manifest), None)]}
        declaration = operation_variant(operation["operation_type"], "not_applicable")
        while operation["status"] == "in_progress":
            with coordinator.failure_context(operation):
                phase = next(target for source, target in declaration["success_edges"] if source == operation["phase"])
                for path, content, previous in plans.get(phase, []):
                    coordinator.freeze_publication(operation["operation_id"], self.worker, operation["lease_epoch"],
                                                   operation["phase_revision"], phase, root / path, content, previous=previous)

                def publish(db, current):
                    from .operations import BootstrapIntegrityError
                    try:
                        ControlPlane._verify_start_prefix(root, plans, declaration, current, phase)
                        if declaration["phases"].index(current["phase"]) >= declaration["phases"].index("child_checkpoint_committed"):
                            verify_checkpoint(root, manifest)
                            validate_run_root(root, manifest=manifest, projection=snapshot["projection"])
                    except (ControlIntegrityError, OSError) as error:
                        raise BootstrapIntegrityError(str(error)) from error
                    if phase == "source_snapshot_committed":
                        validate_source_proof(reserved["source_snapshot_proof"], snapshot["child"]["creation_reason"])
                        return {"source_snapshot_proof": reserved["source_snapshot_proof"], "lineage_snapshot_digest": digest(reserved["source_snapshot_proof"]),
                                "source_policy_classification_or_not_applicable": reserved.get("source_policy_classification_proof", {"tag": "not_applicable"})}
                    if phase == "child_run_root_created":
                        exclusive_directory(root.parent)
                        exclusive_directory(root, observer=coordinator.observer, name="child")
                    if phase == "child_checkpoint_committed":
                        persist_checkpoint(coordinator, db, current, root, snapshot["checkpoint"],
                                           {"source": "input", "step": 0, "parents": {}, "operation_id": current["operation_id"]})
                    for path, _, _ in plans.get(phase, []):
                        coordinator.materialize_publication(db, current, phase, root / path, name="child." + path)
                    evidence = {
                        "child_run_root_created": {"reserved_child_locator": locator, "lineage_snapshot_digest": digest(reserved["source_snapshot_proof"])},
                        "child_policy_published": {"canonical_child_policy": reserved["canonical_child_policy_bytes"], "child_policy_digest": reserved["child_policy_digest"],
                                                   "child_policy_selection_proof": reserved["child_policy_selection_authority"]},
                        "child_run_ledger_started": {"child_run_created_initializing": snapshot["run_creation_binding"]},
                        "child_lineage_recorded": {"root_or_replay_or_fork_lineage": records[1]},
                        "child_bootstrap_records_complete": {"child_bootstrap_closure": records[2:7]},
                        "child_running_lifecycle_recorded": {"child_initializing_to_running": records[7]}}
                    if phase in evidence:
                        return evidence[phase]
                    verify_checkpoint(root, manifest)
                    state = validate_run_root(root, manifest=manifest, projection=snapshot["projection"]).value
                    if phase == "child_checkpoint_committed":
                        db.execute("INSERT INTO run_controls VALUES (?,?,?)", (digest(locator), 1, canonical_bytes({"locator": locator, "projection": state, "manifest": manifest})))
                        return {"child_running_resulting_head": manifest["execution_head"]}
                    if phase == "invocation_capability_prepared":
                        return prepare_capability(coordinator, db, current, root, manifest, state)
                    require(phase == "result_committed", "Unknown child phase")
                    result = {"run_locator": locator, "run_status": "running", "terminal_closure": "not_applicable", "domain_status": None,
                              **{key: manifest[key] for key in ("execution_head", "artifact_head", "checkpoint_head")}, "pause_id": None,
                              "capability_id": "capability_" + current["operation_id"], "request_digest": current["request_digest"]}
                    return {"exact_public_or_internal_result": result, "final_phase_revision": current["phase_revision"] + 1}

                operation = coordinator.step(operation["operation_id"], self.worker, operation["lease_epoch"], operation["phase_revision"], phase, publish)
        return operation
