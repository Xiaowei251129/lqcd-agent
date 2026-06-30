# Tickets

## Purpose

This file is the ticket index, active queue, and compact status ledger for the project. It does not replace the detailed phase prompts in [CODEX_BUILD_PLAN.md](CODEX_BUILD_PLAN.md) or the current implementation snapshot in [REPO_CURRENT_STATE.md](REPO_CURRENT_STATE.md).

Every ticket should follow the reusable contract in [PROMPT_PLAYBOOK.md](PROMPT_PLAYBOOK.md), including the global stale-documentation scan before final response.

## Active Ticket

No active implementation ticket is open. Phase 11 remains deferred until raw-data
readiness and explicit authorization.

## Completed Summary

- Pre-phase0: source-of-truth discovery, scope lock, and documentation baseline completed.
- Phase 0: repository skeleton, docs skeleton, placeholder configs, and import smoke test completed.
- Phase 1: real LangGraph `StateGraph` mock runtime, routing, checkpoint metadata, and CLI skeleton completed.
- Phase 2: standalone deterministic Method Planner completed.
- Phase 2B: Method Planner graph integration completed.
- Phase 3: file-based Codex Handoff node, task-packet validation, and test-status handoff completed.
- Phase 4: Analysis Engineer, safe command runner, output validator, and provenance manifest completed.
- Phase 5: Scientific Reviewer diagnostics for correlator, fit, and matrix-element sections completed.
- Phase 6: Decision Coordinator risk rubric completed.
- Phase 6 maintenance: outputs policy clarification, timestamp default run ids, protected-artifact reuse guard, stale-documentation scan rule, and ticket-ledger cleanup completed.
- Phase 7: Human Approval Gate completed; high and critical risk outcomes now generate approval packets and wait for structured human decisions.
- Phase 8: Memory, Final Report, and Synthetic Evaluation Harness completed; dedicated memory/report modules now write `memory_update.json` and `final_report.md`, and synthetic good, ambiguous, and bad eval cases write `evaluation_summary.csv`.
- Phase 9: Golden Example and Productization completed; the `l64c64a076_m140` golden mock demo writes read-only provenance, high-risk approval artifacts, pending memory, and a final report through one demo command.
- Phase 7-9 maintenance: decision-route audit fields, approved-decision report text, evaluation cleanup guard, and documentation synchronization completed.
- Phase 9 GitHub-ready cleanup: ignored historical `outputs/` artifacts, `.DS_Store`, Python caches, pytest cache, and egg-info cleanup completed.
- Independent Git repository setup: initialized `lqcd-agent` as its own repository, committed the Phase 9 baseline, and pushed `main` to `git@github.com:Xiaowei251129/lqcd-agent.git`.
- Phase 10: Provider abstraction and secure dry-run configuration completed; OpenAI and DeepSeek configs load without live calls, `.env` handling preserves exported values, and deterministic mock provider tests remain the default.
- Phase 10B: Provider-backed agent wiring completed; Method Planner, Scientific Reviewer, and Decision Coordinator can use explicit provider-backed structured output through runner injection or graph `--llm-provider-config`, while deterministic paths remain the default.
- Phase 10B safety-floor hardening: provider-backed reviewer and decision paths now use bounded artifact summaries, and provider decisions cannot downgrade severe local evidence into low-risk accepted memory.
- Phase 10C: Provider-backed advisor-demo scenario benchmark completed on 2026-06-23 and live OpenAI-compatible provider demo verification completed on 2026-06-30; `evaluation/synthetic_benchmarks/` contains scenario inputs, instructor-only expected behavior, synthetic fixtures, demo/full case sets, a mock-provider runner, per-case demonstration checklists, `synthetic_rehearsal_summary.md`, optional live-provider `advisor_demo_report.md` generation, and an exact-allowlisted statistical Analysis Engineer benchmark command.

## Later Backlog

- Phase 11: read-only raw-data manifests and curated evaluation case library after Phase 10C and explicit data readiness.

## Cleanup / Policy Tickets

### Output Hygiene and Cleanup

Status: completed for Phase 9 GitHub-ready cleanup.

Goal: clean ignored local artifacts only after explicit authorization.

Allowed cleanup candidates:

- ignored historical `outputs/` run directories
- `.DS_Store`
- `__pycache__/`
- `.pytest_cache/`
- `*.egg-info/`

Do not delete:

- `outputs/.gitkeep`
- future `evaluation/reference_outputs/`
- future `evaluation/expected_behavior/`
- `accepted_results/`
- human decision files
- `raw_data/`

This ticket should also verify that future smoke tests use `/private/tmp/...` or a unique `--run-id` unless a repo-local demo output is explicitly desired.

### Independent Git Repository Setup

Status: completed.

Goal: initialize `lqcd-agent` as an independent Git repository and prepare a GitHub push only after explicit user confirmation.

Completed outcome: `lqcd-agent` is rooted at `/Users/chengxiaowei/Desktop/LQCD/lqcd-agent`, `main` tracks `origin/main`, and `origin` points to `git@github.com:Xiaowei251129/lqcd-agent.git`. Do not use the parent repository under `/Users/chengxiaowei` for future `lqcd-agent` commits or pushes.
