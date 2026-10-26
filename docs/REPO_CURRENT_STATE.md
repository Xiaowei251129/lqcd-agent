# Current state

Updated 2026-10-26. This is the sole milestone record for the current lightweight repository.

- Current protocol extracted; old tickets, correction/completion records, acceptance matrices, expected traces and test-evidence framework removed.
- One canonical engine powers the current CLI, local demo and deterministic scientific case adapter. Old graph and Codex handoff paths are deleted. Only current Run sources are supported.
- Independent local Python/SQLite runtime and virtual environment are installed; dependencies are pinned. Protocol generation no longer imports tests. Build identity is generated once rather than scanning runtime source per invocation.
- Storage deployment values are configurable; private-root, locking, WAL/FULL, permission and Host-boot boundaries remain. Control ledgers/checkpoints were retained in their existing roles rather than rewritten speculatively.
- Current qualification passed all **93 distinct tests**: the first full attempt passed 90 and exposed three subprocess import failures; after the sole runner-path fix, those three passed in 2.86 seconds. The 90 passing tests were not repeated. The initial full attempt took 266.59 seconds and remains recorded as failed; this is a combined qualification, not a claim of a second fresh full run.
- The current numerical benchmark passed all **nine cases**. Actual JUnit/result paths, source identities, exact runner repair and build-manifest binding are in `check-results/qualification.json`. The first full-attempt pointer remains `check-results/integration.json`; the latest targeted repair is `check-results/latest.json`.
- CLI help measured about 0.046 seconds / 71 imported modules with import profiling, versus about 2.04 seconds / 974 modules before migration. These are single samples of help startup, not overall workflow speed claims.
- Delivery targets the existing `xgao` branch. Git history is retained to preserve other branches; the original checkout and bundle remain separate. Service-side publication requires the actual repository URL.
- Real Code/provider integration, operational production timing and raw-data-backed scientific acceptance remain future work. Bundled workflows are mock/deterministic.
