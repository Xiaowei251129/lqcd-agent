# Data and security

Host code owns paths, identities, permissions, leases, transitions, resource settlement and publication. Domain outputs and backend declarations cannot grant authority. External actions need scoped authorization.

Preserve fencing, idempotency, symlink/hardlink checks, private-root ownership, SQLite WAL/FULL, foreign keys, accepted-result immutability, source digests and stop-owner checks. Replay and fork accept current validated sources only.

The application key lives in the operator workspace's ignored `.env`, owned by the operator with mode 0600. Never commit credentials. Application settings read the file without exporting secrets into child environments. An explicit `--live` opts in to paid API calls; ordinary tests and the local demo remain offline.

Codex uses its SDK-bundled runtime, a fresh private `CODEX_HOME`, API-key login and ephemeral credential storage. It does not use the interactive operator's Codex login or configuration. The model receives bounded task/file context and returns a file proposal. Shell, plugins, apps, hooks, subagents, web search and automatic project instructions are disabled; the Host supplies the task instructions. Filesystem restrictions, disabled command networking and denial of approvals remain configured. Unexpected tool activity invalidates a proposal. No unrestricted-permission fallback is provided.

The current CLI coding example only modifies `sample.py`. Host fencing, path checks, immutable base comparisons and independent syntax verification precede consumption. Its Analysis command requires an AST equivalent to `def value(): return 2` before execution and asserts the integer result. This narrow example is not an execution sandbox for arbitrary generated programs. General program execution requires qualified OS isolation; the current OLCF host disables user namespaces and cannot run Codex command sandboxes.

The local demo exposes only a fixed synthetic start action on loopback, validates browser origin, and accepts no arbitrary shell command or filesystem root.

Scientific reports must distinguish synthetic and measured inputs, record methods and provenance, and require appropriate scientific review. A passing software or numerical benchmark is not physics acceptance. Do not silently replace raw data, accepted results or failed observations to obtain a pass.

Installed resources and owned workspace resolution do not broaden code-execution permissions. The private Host remains the filesystem access boundary; existing SQLite file modes are retained. Read-only inspection shares the coordinator's exact schema and Host binding checks without opening its writer or running durability probes on the existing authority. Doctor uses a fresh private root for those probes.

Portable archives remain private inside the Host and include only closed Run evidence and its explicitly hash-bound domain members. No coordinator/checkpoint SQLite file, backend authentication home, external raw data or backend worktree is copied. The static format grants no Run execution or recovery authority. Verification never extracts members and rejects duplicate names, traversal, symlinks, unsupported file/compression types, oversized content and digest mismatches. Preserve a trusted archive digest separately; a self-consistent bundle alone does not authenticate its origin. Operator cleanup and transport to durable storage remain explicit.

Scientific input identity is frozen before execution. Dataset fingerprints and headers may appear in role context; raw CSV contents are neither placed in model messages nor copied into evidence archives. Complete supplied role context is retained locally; the Reviewer projects command logs out of its model view. References permit only digest-checked local section reads, not arbitrary model-selected filesystem paths or new external actions. Model schemas exclude Host identity and execution paths; validated proposals are materialized by the Host. Existing scientific approval, resource accounting and stop ownership remain unchanged.
