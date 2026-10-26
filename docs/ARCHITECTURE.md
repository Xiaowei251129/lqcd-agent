# Architecture

`cli.py` parses commands without importing the graph. `runtime.py` assembles one `CanonicalProductRuntime`; `demo/server.py` invokes the same CLI. `science.py` adapts the deterministic planning, analysis and reviewer modules to the canonical Agent port. `code_agent/backend.py` defines the sole Code backend interface; the bundled backend is Fake.

The trusted control plane owns Run identities, phases, leases, idempotency, budget, cancellation and progression. Agents return domain facts. They cannot assign control authority. LangGraph routes over committed transitions; its cursor is not a second persistence authority.

Coordinator SQLite is the authority for control operations. Execution/artifact ledgers and checkpoint manifests retain their existing, validated roles in replay and recovery. They have not been collapsed into an untested storage rewrite. Reports and memory classification derive from registered evidence. Scientific workspace members are hash-bound before reuse.

The current protocol is `contracts/control.json`; `_generated_protocol.py` is its immutable generated runtime projection. No generation step imports test code or old ticket files. `_build_manifest.json` records application and graph identities once per source build; invocation does not scan the package tree. Demo-only edits do not alter control compatibility.

Deployment values live in `configs/storage.json`. Admission verifies the owned private root, mount and locking options, minimum SQLite runtime and same Host boot. Actual WAL/FULL/foreign-key checks remain. The default temporary parent remains the user-selected Lustre directory.

Only current-version Runs are accepted. There is no old source reader, legacy graph, Codex handoff engine, historical acceptance matrix or independent demo workflow. Numerical benchmarks exercise reusable analysis programs; the integration tests exercise actual processes and the canonical workflow.
