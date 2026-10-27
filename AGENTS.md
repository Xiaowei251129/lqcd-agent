# Working agreements

Build a useful LQCD research partner. Mock outputs and software checks are not evidence of physics correctness.

- Finish authorized work autonomously. Resolve reversible choices; ask only for material missing information or authorization.
- Use the smallest coherent implementation. Keep one canonical workflow and one Code backend interface.
- This checkout supports the current version only. Remove retired code, tickets, compatibility branches and obsolete tests rather than archiving them here. Do not delete version-control history without explicit authorization.
- Routine work needs no ticket, frozen hash, approval chain or duplicate completion records. Existing user authorization persists.
- Read relevant code and docs; do not ingest the entire repository by default. Comments are English; explanations use the user's language.
- Use the repository's `.venv`. Temporary files use the trusted storage profile in `src/lqcd_agent/resources/storage.json` or the operator's validated deployment profile; never fall back to `/tmp`.
- Run affected tests with `python scripts/check.py tests/path.py::test_name`. Default is the 12-check core; `--integration` runs the current suite once and the numerical benchmark. No historical acceptance mode remains.
- Add tests for meaningful behavior or defects. Do not add tests that mirror code, repeat passing selections, or expand the core for every fix.
- Preserve actual authority, fencing, idempotency, permissions, WAL/FULL durability, immutable accepted results and scientific provenance. Do not weaken behavior to obtain a pass.
- Distinguish results, skipped or unexecuted work and limitations. Model confidence is not a passing result.
- Use up to 8 CPUs for independent work when measurements justify it. Isolate mutable state; do not parallelize shared SQLite writes blindly.
- Confirm unapproved destructive/irreversible actions, external publication/contact, spending, permission expansion or incompatible migration. Reversible authorized maintenance proceeds without new process gates.
- `README.md` is the overview; `docs/REPO_CURRENT_STATE.md` is the only milestone/status record; `docs/VERIFICATION_GUIDE.md` defines verification.
- Documentation-only changes need links/diff checks. Update status when milestones change; do not maintain parallel histories.
- Done means behavior works, relevant checks passed, changes were reviewed and material limits are explicit.
