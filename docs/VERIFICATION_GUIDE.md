# Verification

| Intent | Command |
| --- | --- |
| Core protection | `python scripts/check.py` |
| Affected behavior | `python scripts/check.py tests/path.py::test_name` |
| Integration | `python scripts/check.py --integration` |
| Numerical benchmark | `python -m lqcd_agent.benchmark` |

Core has 12 critical checks. Integration runs the current scientific, command-policy, durability, storage and CLI tests once, then nine numerical benchmark cases. There are no historical B05 test-count or proof-chain requirements. Old results are not reused as evidence for this version.

A passing check requires a nonempty selection, actual zero exit and JUnit without failures, errors or skips. Reports and raw JUnit go into a fresh root under the configured Lustre parent. `check-results/latest.json` and `check-results/integration.json` point to the latest completed targeted/core check and full integration attempt. `check-results/qualification.json` records the current reviewed selections and any repairs; an original failed run is never relabelled. Affected checks and a full integration run have distinct scopes. Integration binds one current source digest before and after execution. Passed tests clean only their own fresh roots; failed roots are retained for diagnosis.

For ordinary code edits, run the affected tests. Do not rerun the complete suite to update a document. For docs, check relative links and `git diff --check`. Tests are maintained according to behavior and risk, not a required case count.

`tests/test_prompt_context.py` checks the exact context boundary, lossless Unicode/escaping, and rejection before provider invocation for Planner, Reviewer and Coordinator. Oversized requests retain structured errors and no fabricated request/response. `tests/test_science_integrity.py` checks that an absent or untrusted Reviewer risk field cannot bypass Host confirmation; `tests/test_workflow.py` verifies the actual canonical scientific Run remains paused with pending approval and no accepted terminal result. See the [context and confirmation maintenance record](maintenance/PROMPT_CONTEXT_AND_REVIEW_POLICY.md).

The checkout's Python 3.12 environment and `.venv` are ignored local dependencies. Standard console scripts and `python -m lqcd_agent` use the installed package. Reproduce dependencies in a fresh `.venv` with `python -m pip install -r requirements.lock` and `python -m pip install --no-deps --no-build-isolation -e .`; set `TMPDIR` to the approved execution parent first (`/private/tmp` on macOS, the configured Lustre parent on OLCF). Supply `LQCD_AGENT_STORAGE_CONFIG` for installations outside this source checkout. The local macOS qualification uses Python 3.12.7 and SQLite 3.53.0; its site packages are independently installed from the lockfile.

Deploy on qualified storage. Do not use a live SQLite file as a cross-node shared database, loosen locking or synchronization, or copy a live database as a backup. Use the coordinator's consistent backup operation. Admission configuration is operator-owned, not a caller-provided output path.

Live qualification is explicit and separate from offline pytest. The local `check-results/live-codex-local.json` records the bounded coding example, and `live-scientific-local.json` records real Responses planning/review with registered effective-mass analysis on explicit synthetic calibration input. The scientific Run awaits a human decision after review. Earlier ignored OLCF reports were not transferred with Git; the original missing-generator attempt remains recorded as a distinct failure, not overwritten by the new case. Ordinary test runs do not read application credentials or start paid SDK jobs. Use the commands and boundaries in the README for an operator-authorized live check.

Local qualification details and evidence locations are in the [macOS maintenance record](maintenance/LOCAL_MACOS_QUALIFICATION.md). macOS checks exercise its native profile; Linux-only Lustre admission assertions are not exercised on Darwin. A scientific workflow reaching Human Gate still requires a business decision; a successful review artifact or synthetic numerical oracle does not supply that decision.
