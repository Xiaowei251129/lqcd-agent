# Verification

| Intent | Command |
| --- | --- |
| Core protection | `python scripts/check.py` |
| Affected behavior | `python scripts/check.py tests/path.py::test_name` |
| Integration | `python scripts/check.py --integration` |
| Numerical benchmark | `python -m lqcd_agent.benchmark` |
| Deployment preflight | `lqcd-agent doctor` |
| Local CLI timings | `python scripts/measure_cli.py --samples 3` |
| Portable evidence check | `lqcd-agent verify-archive --archive-path /absolute/archive.zip` |

Core has 12 critical checks. Integration runs the current scientific, command-policy, durability, storage and CLI tests once, then nine numerical benchmark cases. There are no historical B05 test-count or proof-chain requirements. Old results are not reused as evidence for this version.

A passing check requires a nonempty selection, actual zero exit and JUnit without failures, errors or skips. Reports and raw JUnit go into a fresh root under the approved execution parent (`/private/tmp` on macOS, the configured Lustre parent on OLCF). `check-results/latest.json` and `check-results/integration.json` point to the latest completed targeted/core check and full integration attempt. `check-results/qualification.json` records the current reviewed selections and any repairs; an original failed run is never relabelled. Affected checks and a full integration run have distinct scopes. Integration binds one current source digest before and after execution. Passed tests clean only their own fresh roots; failed roots are retained for diagnosis.

For ordinary code edits, run the affected tests. Do not rerun the complete suite to update a document. For docs, check relative links and `git diff --check`. Tests are maintained according to behavior and risk, not a required case count.

`tests/test_prompt_context.py` checks the exact context boundary, lossless Unicode/escaping, and rejection before provider invocation for Planner, Reviewer and Coordinator. Oversized requests retain structured errors and no fabricated request/response. `tests/test_science_integrity.py` checks that an absent or untrusted Reviewer risk field cannot bypass Host confirmation; `tests/test_workflow.py` verifies the actual canonical scientific Run remains paused with pending approval and no accepted terminal result. See the [context and confirmation maintenance record](maintenance/PROMPT_CONTEXT_AND_REVIEW_POLICY.md).

The checkout's Python 3.12 environment and `.venv` are ignored local dependencies. Standard console scripts and `python -m lqcd_agent` use the installed package. Reproduce dependencies in a fresh `.venv` with `python -m pip install -r requirements.lock` and `python -m pip install --no-deps --no-build-isolation -e .`; set `TMPDIR` to the approved execution parent first (`/private/tmp` on macOS, the configured Lustre parent on OLCF). The default storage profile ships in the package; supply `LQCD_AGENT_STORAGE_CONFIG` only to select an operator-owned deployment profile. Set `LQCD_AGENT_WORKSPACE` when the operator workspace differs from the current directory. The local macOS qualification uses Python 3.12.7 and SQLite 3.53.0; its site packages are independently installed from the lockfile.

Deploy on qualified storage. Do not use a live SQLite file as a cross-node shared database, loosen locking or synchronization, or copy a live database as a backup. Use the coordinator's consistent backup operation. Admission configuration is operator-owned, not a caller-provided output path.

Live qualification is explicit and separate from offline pytest. The local `check-results/live-codex-local.json` records the bounded coding example, and `live-scientific-local.json` records real Responses planning/review with registered effective-mass analysis on explicit synthetic calibration input. The scientific Run awaits a human decision after review. Earlier ignored OLCF reports were not transferred with Git; the original missing-generator attempt remains recorded as a distinct failure, not overwritten by the new case. Ordinary test runs do not read application credentials or start paid SDK jobs. Use the commands and boundaries in the README for an operator-authorized live check.

Local qualification details and evidence locations are in the [macOS maintenance record](maintenance/LOCAL_MACOS_QUALIFICATION.md). macOS checks exercise its native profile; Linux-only Lustre admission assertions are not exercised on Darwin. A scientific workflow reaching Human Gate still requires a business decision; a successful review artifact or synthetic numerical oracle does not supply that decision.

The [engineering maintenance record](maintenance/ENGINEERING_DELIVERY.md) describes four audited packages and removed paths. `tests/test_delivery.py` builds a wheel with a deliberately stale source manifest, installs it in a fresh virtual environment and runs doctor plus a scientific case outside the source checkout. Locked third-party dependencies are reused offline; the application must come from the installed wheel. `tests/test_engineering_assembly.py` covers nested/ambiguous configuration, the registered record-input program, malformed CSV and failed-review propagation. `tests/test_inspection.py` verifies status neither constructs executors nor changes authority files; unknown schema is tested in memory. A passive Codex metadata fixture checks the shared original job directory and rejects a redirected backend root, without model calls or backend construction. `tests/test_archive.py` covers closure admission, idempotence, unchanged sources, scientific member tampering and unsafe ZIP paths/types.

The GitHub workflow pins checkout/setup actions, grants read-only repository access, installs the lock and runs offline integration on macOS. Local checks do not certify a remote CI run or OLCF admission. The CLI timing probe reports independent-process samples, median and maximum; it retains its own completed Hosts and does not call paid APIs. Small local samples measure engineering overhead, not scientific capability or a production latency SLO.

Archive verification is content/inventory checking, not a replay, origin authentication without a separately trusted digest, or physics acceptance. Archives exclude SQLite and do not replace the coordinator backup API. There is no old-Run migration, automatic cleanup, unrestricted execution or extra approval policy.
