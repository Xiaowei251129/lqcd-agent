# Architecture

`cli.py` parses commands without importing the graph. `runtime.py` assembles one `CanonicalProductRuntime`; `demo/server.py` invokes the same CLI. `science.py` adapts planning, numerical analysis and review to the canonical Agent port, with explicit Responses planning/review in live mode. `code_agent/backend.py` defines the sole Code backend interface, implemented by the offline Fake and application-owned Codex SDK backends.

The trusted control plane owns Run identities, phases, leases, idempotency, budget, cancellation and progression. Agents return domain facts. They cannot assign control authority. LangGraph routes over committed transitions; its cursor is not a second persistence authority.

Provider-backed roles serialize the entire user context as compact JSON within the existing 6,000-character limit. An oversized context is rejected before provider invocation with `context_limit_exceeded`; no task, evidence or output contract is silently dropped. The existing role failure paths persist the error, with a null request/response in the trace when no request was built. The coordinator retains its critical/pending human-approval behavior on such a failure.

Canonical scientific review always requires human confirmation. Its adapter explicitly emits Host diagnostic `risk=high` and `human_need=approval`, preserving the existing floor independently of model confidence or extra report fields. The Reviewer schema contains scientific findings and confidence, not a control `risk_level`; the adapter does not consume that absent field.

Coordinator SQLite is the authority for control operations. Execution/artifact ledgers and checkpoint manifests retain their existing, validated roles in replay and recovery. They have not been collapsed into an untested storage rewrite. Reports and memory classification derive from registered evidence. Scientific workspace members are hash-bound before reuse.

The current protocol is `contracts/control.json`; `_generated_protocol.py` is its immutable generated runtime projection. No generation step imports test code or old ticket files. `_build_manifest.json` records application and graph identities once per source build; invocation does not scan the package tree. Demo-only edits do not alter control compatibility.

Linux deployment values live in `configs/storage.json`. Admission verifies the owned private root, mount and locking options, minimum SQLite runtime and same Host boot. macOS uses the existing native local-filesystem profile and `/private/tmp` execution parent. Actual WAL/FULL/foreign-key checks remain. Host clock epochs use the OS boot identity across CLI invocations; coding-worker termination verifies the same boot and process start identity before signalling the process group.

Only current-version Runs are accepted. There is no old source reader, legacy graph, Codex handoff engine, historical acceptance matrix or independent demo workflow. Numerical benchmarks exercise reusable analysis programs; the integration tests exercise actual processes and the canonical workflow.
