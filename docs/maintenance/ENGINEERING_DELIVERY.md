# Engineering delivery work

The operator authorized four work packages on 2026-10-27. This record captures the audit, implementation boundaries and verification; milestone status belongs in `docs/REPO_CURRENT_STATE.md`.

## Audit before modification

1. Delivery: runtime defaults use source-relative paths; the storage profile is outside the installed package; wheel builds do not refresh the application manifest. No versioned CI workflow or deployment diagnostic exists.
2. Assembly and contracts: every Host creates a synthetic Git repository, and every command assembles its Code host. Case and provider configuration each use a handwritten YAML subset. The capability inventory depends on source filenames; planner input mappings duplicate program metadata. Reviewer failure is not explicitly propagated by the scientific adapter.
3. Observation and performance: status queries assemble the runtime; model traces do not carry latency or provider request identity. No reproducible CLI performance measurement exists. Preserve the existing integrity checks and authority rather than trading them for throughput.
4. Lifecycle: finished scientific outputs remain in temporary Host directories. A portable, verified archive for finished Runs is missing. Database backup already exists and must not be replaced by copying live SQLite files.

## Authorized implementation boundaries

- Keep the canonical graph, immutable control declarations, Host/Run ownership, permissions, Human Response validation, fencing and WAL/FULL semantics.
- Delivery: installable resources, operator workspace resolution, a diagnostic command, wheel smoke coverage and minimal offline CI.
- Assembly: isolate example fixtures, make scientific assembly independent of them, unify configuration parsing and registered program mappings, and propagate failed scientific review.
- Observation: structured local timing/provider metadata, a read path for status, and a repeatable offline performance report. No mandatory telemetry service or paid API execution.
- Lifecycle: archive terminated Runs inside their private Host, validate portable archive contents without extraction or execution, and expose clear status/next-action information. No automatic deletion, arbitrary destination write, database migration or old-Run execution path.

Remove replaced implementations; do not retain compatibility aliases or a second workflow. Each package receives affected checks, followed by one full integration run after the final source change. Platform-specific storage checks and real API qualification remain separately identified.

## Implemented changes

1. Delivery: move the unchanged storage profile into package data; regenerate wheel manifests during build; resolve the owned operator workspace independently of installation; add offline doctor and a read-only, action-pinned macOS CI workflow. Wheel smoke installs the application outside the checkout and exercises a scientific Run with pending human approval.
2. Assembly/contracts: relocate fixed example roles and sample Code preparation to `examples.py`; scientific Hosts no longer create a Git repository or Code workspace. Replace handwritten case/provider parsing with strict JSON/YAML loading, and source selection mappings/model schemas from program descriptors. The existing matrix-normalization helper now consumes registered CSV record input. Propagate failed Reviewer status while retaining Host approval/risk policy.
3. Observation: share the existing closed coordinator schema checks between writer and inspection; use read-only SQLite with cross-head/manifest validation and no executor assembly or lease renewal. Add `next_action`, provider latency and available request/response IDs, plus a fresh-process offline timing probe. These diagnostics grant no control authority.
4. Lifecycle: generate deterministic, bounded terminal evidence ZIPs inside the private Host, with source/head checks and scientific member digests. Refuse active Runs, source changes, conflicting existing bytes and unsafe bundle content. Keep sources, SQLite backup and Run recovery separate; no automatic deletion or extraction.

## Removed or merged

- Remove source-relative runtime settings so installation and the operator workspace remain independent.
- Remove unconditional example Git/Code initialization from scientific execution and queries.
- Merge planner/mock input mapping and selection logic into the program registry; remove the two duplicate CSV-header readers and fixed two-point-only model input schema.
- Replace filename-based installed capability checks and both handwritten case/provider YAML subsets with the shared `configuration.py` loader.
- Merge writer/reader closed database schema and Host-binding validation; keep the writer's existing checks and pragmas.
- Reuse one Codex job lookup implementation for backend and status inspection. No compatibility reader, legacy Run path, database migration, permissive execution branch or extra approval mode was introduced.

## Verification boundaries

Affected checks covered wheel installation, scientific assembly/input validation, Reviewer propagation, read-only status, archive admission/tampering and existing durability/backup/fencing. A separate passive Codex status fixture uses a validated receipt and the shared original job namespace, asserting no backend construction or file changes without a paid call. It also rejects a redirected backend root, preserving the check previously performed by backend construction. Initial affected failures exposed a moved import, fixture output declarations and an overstrict newly added reader file-mode assumption; the corrections preserve the original private-Host boundary and existing SQLite file modes. The final read-path audit also corrected its Codex job directory reference and centralized that fixed namespace with production assembly. Original failed reports remain separate. Cancellation was checked without credentials or an available data workspace; no existing control authorization was bypassed.

GitHub CI is configured but has not run remotely. Paid Responses/Codex qualification was not repeated for that build. Previous live evidence applies to its earlier build. The wheel smoke reuses locked third-party dependencies offline; it does not certify a new network dependency resolution or live coding deployment. Portable bundles need explicit transport to durable storage and a separately trusted SHA-256; they are not database backups, origin certificates, recoverable Runs or physics acceptance.

## Final verification — 2026-10-27

- Final integration: **133 tests passed**, no skips; **all 9 numerical benchmark cases passed**. The final result is `/private/tmp/lqcd-agent-check-tm8vpp_l/result.json`, indexed by ignored `check-results/integration.json`. The final run took 194.90 seconds. Earlier full runs and targeted reports remain separate observations.
- Application build: `38838a66b9c3caa0aa1b3563d3f327b8a4a6a5678d121cc62b90ce211c12ce09`. Integration source digest before/after: `e51fa99c0ee48ab1c1b254bc62c9ed793b1e1d642991e05335455b2ea23cb4ab`.
- Protocol generation/build-manifest checks, strict JSON/duplicate-key checks, Markdown relative links, English source comments, Python compilation into an isolated temporary bytecode root and `git diff --check` passed. No change to control declarations, dependency lock, SQLite schema/version or storage profile values. `.env` remains ignored, untracked and mode `0600`; tracked/new deliverables contain no detected API-key literals.

Fresh offline CLI processes, three samples before and three after, same local macOS deployment:

| Wall-clock operation | Baseline median | Final median |
| --- | ---: | ---: |
| Start and finish synthetic Run | 7.646 s | 7.463 s |
| Independent status query | 1.154 s | 0.188 s |

Status latency fell approximately **83.7%** in this local sample; start timings are broadly similar. Final maxima were 7.955 s / 0.191 s respectively. Existing integrity validation and write durability were retained. These small samples are not a production SLO or a scientific capability evaluation. Raw samples remain in ignored `check-results/engineering-baseline.json` and `engineering-after.json`; the timing probe retained its own completed Hosts for inspection.

The external checks at that point were remote GitHub CI and explicitly scoped real Responses/Codex qualification. Durable transport of archives remains an explicit operator action.
