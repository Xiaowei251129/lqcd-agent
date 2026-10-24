"""Closed semantic traces with a deliberately narrow ephemeral allowlist."""
from .strict_json import keys, require, canonical, text

TEXT_FIELDS = (
    "event", "physical_node", "attempt_kind", "stage", "run_id", "parent_run_id", "cycle_id",
    "attempt_id", "transition_id", "operation_id", "external_operation_id", "pause_id", "request_id",
    "response_id", "grant_id", "reservation_id", "workspace_id", "capability_id", "owner",
    "status", "phase", "source", "target", "route", "trigger_class", "guard", "outcome",
    "execution_head", "artifact_head", "checkpoint_head", "policy_digest", "result_digest",
    "task_digest", "manifest_digest", "seal_digest", "bundle_digest", "analysis_spec_digest",
    "base_digest", "effective_tree_digest", "run_status", "domain_status", "current_attempt_id",
    "current_operation_id", "binding_digest",
)
INT_FIELDS = ("index", "phase_revision", "lease_epoch", "generation", "cycle_count", "attempt_count", "transition_count")
BOOL_FIELDS = ("guard_passed", "accepted", "protected", "started")
ARRAY_FIELDS = ("budget", "artifacts", "invariants")
EPHEMERAL = {"timestamp", "duration", "output_root", "workspace_path", "process_id", "opaque_checkpoint",
             "provider_job", "provider_thread", "provider_session"}
FIELDS = set(TEXT_FIELDS + INT_FIELDS + BOOL_FIELDS + ARRAY_FIELDS)


def event(name, **values):
    result = {key: None for key in TEXT_FIELDS + INT_FIELDS + BOOL_FIELDS}
    result.update({key: [] for key in ARRAY_FIELDS})
    result.update(values)
    result["event"] = name
    validate_event(result)
    return result


def validate_event(value):
    require(type(value) is dict, "trace", "event")
    require(set(value) in (FIELDS, FIELDS | {"ephemeral"}), "trace", "fields")
    for key in TEXT_FIELDS:
        require(value[key] is None or type(value[key]) is str, "trace", key)
    text(value["event"], "trace", "event")
    for key in INT_FIELDS:
        require(value[key] is None or (type(value[key]) is int and value[key] >= 0), "trace", key)
    for key in BOOL_FIELDS:
        require(value[key] is None or type(value[key]) is bool, "trace", key)
    require(type(value["invariants"]) is list, "trace", "invariants")
    require(all(type(x) is str and x for x in value["invariants"]), "trace", "invariants")
    require(len(set(value["invariants"])) == len(value["invariants"]), "trace", "invariants")
    for key, fields in (("budget", {"dimension", "used", "remaining"}), ("artifacts", {"slot", "artifact_id", "digest", "current", "protected"})):
        require(type(value[key]) is list, "trace", key)
        seen = []
        for item in value[key]:
            keys(item, fields, key)
            if key == "budget":
                text(item["dimension"], key, "dimension")
                for amount in ("used", "remaining"):
                    require(item[amount] is None or (type(item[amount]) in (int, float) and item[amount] >= 0), key, amount)
                seen.append(item["dimension"])
            else:
                for field in ("slot", "artifact_id", "digest"):
                    text(item[field], key, field)
                for field in ("current", "protected"):
                    require(type(item[field]) is bool, key, field)
                seen.append(item["artifact_id"])
        require(len(seen) == len(set(seen)), "trace", key)
    if "ephemeral" in value:
        require(type(value["ephemeral"]) is dict and set(value["ephemeral"]) <= EPHEMERAL, "trace", "ephemeral")
        canonical(value["ephemeral"])
    canonical(value)


def normalize(trace, *, binding=None, expected=False):
    require(type(trace) is dict, "trace", "object")
    version = trace.get("schema_version")
    require(version in ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11", "0.12", "0.13"), "trace", "schema")
    require(not (expected and version == "0.13"), "trace", "raw_only_version", "invalid_evidence")
    if not expected and version == "0.12":
        require(binding is None or binding.get("schema_version") != "0.2", "trace", "scoped_source_required", "invalid_evidence")
    if version == "0.1":
        keys(trace, {"schema_version", "events"}, "trace")
    else:
        representation = "semantic_expected" if expected else "raw_with_proof"
        fields = {"schema_version", "representation", "events"} | (set() if expected else {"proof"})
        keys(trace, fields, "trace")
        require(trace["representation"] == representation, "trace", "representation", "invalid_evidence")
    require(type(trace["events"]) is list, "trace", "events")
    events = []
    for item in trace["events"]:
        validate_event(item)
        events.append({key: value for key, value in item.items() if key != "ephemeral"})
    if version == "0.1":
        return {"schema_version": "0.1", "events": events}
    if not expected:
        if version in ("0.12", "0.13"):
            from .fault_source_trace import project
            events = project(events, trace["proof"], binding, scoped=version == "0.13")
        elif version == "0.11":
            from .unconsumed_code_final_trace import project
            events = project(events, trace["proof"], binding)
        elif version == "0.10":
            from .ordinary_publication_prefix_trace import project
            events = project(events, trace["proof"], binding)
        elif version == "0.9":
            from .prior_code_evidence_trace import project
            events = project(events, trace["proof"], binding)
        elif version == "0.8":
            from .product_failure_trace import project
            events = project(events, trace["proof"], binding)
        elif version == "0.7":
            from .ordinary_maximum_trace import project
            events = project(events, trace["proof"], binding)
        elif version == "0.6":
            from .ordinary_trace import project
            events = project(events, trace["proof"], binding)
        elif version == "0.5":
            from .a05_trace import project
            events = project(events, trace["proof"], binding)
        else:
            from .trace_proof import project
            events = project(events, trace["proof"], binding, version=version)
    return {"schema_version": "0.12" if version == "0.13" else version, "representation": "semantic_expected", "events": events}


def compare(actual, expected, *, binding=None):
    require(canonical(normalize(actual, binding=binding)) == canonical(normalize(expected, expected=True)),
            "trace", "exact", "invalid_evidence")
