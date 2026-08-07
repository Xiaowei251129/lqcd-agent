# Architecture

## Overview

The runtime architecture is a LangGraph `StateGraph` with five core agents and two support nodes. Early phases may use deterministic mock node bodies, but the node names, state fields, artifact contracts, checkpoint behavior, and routing conditions must match this architecture.

The graph exists to coordinate auditable work. It is not a notebook wrapper and not an autonomous scientific decision maker.

## Graph Nodes

Core agents:

- Method Planner Agent
- Codex Handoff Node
- Analysis Engineer Agent
- Scientific Reviewer Agent
- Decision Coordinator Agent

Support nodes:

- Human Approval Gate
- Memory and Report Node

## Initial Runtime Skeleton

The current implementation wires a real LangGraph `StateGraph` with deterministic bodies or modules for:

- Method Planner Agent
- Codex Handoff Node
- Analysis Engineer Agent
- Scientific Reviewer Agent
- Decision Coordinator Agent
- Human Approval Gate
- Memory and Report Node

The Codex Handoff Node is file-based by default: it reads `coder_task_packet.yaml`, `tests_status.json`, and `code_change_summary.md`. When the graph is run with explicit automatic handoff enabled, it may invoke the local Codex CLI worker to produce those handoff artifacts before continuing. The Human Approval Gate is also file-based: it writes an approval packet and reads `approval_packet/07_human_decision.yaml`, but it never rewrites human decisions. The current runtime uses deterministic agents by default and calls an LLM provider only when an explicit provider config is supplied.

Phase 2 added a standalone deterministic Method Planner module. Phase 2B wired that module into the graph method planner node. Phase 3 wired the file-based Codex Handoff path into `code_needed=true` and code-failure retry routes. Phase 7 wired high and critical risk outcomes into the Human Approval Gate. Phase 8 replaced the placeholder Memory and Report behavior with dedicated memory and final-report modules. Phase 9 added the conservative `l64c64a076_m140` golden mock demo, which uses sibling example files as read-only provenance and keeps analysis output synthetic. In the current runtime, planner `code_needed=false` continues to Analysis Engineer, planner `needs_more_info` stops safely as `pending` with structured state errors, and planner `code_needed=true` routes to Codex Handoff. If required handoff result files are missing, Codex Handoff stops safely as `pending`.

## Primary Flow

```text
START
  -> Method Planner Agent
  -> if code_needed:
       Codex Handoff Node
       -> tests pass: Analysis Engineer Agent
       -> tests fail and retry_count < max_retry: Codex Handoff Node
       -> tests fail and retry_count >= max_retry: Decision Coordinator Agent
     else:
       Analysis Engineer Agent
  -> if run_success:
       Scientific Reviewer Agent
     else if failure_type == code:
       Codex Handoff Node
     else:
       Method Planner Agent or Decision Coordinator Agent
  -> Decision Coordinator Agent
  -> if risk_level in high, critical:
       Human Approval Gate
     else:
       Memory and Report Node
  -> END
```

Human Approval Gate routes:

- `approve_with_conditions` -> Memory and Report Node
- `approve_rerun` -> records Analysis Engineer rerun intent and stops pending
- `request_code_change` -> Codex Handoff Node
- `reject_or_hold` -> Memory and Report Node
- no decision -> Memory and Report Node writes pending memory/report artifacts, with accepted memory still blocked until a valid human decision

## Checkpointing and Context Boundary

Checkpointing and LLM context are separate concerns.

- Full graph state is persisted through a SQLite checkpoint backend for local CLI runs and through `MemorySaver` for unit and smoke tests.
- The checkpoint database must live under `<output_root>/<case_id>/<run_id>/checkpoints/` once outputs exist.
- `checkpoint_thread_id` must be stable for a given `case_id` and `run_id`.
- LLM nodes receive only selected state fields and artifact summaries.
- Long event logs must be summarized before being passed to LLM nodes.
- Routing must never depend on truncated or summarized free-form text.
- `graph_state.json` is written after meaningful node completions and route decisions so local artifacts can be inspected without reading checkpoint internals.

## Command Boundary

The MVP allows only allowlisted mock, test, smoke, and internal statistical benchmark commands. The Phase 9 golden demo uses `mock:write_golden_example_matrix_elements`, which writes synthetic matrix-element evidence with read-only golden-example provenance and an intentional severe demo flag. Phase 10C generated cases use the exact-allowlisted `analysis:run_synthetic_benchmark:<scenario_path>` command, which runs a weighted log-linear synthetic fit and writes support artifacts plus a validated matrix-element JSON output. Every command execution must record command, working directory, return code, timeout, stdout/stderr summary, and output paths in the manifest.

## Output Boundary

Actual run artifacts are written under `<output_root>/<case_id>/<run_id>/`. Repo-local `outputs/` is an ignored actual-run output root, not a reference-output location. Future curated evaluation baselines live under `evaluation/reference_outputs/`, with expected behavior under `evaluation/expected_behavior/`.

When the CLI is invoked without `--run-id`, it generates a timestamp run id. When an explicit run id points at a directory with completed or decision artifacts, the CLI refuses to reuse that run directory. Resume and force overwrite behavior remain deferred to future explicit tickets.

## Provider Boundary

The default provider behavior is deterministic and network-free. Phase 10 adds a provider abstraction and secure dry-run configuration for OpenAI and DeepSeek. Phase 10B wires Method Planner, Scientific Reviewer, and Decision Coordinator to provider-backed structured output through the explicit `llm_provider_config_path` state field and CLI `--llm-provider-config` option. If the option is omitted, the graph uses the existing deterministic agent paths. Provider output must pass strict JSON schema validation before it can write artifacts or affect routing; invalid output writes a structured failure artifact and routes only through conservative structured fields. Phase 10D writes non-secret provider request/response audit records under each run's `llm_calls/` directory and records those files in the manifest and final report.

Provider-backed decisions also obey a local evidence policy. Before the Scientific Reviewer and Decision Coordinator call a provider, they pass bounded artifact summaries rather than raw numeric data. Before a provider-backed decision is accepted, the Decision Coordinator computes the deterministic risk implied by local artifacts. Provider output may add structured reasoning, but it cannot lower high or critical local evidence, severe review warnings, failed runs, or unusable artifacts into low-risk accepted memory. When provider output is lower than the local floor, `decision_log.json` records a `provider_safety_floor` reason and routes through the conservative local risk path. Provider output also cannot force Human Gate from unsupported non-severe evidence; context-only or ungrounded non-severe reviewer cautions are filtered out of route-changing warning evidence.

The Phase 10D local console discovers YAML and JSON cases, previews registered-program or command-based analysis routes, lets the operator select a configured runtime provider, blocks live providers without their explicit opt-in environment variable, and shows the equivalent CLI command before execution. Its default output root is the ignored repo-local `outputs/` directory.

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [State Schema](STATE_SCHEMA.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
