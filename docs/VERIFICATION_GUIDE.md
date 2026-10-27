# Verification

| Intent | Command |
| --- | --- |
| Static correctness/import checks | `ruff check src tests scripts setup.py` |
| Core protection | `python scripts/check.py` |
| Affected behavior | `python scripts/check.py tests/path.py::test_name` |
| Integration | `python scripts/check.py --integration` |
| Numerical benchmark | `python -m lqcd_agent.benchmark` |
| Deployment preflight | `lqcd-agent doctor` |
| Local CLI timings | `python scripts/measure_cli.py --samples 3` |
| Portable evidence check | `lqcd-agent verify-archive --archive-path /absolute/archive.zip` |

Core has 12 critical checks. Integration runs the current scientific, command-policy, durability, storage and CLI tests once, then nine numerical benchmark cases. There are no historical B05 test-count or proof-chain requirements. Old results are not reused as evidence for this version.

A passing check requires a nonempty selection, actual zero exit and JUnit without failures, errors or skips. Reports and raw JUnit go into a fresh root under the approved execution parent (`/private/tmp` on macOS, the configured Lustre parent on OLCF). `check-results/latest.json` and `check-results/integration.json` point to the latest completed targeted/core check and full integration attempt; original failed reports retain their status. Affected checks and a full integration run have distinct scopes. Integration binds source, lock, build inputs and CI configuration before and after execution; ignored bytecode, package metadata and macOS `.DS_Store` files do not participate. Passed tests clean only their own fresh roots; failed roots are retained for diagnosis.

The runner also exports `check-results/ci-summary.json` and `ci-junit.xml`. The summary contains only selection/outcome, duration, source digest and benchmark status. Public JUnit contains case names, durations and outcome tags; it omits file paths, failure messages, captured output and private runtime references. CI uploads only these two files for seven days, including after a failed check. Detailed evidence and runtime directories remain excluded. Unit checks exercise privacy-preserving export and changes to build/CI inputs invalidating source identity.

For ordinary code edits, run the affected tests. Do not rerun the complete suite to update a document. For docs, check relative links and `git diff --check`. Tests are maintained according to behavior and risk, not a required case count.

`tests/test_prompt_context.py` checks the exact context boundary, lossless Unicode/escaping, and rejection before provider invocation for Planner and Reviewer. Oversized requests retain structured errors and no fabricated request/response. `tests/test_science_integrity.py` checks that an absent or untrusted Reviewer risk field cannot bypass Host confirmation; `tests/test_workflow.py` verifies the actual canonical scientific Run remains paused with pending approval and no accepted terminal result. See the [context and confirmation maintenance record](maintenance/PROMPT_CONTEXT_AND_REVIEW_POLICY.md).

The checkout's Python 3.12 environment and `.venv` are ignored local dependencies. Standard console scripts and `python -m lqcd_agent` use the installed package. Follow the [single environment and lock-generation procedure](../README.md#develop); install with `--require-hashes` and set `TMPDIR` to the approved execution parent first (`/private/tmp` on macOS, the configured Lustre parent on OLCF). The default storage profile ships in the package; supply `LQCD_AGENT_STORAGE_CONFIG` only to select an operator-owned deployment profile. Set `LQCD_AGENT_WORKSPACE` when the operator workspace differs from the current directory. The local macOS qualification uses Python 3.12.7 and SQLite 3.53.0.

Deploy on qualified storage. Do not use a live SQLite file as a cross-node shared database, loosen locking or synchronization, or copy a live database as a backup. Use the coordinator's consistent backup operation. Admission configuration is operator-owned, not a caller-provided output path.

Live qualification is explicit and separate from offline pytest. The local `check-results/live-codex-local.json` records the bounded coding example, and `live-scientific-local.json` records real Responses planning/review with registered effective-mass analysis on explicit synthetic calibration input. The scientific Run awaits a human decision after review. Earlier ignored OLCF reports were not transferred with Git; the original missing-generator attempt remains recorded as a distinct failure, not overwritten by the new case. Ordinary test runs do not read application credentials or start paid SDK jobs. Use the commands and boundaries in the README for an operator-authorized live check.

Local qualification details and evidence locations are in the [macOS maintenance record](maintenance/LOCAL_MACOS_QUALIFICATION.md). macOS checks exercise its native profile; Linux-only Lustre admission assertions are not exercised on Darwin. A scientific workflow reaching Human Gate still requires a business decision; a successful review artifact or synthetic numerical oracle does not supply that decision.

The [engineering maintenance record](maintenance/ENGINEERING_DELIVERY.md) describes four audited packages and removed paths. `tests/test_delivery.py` builds a wheel with a deliberately stale source manifest, installs it in a fresh virtual environment and runs doctor plus a scientific case outside the source checkout. Locked third-party dependencies are reused offline; the application must come from the installed wheel. `tests/test_engineering_assembly.py` covers nested/ambiguous configuration, the registered record-input program, malformed CSV and failed-review propagation. `tests/test_inspection.py` verifies status neither constructs executors nor changes authority files; unknown schema is tested in memory. A passive Codex metadata fixture checks the shared original job directory and rejects a redirected backend root, without model calls or backend construction. `tests/test_archive.py` covers closure admission, idempotence, unchanged sources, scientific member tampering and unsafe ZIP paths/types.

The GitHub workflow pins actions, grants read-only repository access, checks deterministic lock generation and installed dependencies, and runs Ruff plus offline integration on macOS. New pushes cancel older checks for the same workflow/ref. A separate Ubuntu job checks source/generated consistency, the numerical kernel and wheel construction using runner-owned temporary storage; it never opens an application authority or claims Lustre admission. Pure-contract tests run without site packages against an unavailable storage profile, and an architecture check prohibits control-to-graph imports. Local checks do not certify remote CI or OLCF admission. The CLI timing probe reports independent-process samples, median and maximum; it retains measured Hosts and does not call paid APIs. Small samples measure local engineering overhead, not scientific capability or a production latency SLO.

Archive verification is content/inventory checking, not a replay, origin authentication without a separately trusted digest, or physics acceptance. Archives exclude SQLite and do not replace the coordinator backup API. There is no old-Run migration, automatic cleanup, unrestricted execution or extra approval policy.

## Scientific evidence and context maintenance

`tests/test_research_evidence.py` verifies exact consumed-byte provenance, changed-data refusal before calculation, explicit missing-input identity, and inherited input identity during a real scientific Replay. It also checks that models select program IDs while the Host creates mappings, rejects forged identities/paths and duplicate/unknown selections, preserves pending proposals, and supports digest-checked context section reads. Existing workflow, durability, cancellation, archive and credential tests remain part of integration.

Read a role's evidence catalog from its `llm_calls/<role>.json` request message. In Python:

```python
from lqcd_agent.llm.context import read_context_evidence

# output_dir is the scientific role's recorded domain output directory.
# catalog is the evidence_catalog from that role's request JSON.
source = read_context_evidence(output_dir, catalog, 'repo_inventory', fields=['analysis_programs'])
```

Planner sources are `user_goal`, `case_config`, `repo_inventory` and `research_context`. Reviewer sources include the complete supplied `method_plan`, `run_result`, Host `review_evidence`, review scope and `research_context`. The scientific adapter supplies remediation and bounded relevant history in `research_context`; standalone callers may omit it. A referenced digest identifies one immutable bundle; missing sections, changed bytes, symlinks and hardlinks are rejected. This helper reads local evidence and grants no execution, approval or control authority. Model messages contain selected views, not command logs or a general filesystem-reading tool. Archives include these bundles through the existing scientific member inventory.

Architecture regressions compare deterministic and optimistic-provider review of negative matrix errors, missing/malformed matrix data and failed/malformed run input. Provider failure must retain Host warnings. Real role requests must receive frozen remediation/history, and caller mutation must not alter retained context. Existing CLI workflows also check immutable ledger extension and reject modified budget/verification journals even when their outer intent digests are recomputed. Injected live adapters still require explicit activation; application credential tests verify the private key is not exported. See the [audit and measurement record](maintenance/ARCHITECTURE_SIMPLIFICATION.md).

`python scripts/measure_context.py` measures fixed offline request character sizes (messages and compact JSON Schema separately) and 50 invocations of the current eight-point numerical program. These are payload sizes and local computation timings, not tokenizer counts, API latency, cache hit rates or scientific quality estimates. Explicitly authorized provider qualification is still required for this build; ordinary checks do not spend API credits.
