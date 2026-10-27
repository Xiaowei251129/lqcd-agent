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

The checkout's own Python 3.12.7 / SQLite 3.53.0 runtime and `.venv` are ignored local dependencies. The runtime was copied independently, its SQLite loader path relocated and checked; site packages were installed from exact pins, not linked to the old environment. Standard console scripts and `python -m lqcd_agent` use the installed package. Reproduce dependencies with `python -m pip install -r requirements.lock` and `python -m pip install --no-deps --no-build-isolation -e .`; set `TMPDIR` to the approved Lustre parent first. Supply `LQCD_AGENT_STORAGE_CONFIG` for installations outside this source checkout.

Deploy on qualified storage. Do not use a live SQLite file as a cross-node shared database, loosen locking or synchronization, or copy a live database as a backup. Use the coordinator's consistent backup operation. Admission configuration is operator-owned, not a caller-provided output path.

Live qualification is explicit and separate from offline pytest: `check-results/live-codex.json` records the bounded coding example, while `live-provider-admission.json` records Responses planning and the expected missing-implementation pause. The broader scientific-workflow attempt remains separately marked failed; Analysis/reviewer were not executed there. Ordinary test runs do not read application credentials or start paid SDK jobs. Use the commands and boundaries in the README for an operator-authorized live check.
