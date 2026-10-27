# Engineering decisions

Milestone status belongs in [Current state](REPO_CURRENT_STATE.md).

## 2026-10-27 — bounded engineering delivery

Keep the canonical control protocol, permissions, human-confirmation floor and SQLite durability profile. Move deployment resources into the installed package; bind execution to an explicit owned workspace. Use one program descriptor for selection, input mappings and model schemas, and isolate integration examples from scientific assembly. Share closed database schema validation with a read-only inspection path. Keep portable terminal evidence archives separate from database backup and Run recovery, with no extraction, migration or automatic deletion. These choices remove duplicate mappings and source-tree assumptions without introducing another execution or persistence authority. Audit and verification are in the [maintenance record](maintenance/ENGINEERING_DELIVERY.md).
