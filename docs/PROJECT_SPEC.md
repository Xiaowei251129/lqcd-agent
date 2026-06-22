# Project Specification

## Purpose

This project builds an AI-assisted, auditable LangGraph workflow for pion quasi-DA analysis support in lattice QCD. The system helps plan routine analysis steps, run allowed mock workflows, diagnose structured synthetic matrix-element artifacts, assign risk, and produce reproducible reports.

The system does not make final physics claims. Human approval remains required for high or critical risk outcomes, accepted-result promotion, central fit choices, final systematic uncertainty choices, and paper-level claims.

## MVP Scope

The MVP focuses on a mock-only pion quasi-DA workflow:

- Input: a user physics goal and a case configuration for a synthetic pion quasi-DA case.
- Golden example: structured synthetic matrix elements versus Wilson-line separation `z` and hadron momentum `Pz`.
- Primary observables: bare and normalized matrix elements, including real/imaginary components, uncertainties, and diagnostic flags.
- Output: `method_plan.json`, mock analysis outputs, `scientific_review_report.json`, `decision_log.json`, checkpoint metadata, optional approval packet, memory update, and `final_report.md`.
- Definition of done: one command runs the mock case from configuration through final report, manifest, decision log, and checkpoint metadata.

## Data Boundary

Phase 0 through MVP may read only raw-data manifests, descriptions, and checksums. The workflow must not read real raw numeric data during the MVP. It must not write to `raw_data/` at any phase.

Synthetic evaluation cases must live outside `raw_data/`. Future raw-data-backed evaluation cases are deferred until the raw-data policy and reference-output policy are implemented.

## Non-Goals

- No implementation code in the source-of-truth documentation step.
- No repository skeleton creation before the docs are approved.
- No dependency installation during documentation work.
- No real LQCD raw numeric data ingestion in the MVP.
- No live LLM provider calls before the provider phase.
- No automated central-fit selection, final systematic uncertainty decision, accepted-result promotion, or paper-level physics conclusion.
- No custom replacement for LangGraph once graph runtime work begins.

## Success Criteria

The MVP succeeds when:

- A deterministic mock provider can drive the full graph without network access.
- The mock golden example produces structured artifacts with provenance.
- Good, ambiguous, and bad synthetic cases exercise low, medium, and high-risk behavior.
- High and critical risk outcomes must enter the Human Approval Gate before accepted memory or result promotion; they may write pending audit artifacts while waiting for a valid decision.
- Routing decisions depend on structured fields, not free-form text.
- Checkpointing preserves full graph state, while LLM-facing context receives only selected fields and summaries.

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [State Schema](STATE_SCHEMA.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
