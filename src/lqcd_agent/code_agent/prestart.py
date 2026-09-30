"""Durable, precomputed Code inputs in the existing external-operation row."""
from hashlib import sha256

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.coordinator import boundary, exclusive_directory, publish_exact, read_regular, replace_projection
from lqcd_agent.control.execution import append_record_bytes, parse_ledger
from lqcd_agent.control.integrity import validate_control_root
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.pause import runtime_fingerprint
from lqcd_agent.control.projections import bounded_projection
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.records import build_record
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, number, require

from .schemas import IDENTITY, task_context, validate_manifest, validate_task


class CodePrestart:
    """Publish task, manifest, aggregate and core without starting an Attempt."""

    def __init__(self, coordinator, producer_operation_id, worker_id, epoch):
        self.coordinator, self.producer = coordinator, producer_operation_id
        self.worker, self.epoch = worker_id, epoch

    def _fence(self, db, *, materialize_setup_only=False, materialize_frozen_aggregate_only=False):
        coordinator = self.coordinator
        value = ExternalControl(coordinator).read(db, self.producer)
        now = coordinator._time().monotonic_seconds
        require(value["worker_owner_id"] == self.worker and value["lease_epoch"] == self.epoch and
                value["resolution_owner"] is None, "Stale external prestart owner")
        require(not (materialize_setup_only and materialize_frozen_aggregate_only),
                "Conflicting prestart recovery modes")
        if materialize_frozen_aggregate_only:
            require(now < value["worker_lease_expires_at"] and
                    value["operation_phase"] == "workspace_manifest_committed" and
                    value["reservation_digest"] is None and
                    "aggregate" in value.get("prestart", {}),
                    "Frozen aggregate recovery has no unpublished suffix")
        elif not materialize_setup_only:
            require(now < min(value["worker_lease_expires_at"], value["hard_deadline"]),
                    "Stale external prestart owner")
        active = value.get("prestart", {}).get("active_time")
        if materialize_frozen_aggregate_only:
            require(active is not None and active["published"] is True and
                    active.get("recovery_only") is not True and
                    now >= min(value["hard_deadline"], active["setup_record"]["payload"]["deadline_monotonic_seconds"]),
                    "Frozen aggregate recovery requires an expired original effect window")
        if materialize_setup_only:
            require(active is not None and now < value["worker_lease_expires_at"] and
                    (now < min(value["hard_deadline"], active["setup_record"]["payload"]["deadline_monotonic_seconds"]) or
                     active.get("recovery_only") is True and active.get("recovery_epoch") == self.epoch and
                     now < active["recovery_expires_at"]), "Stale setup materialization owner")
        if active is not None and not (materialize_setup_only or materialize_frozen_aggregate_only):
            require(active.get("recovery_only") is not True, "Setup recovery lease cannot execute effects")
            require(now < active["setup_record"]["payload"]["deadline_monotonic_seconds"],
                    "Setup active-time deadline elapsed")
        parent = coordinator.get(value["parent_control_operation_id"], db=db)
        require(parent["operation_type"] == "advance_run" and parent["status"] == "committed", "Missing committed Code parent")
        _, cap = InvocationLeases(coordinator).get(parent["result"]["capability_id"], db=db)
        authorization = cap["authorization"]
        require(cap["state"] == "unclaimed" and cap["started_intent"] is None and
                authorization["scope"] == "external_prestart_only" and
                authorization["identity"]["attempt_id"] == value["attempt_id"] and
                all(authorization["identity"][k] == v for k, v in value["run_locator"].items()) and
                parent["phase_revision"] == authorization["activation_result_revision"] and
                authorization["producer_operation_id"] == parent["operation_id"], "Invalid prestart capability")
        require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (digest(value["run_locator"]),)).fetchone() is None,
                "Run terminal ownership revoked prestart")
        root = coordinator.root / value["run_locator"]["case_id"] / value["run_locator"]["run_id"]
        require(root == root.resolve() and root.is_relative_to(coordinator.root), "Prestart Run path changed")
        return value, authorization, root

    def _save(self, db, value):
        revision = value["phase_revision"]
        value["phase_revision"] += 1
        count = db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
            (value["phase_revision"], canonical_bytes(value), self.producer, revision)).rowcount
        require(count == 1, "External prestart CAS lost")

    def _phase(self, db, value, target):
        machine = PROTOCOL["state_machines"]["external_operation"]
        require((value["operation_phase"], target) in machine["success_edges"], "Illegal prestart phase progression")
        value["operation_phase"] = target
        value["operation_status"] = "reserved"
        self._save(db, value)

    def _source(self, db, value, root):
        row = db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(value["run_locator"]),)).fetchone()
        require(row is not None, "Missing Code Run authority")
        control = loads(row[0])
        state = validate_control_root(self.coordinator, db, value["run_locator"], control).value
        require(state["attempt_id"] == value["attempt_id"] and state["attempt_kind"] == "code_agent" and
                state["attempt_status"] == "scheduled" and state["run_status"] == "running", "Code prestart target changed")
        return control, parse_ledger(read_regular(root / "execution_history.jsonl")), loads(read_regular(root / "artifact_index.json"))

    def publish_setup(self):
        with self.coordinator.transaction(commit_boundary="external.active_time_reserved") as db:
            saved = ExternalControl(self.coordinator).read(db, self.producer)
            frozen = saved.get("prestart", {}).get("active_time")
            require(frozen is not None and digest(frozen["setup_record"]) == frozen["setup_record_digest"],
                    "Missing frozen setup interval")
            if frozen["published"]:
                root = self.coordinator.root / saved["run_locator"]["case_id"] / saved["run_locator"]["run_id"]
                records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
                require(sum(record == frozen["setup_record"] for record in records) == 1,
                        "Published setup interval changed")
                return frozen["setup_record"]
            value, _, root = self._fence(db, materialize_setup_only=True)
            frozen = value.get("prestart", {}).get("active_time")
            require(frozen is not None and digest(frozen["setup_record"]) == frozen["setup_record_digest"],
                    "Missing frozen setup interval")
            require(value["operation_phase"] == "external_operation_reserved", "Setup publication out of order")
            row = db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(value["run_locator"]),)).fetchone()
            require(row is not None and loads(row[0]) == frozen["source_control"], "Setup control source changed")
            publish_exact(root / "execution_history.jsonl", frozen["setup_content"].encode(),
                          previous=frozen["previous_ledger"].encode(), observer=self.coordinator.observer,
                          name="external.setup_reservation")
            replace_projection(root / "artifact_index.json", canonical_bytes(frozen["source_index"]),
                               canonical_bytes(frozen["setup_index"]), observer=self.coordinator.observer)
            execution = parse_ledger(frozen["setup_content"].encode())
            index = frozen["setup_index"]
            state = bounded_projection(execution, artifact_index=index, artifact_head=index["artifact_head"],
                                       artifact_event_index=index["revision"]).value
            control = {**frozen["source_control"], "checkpoint_anchor_kind": "external_prestart", "external_owner": self.producer,
                       "projection": {**state, "checkpoint_head": frozen["source_control"]["manifest"]["checkpoint_head"]}}
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?",
                       (canonical_bytes(control), digest(value["run_locator"])))
            frozen["published"] = True
            self._save(db, value)
            return frozen["setup_record"]

    def commit_task(self, task):
        task = validate_task(task).value
        with self.coordinator.transaction() as db:
            value, authorization, root = self._fence(db)
            if "task" not in value.get("prestart", {}):
                require(value["operation_phase"] == "external_operation_reserved", "Task publication out of order")
                _, execution, index = self._source(db, value, root)
                source = self.coordinator.snapshot(value["parent_control_operation_id"], db=db)
                transition = source["records"][-1]
                active = value["prestart"]["active_time"]
                expected = [transition, active["setup_record"]] if active["published"] else [transition]
                require(execution.values[-len(expected):] == expected, "Task lacks exact setup source")
                require(transition["record_type"] == "transition" and transition["event"] == "committed", "Task lacks inbound Transition")
                expected = {**value["run_locator"], "cycle_id": value["cycle_id"], "attempt_id": value["attempt_id"],
                            "transition_id": transition["transition_id"], "producer_operation_id": self.producer}
                require(all(task[k] == expected[k] for k in IDENTITY) and
                        task["source_attempt_id"] == transition["source_attempt_id"] and
                        task["external_producer_contract"]["parent_control_operation_id"] == value["parent_control_operation_id"],
                        "Task producer or Transition mismatch")
                require(task["execution_head"] == authorization["heads"]["execution_head"] == digest(transition) and
                        task["artifact_head"] == index["artifact_head"] and task["source_runtime_fingerprint"] == runtime_fingerprint(),
                        "Task source heads changed")
                require((task["coding_backend_kind"], task["backend_version"]) == (value["backend_kind"], value["backend_version"]),
                        "Task backend differs from producer")
                decision = next((r for r in execution.values if r["event_id"] == task["budget_envelope_ref"]["event_id"]), None)
                require(decision is not None and digest(decision) == task["budget_envelope_digest"] and
                        decision["record_type"] == "budget" and decision["event"] == "decision_recorded" and
                        decision["payload"]["decision"] == "allow" and decision["payload"]["target_kind"] == "code_agent" and
                        decision == next(r for r in reversed(execution.values) if r["record_type"] == "budget" and
                                         r["event"] == "decision_recorded"), "Task lacks exact Code admission")
                policy = loads(read_regular(root / "budget_policy.json"))
                require(task["budget_policy_digest"] == policy["policy_digest"] and task["budget_profile_id"] == policy["profile_id"],
                        "Task budget policy changed")
                members = {(pointer["artifact_id"], member["canonical_path"], member["sha256"])
                           for pointer in index["current"].values() if pointer is not None for member in pointer["members"]}
                if task["task_origin"] == "coordinator_code_fix":
                    prior = self.coordinator.snapshot(value["parent_control_operation_id"], db=db)["original_index"]
                    members.update((pointer["artifact_id"], member["canonical_path"], member["sha256"])
                        for slot, pointer in prior["current"].items() if slot in ("analysis", "review", "decision") and pointer is not None
                        for member in pointer["members"])
                plan = index["current"]["plan"]
                require(plan is not None and any(e["artifact_id"] == plan["artifact_id"] for e in task["evidence"]), "Task lacks current plan")
                for evidence in task["evidence"]:
                    require((evidence["artifact_id"], evidence["path"], evidence["sha256"]) in members and
                            sha256(read_regular(root / evidence["path"])).hexdigest() == evidence["sha256"], "Task evidence changed")
                self._freeze(db, value, "task", task)
        self.publish_setup()
        return self._document("task", task, "external_operation_reserved", "task_committed", "task_digest", "external.task")

    def _freeze(self, db, value, name, payload):
        value.setdefault("prestart", {})[name] = payload
        self._save(db, value)

    @staticmethod
    def _inputs(value, root, *, manifest=True):
        directory = root / "code_agent_control" / value["attempt_id"]
        task = validate_task(value["prestart"]["task"]).value
        require(read_regular(directory / "code_agent_task.json") == canonical_bytes(task) and
                task["task_digest"] == value["task_digest"], "Committed task bytes changed")
        if manifest:
            workspace = validate_manifest(value["prestart"]["manifest"], task).value
            require(read_regular(directory / "workspace_manifest.json") == canonical_bytes(workspace) and
                    workspace["manifest_digest"] == value["workspace_manifest_digest"], "Committed manifest bytes changed")

    def _document(self, name, payload, source, target, checksum, hook):
        with self.coordinator.transaction(commit_boundary="external." + target) as db:
            value, _, root = self._fence(db)
            require(value["prestart"][name] == payload, "Conflicting immutable prestart input")
            directory = root / "code_agent_control" / value["attempt_id"]
            exclusive_directory(directory.parent)
            exclusive_directory(directory)
            path = directory / ("code_agent_task.json" if name == "task" else "workspace_manifest.json")
            publish_exact(path, canonical_bytes(payload), observer=self.coordinator.observer, name=hook)
            self._fence(db)
            if value["operation_phase"] == source:
                value["task_digest" if name == "task" else "workspace_manifest_digest"] = payload[checksum]
                self._phase(db, value, target)
            else:
                require(value["task_digest" if name == "task" else "workspace_manifest_digest"] == payload[checksum],
                        "Prestart document phase mismatch")
            return payload

    def commit_manifest(self, manifest):
        with self.coordinator.transaction() as db:
            value, _, root = self._fence(db)
            task = value.get("prestart", {}).get("task")
            require(task is not None and value["task_digest"] is not None, "Manifest precedes committed task")
            self._inputs(value, root, manifest=False)
            manifest = validate_manifest(manifest, task).value
            require(manifest["workspace_id"] == value["workspace_id"] and
                    manifest["managed_root_identity"] == value["managed_workspace_locator_digest"], "Foreign managed workspace")
            if "manifest" not in value["prestart"]:
                require(value["operation_phase"] == "task_committed", "Manifest publication out of order")
                self._source(db, value, root)
                self._freeze(db, value, "manifest", manifest)
        return self._document("manifest", manifest, "task_committed", "workspace_manifest_committed", "manifest_digest",
                              "external.unmaterialized_manifest")

    def reserve_aggregate(self, *, maximum_charge, timeout_seconds, config_digest):
        """Freeze the exact budget suffix before materializing either ledger file."""
        number(timeout_seconds)
        require(timeout_seconds > 0, "Invalid Backend timeout")
        request = {"maximum_charge": maximum_charge, "timeout_seconds": timeout_seconds, "config_digest": config_digest}
        with self.coordinator.transaction() as db:
            value, _, root = self._fence(db)
            require(value["operation_phase"] in ("workspace_manifest_committed", "reservation_committed", "core_contract_committed", "workspace_materialized"),
                    "Aggregate publication out of order")
            self._inputs(value, root)
            saved = value.get("prestart", {}).get("aggregate")
            if saved is None:
                require(value["operation_phase"] == "workspace_manifest_committed", "Aggregate publication out of order")
                require(self.coordinator._time().monotonic_seconds + timeout_seconds <= value["hard_deadline"],
                        "Aggregate exceeds producer deadline")
                require(maximum_charge["active_seconds"] == value["prestart"]["active_time"]["backend_maximum_seconds"],
                        "Backend active maximum differs from producer intent")
                control, execution, index = self._source(db, value, root)
                task, manifest = value["prestart"]["task"], value["prestart"]["manifest"]
                policy = loads(read_regular(root / "budget_policy.json"))
                budget = execution.projection.value["budget"]
                limits, remaining = {}, {}
                for name in ("llm_calls", "tool_calls", "verification_commands", "active_seconds"):
                    keys = ("verification_commands_per_code_attempt",) if name == "verification_commands" else (name + "_per_attempt", name + "_per_run")
                    limits[name] = min(policy["limits"][key] for key in keys)
                    remaining[name] = min(budget["dimensions"][key]["remaining"] for key in keys)
                position = budget["budget_event_index"] + 1
                record = build_record("budget", "resource_reserved", **value["run_locator"], event_index=len(execution.values) + 1,
                    previous_execution_head=execution.projection.value["execution_head"], artifact_head=index["artifact_head"],
                    artifact_event_index=index["revision"], timestamp=self.coordinator._time(),
                    budget_event_id=f"budget_event_{position:06d}", budget_event_index=position,
                    policy_version=policy["schema_version"], policy_digest=policy["policy_digest"], payload={
                        "resource_operation_id": self.producer + ":aggregate", "resource_kind": "code_backend_operation",
                        "attempt_id": value["attempt_id"], "ordinal": 1, "maximum_charge": maximum_charge,
                        "applicable_limits": limits, "remaining_before": remaining, "timeout_seconds": timeout_seconds,
                        "input_digest": task["task_digest"], "task_digest": task["task_digest"], "config_digest": config_digest,
                        "producer_operation_id": self.producer, "workspace_id": value["workspace_id"], "task_id": task["task_id"],
                        "code_task_context_digest": digest(task_context(task)), "coding_backend_kind": task["coding_backend_kind"],
                        "backend_runtime_fingerprint": task["backend_runtime_fingerprint"], "workspace_manifest_digest": manifest["manifest_digest"]}).value
                previous = read_regular(root / "execution_history.jsonl")
                content = append_record_bytes(previous, record)
                parse_ledger(content)
                saved = {"request": request, "record": record, "previous": previous.decode(), "content": content.decode(),
                         "previous_index": index, "index": {**index, "execution_head": digest(record)}, "control": control}
                self._freeze(db, value, "aggregate", saved)
            require(saved["request"] == request, "Conflicting aggregate reservation")
        return self._materialize_aggregate()

    def recover_frozen_aggregate(self):
        """Complete only the original side-effect-free aggregate publication."""
        return self._materialize_aggregate(expired=True)

    def _materialize_aggregate(self, *, expired=False):
        with self.coordinator.transaction(commit_boundary="external.reservation_committed") as db:
            value, _, root = self._fence(db, materialize_frozen_aggregate_only=expired)
            saved = value["prestart"]["aggregate"]
            record = saved["record"]
            require(saved["content"].encode() == append_record_bytes(saved["previous"].encode(), record) and
                    saved["index"] == {**saved["previous_index"], "execution_head": digest(record)} and
                    record["payload"]["resource_operation_id"] == self.producer + ":aggregate" and
                    record["payload"]["producer_operation_id"] == self.producer and
                    record["payload"]["attempt_id"] == value["attempt_id"] and
                    record["payload"]["task_digest"] == value["task_digest"] and
                    record["payload"]["workspace_manifest_digest"] == value["workspace_manifest_digest"],
                    "Frozen aggregate source changed")
            state = bounded_projection(parse_ledger(saved["content"].encode()), artifact_index=saved["index"],
                artifact_head=saved["index"]["artifact_head"], artifact_event_index=saved["index"]["revision"]).value
            if value["operation_phase"] == "workspace_manifest_committed":
                row = db.execute("SELECT value FROM run_controls WHERE run_key=?",
                                 (digest(value["run_locator"]),)).fetchone()
                require(row is not None and loads(row[0]) == saved["control"],
                        "Frozen aggregate control source changed")
            publish_exact(root / "execution_history.jsonl", saved["content"].encode(), previous=saved["previous"].encode(),
                          observer=self.coordinator.observer, name="external.aggregate_reservation")
            replace_projection(root / "artifact_index.json", canonical_bytes(saved["previous_index"]), canonical_bytes(saved["index"]),
                               observer=self.coordinator.observer)
            self._fence(db, materialize_frozen_aggregate_only=expired)
            if value["operation_phase"] == "workspace_manifest_committed":
                value["reservation_id"] = saved["record"]["payload"]["resource_operation_id"]
                value["reservation_digest"] = digest(saved["record"])
                self._phase(db, value, "reservation_committed")
                control = saved["control"]
                control.update(checkpoint_anchor_kind="external_prestart", external_owner=self.producer,
                               projection={**state, "checkpoint_head": control["manifest"]["checkpoint_head"]})
                db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?",
                           (canonical_bytes(control), digest(value["run_locator"])))
            require(value["reservation_digest"] == digest(saved["record"]), "Aggregate phase lost its reservation")
            return saved["record"]

    def commit_core(self):
        with self.coordinator.transaction(commit_boundary="external.core_contract_committed") as db:
            value, _, root = self._fence(db)
            require(value["operation_phase"] in ("reservation_committed", "core_contract_committed", "workspace_materialized"), "Core publication out of order")
            self._source(db, value, root)
            self._inputs(value, root)
            core = {"schema_version": "0.1", **value["run_locator"], **{key: value[key] for key in (
                "producer_operation_id", "parent_control_operation_id", "cycle_id", "attempt_id", "workspace_id",
                "managed_workspace_locator_digest", "task_digest", "workspace_manifest_digest", "reservation_id",
                "reservation_digest", "backend_kind", "backend_version", "hard_deadline")}}
            core["operation_contract_digest"] = digest(core)
            boundary(self.coordinator.observer, "external.immutable_core_cas", "before", core)
            if value["operation_phase"] == "reservation_committed":
                value["prestart"]["core"] = core
                value["operation_contract_digest"] = core["operation_contract_digest"]
                self._phase(db, value, "core_contract_committed")
            else:
                require(value["prestart"]["core"] == core, "Immutable core changed")
            boundary(self.coordinator.observer, "external.immutable_core_cas", "after", core)
            return core

    def materialize_workspace(self, base_repository):
        from .workspace import WorkspaceProvider, immutable_git_tree

        with self.coordinator.transaction(commit_boundary="external.workspace_materialized") as db:
            value, _, root = self._fence(db)
            require(value["operation_phase"] in ("core_contract_committed", "workspace_materialized"),
                    "Physical workspace precedes its immutable core")
            self._source(db, value, root)
            self._inputs(value, root)
            core = value["prestart"]["core"]
            require(core["operation_contract_digest"] == value["operation_contract_digest"] ==
                    digest({k: v for k, v in core.items() if k != "operation_contract_digest"}), "Immutable workspace core changed")
            manifest = value["prestart"]["manifest"]
            files = immutable_git_tree(base_repository, manifest["base_revision"])
            provider = WorkspaceProvider(self.coordinator.root / "code_workspaces")
            prior = value["prestart"].get("workspace")
            require((prior is not None) == (value["operation_phase"] == "workspace_materialized"), "Workspace phase lacks its witness")
            boundary(self.coordinator.observer, "external.workspace_materialization", "before", manifest)
            witness = provider.materialize(manifest, files, lambda: self._fence(db), witness=prior)
            boundary(self.coordinator.observer, "external.workspace_materialization", "after", witness)
            self._fence(db)
            if prior is None:
                value["prestart"]["workspace"] = witness
                self._phase(db, value, "workspace_materialized")
            return witness
