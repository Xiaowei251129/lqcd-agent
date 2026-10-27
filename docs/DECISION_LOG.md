# Engineering decisions

Milestone status belongs in [Current state](REPO_CURRENT_STATE.md).

## 2026-10-27 — one scientific validator and one publication path

Use the same Host scientific diagnostics in deterministic and provider review. Limit model proposals to interpretation and additive findings; preserve numerical warnings and their confidence ceiling even when model generation fails. Pass validated remediation/history through the existing context bundle, retaining one model call and the current context limit.

Delete unused direct artifact writers and the legacy provider-config factory instead of retaining parallel execution paths. Application assembly owns credentials/live activation; roles accept providers. Reuse immutable ledger snapshots only within a single read or journal validation, refresh after effects, and retain all control fencing and exact publication checks. No global replay cache, new persistence owner, retrieval loop or permission change is introduced. Audit, removed paths and measurements are in the [maintenance record](maintenance/ARCHITECTURE_SIMPLIFICATION.md).

## 2026-10-27 — bounded engineering delivery

Keep the canonical control protocol, permissions, human-confirmation floor and SQLite durability profile. Move deployment resources into the installed package; bind execution to an explicit owned workspace. Use one program descriptor for selection, input mappings and model schemas, and isolate integration examples from scientific assembly. Share closed database schema validation with a read-only inspection path. Keep portable terminal evidence archives separate from database backup and Run recovery, with no extraction, migration or automatic deletion. These choices remove duplicate mappings and source-tree assumptions without introducing another execution or persistence authority. Audit and verification are in the [maintenance record](maintenance/ENGINEERING_DELIVERY.md).

## 2026-10-27 — scientific evidence and minimal model contracts

Bind data identity to immutable Run inputs and to the exact stream consumed by analysis. A digest captured after computation could describe a replacement file, so manifests reuse the observed input record. Explicit absence is also frozen; replay cannot silently admit newly appearing data.

Keep model proposals separate from Host-owned artifact identity and execution metadata. Share one schema between provider output constraints and validation, using `$defs` rather than repeating record definitions. Remove the old LLM Coordinator, executable-mapping repair path, normalization advisories and obsolete tests. Retain the deterministic Coordinator, human-confirmation floor and immutable control protocol.

Store one context evidence bundle per role request, with views over explicitly supplied sources and verified local section reads. Preserve all scientific warnings and task constraints within the existing outbound limit; keep operational scope lists and command logs local. This uses the existing artifact lifecycle without extra model calls, new permission knobs or automatic cross-Run memory. Offline measurements support schema/context simplification; the current microsecond numerical workload does not justify a result cache. No API cache configuration, billing assumptions, concurrency changes or durability relaxation were introduced. Details are in the [maintenance record](maintenance/RESEARCH_EVIDENCE_AND_CONTEXT.md).
