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
| Research case input integrity | `python -m lqcd_agent.research_cases verify` |

Core has 12 critical checks. Integration runs the current scientific, command-policy, durability, storage and CLI tests once, then nine numerical benchmark cases. Test counts are not acceptance criteria. Old results are not reused as evidence for this version.

The measured C2/Normalization case assessments are separate from those nine lightweight numerical checks. `tests/test_scientific_codegen.py` also runs both families through normal scientific planning, CodeHost delivery, actual isolated execution, Host review and Human Gate using synthetic deterministic backend fixtures. Separate mock-provider checks retain complete production-size summaries and Host diagnostics. Regressions cover changed data, effective-code/runtime drift, pending plans, empty coding contracts, nonzero calculation exits, dependency-free cancellation and idempotent delivery. These fixtures do not claim model or physics quality. Input packs, references, generated programs and reports remain local. `tests/test_research_cases.py` verifies source-preserving extraction, replica identities, independent numerical checks and actual sandbox read/write denial without measured data or API calls. Live programming and real-input assessment require the explicit operator actions in the [case guide](RESEARCH_CASES.md); ordinary CI does not spend API credits or depend on the external research project.

A passing check requires a nonempty selection, actual zero exit and JUnit without failures, errors or skips. Reports and raw JUnit go into a fresh root under the approved execution parent (`/private/tmp` on macOS). `check-results/latest.json` and `check-results/integration.json` point to the latest completed targeted/core check and full integration attempt; original failed reports retain their status. Affected checks and a full integration run have distinct scopes. Integration binds source, lock, build inputs and CI configuration before and after execution; ignored bytecode, package metadata and macOS `.DS_Store` files do not participate. Passed tests clean only their own fresh roots; failed roots are retained for diagnosis.

The runner also exports `check-results/ci-summary.json` and `ci-junit.xml`. The summary contains only selection/outcome, duration, source digest and benchmark status. Public JUnit contains case names, durations and outcome tags; it omits file paths, failure messages, captured output and private runtime references. CI uploads only these two files for seven days, including after a failed check. Detailed evidence and runtime directories remain excluded. Unit checks exercise privacy-preserving export and changes to build/CI inputs invalidating source identity.

For ordinary code edits, run the affected tests. Do not rerun the complete suite to update a document. For docs, check relative links and `git diff --check`. Tests are maintained according to behavior and risk, not a required case count.

`tests/test_prompt_context.py` checks the exact context boundary, lossless Unicode/escaping, and rejection before provider invocation for Planner and Reviewer. Oversized requests retain structured errors and no fabricated request/response. `tests/test_science_integrity.py` checks that an absent or untrusted Reviewer risk field cannot bypass Host confirmation; `tests/test_workflow.py` verifies the actual canonical scientific Run remains paused with pending approval and no accepted terminal result. The initial request builder preserves lossless JSON within 6,000 characters and rejects larger required context before any provider call; it does not truncate or invent a request/response. Host scientific review requires human approval regardless of model confidence or undeclared risk hints.

The checkout's Python 3.12 environment and `.venv` are ignored local dependencies. Standard console scripts and `python -m lqcd_agent` use the installed package. Follow the [single environment and lock-generation procedure](../README.md#develop); install with `--require-hashes` and set `TMPDIR` to the approved execution parent first (`/private/tmp` on macOS). Execution uses the fixed native macOS parent; no deployment-profile environment override is supported. Set `LQCD_AGENT_WORKSPACE` when the operator workspace differs from the current directory. Current environment qualification belongs in [Current state](REPO_CURRENT_STATE.md).

Deploy on qualified storage. Do not use a live SQLite file as a cross-node shared database, loosen locking or synchronization, or copy a live database as a backup. Use the coordinator's consistent backup operation.

Live qualification is explicit and separate from offline pytest. A live result applies only to its recorded source/build, model, input and executed workflow; earlier single-call provider results do not qualify the current research SDK collaboration. Retain failed attempts separately and distinguish successful model execution from scientific acceptance. Ordinary test runs do not read application credentials or start paid SDK jobs. Use the commands and boundaries in the [README](../README.md#application-api-and-coding) for an operator-authorized live check; detailed reports stay local and the current qualification summary belongs in Current state.

Native macOS checks exercise actual storage, boot/PID identity, process stop and child cleanup, cancellation and stable clock epochs across CLI processes. Unreadable or changed process identities must not authorize signalling. A scientific workflow reaching Human Gate still requires a researcher decision; a successful review artifact or synthetic numerical oracle does not supply that decision.

`tests/test_delivery.py` builds a wheel with a deliberately stale source manifest, installs it in a fresh virtual environment and runs doctor plus a scientific case outside the source checkout. Locked third-party dependencies are reused offline; the application must come from the installed wheel. `tests/test_engineering_assembly.py` covers nested/ambiguous configuration, the registered record-input program, malformed CSV and failed-review propagation. `tests/test_inspection.py` verifies status neither constructs executors nor changes authority files; unknown schema is tested in memory. A passive Codex metadata fixture checks the shared original job directory and rejects a redirected backend root, without model calls or backend construction. `tests/test_archive.py` covers closure admission, idempotence, unchanged sources, scientific member tampering and unsafe ZIP paths/types.

The GitHub workflow pins actions, grants read-only repository access, checks deterministic lock generation and installed dependencies, and runs Ruff plus offline integration on macOS. New pushes cancel older checks for the same workflow/ref. A separate Ubuntu job checks source/generated consistency, the numerical kernel and wheel construction using runner-owned temporary storage; it never opens an application authority or claims runtime qualification. Pure-contract tests run without site packages against an unavailable storage profile, and an architecture check prohibits control-to-graph imports. Local checks do not certify remote CI. The CLI timing probe reports independent-process samples, median and maximum; it retains measured Hosts and does not call paid APIs. Small samples measure local engineering overhead, not scientific capability or a production latency SLO.

Archive verification is content/inventory checking, not a replay, origin authentication without a separately trusted digest, or physics acceptance. Archives exclude SQLite and do not replace the coordinator backup API. There is no old-Run migration, automatic cleanup, unrestricted execution or extra approval policy.

## Scientific evidence and context

`tests/test_research_evidence.py` verifies exact consumed-byte provenance, changed-data refusal before calculation, explicit missing-input identity, and inherited input identity during a real scientific Replay. It also checks that models select program IDs while the Host creates mappings, rejects forged identities/paths and duplicate/unknown selections, preserves pending proposals, and supports digest-checked context section reads. Existing workflow, durability, cancellation, archive and credential tests remain part of integration.

Read a role's evidence catalog from its `llm_calls/<role>.json` request message. In Python:

```python
from lqcd_agent.llm.context import read_context_evidence

# output_dir is the scientific role's recorded domain output directory.
# catalog is the evidence_catalog from that role's request JSON.
source = read_context_evidence(output_dir, catalog, 'repo_inventory', fields=['analysis_programs'])
```

Planner sources are `user_goal`, `case_config`, `repo_inventory` and `research_context`. Reviewer sources include the complete supplied `method_plan`, `run_result`, Host `review_evidence`, review scope and `research_context`. The scientific adapter supplies remediation and bounded relevant history in `research_context`; standalone callers may omit it. A referenced digest identifies one immutable bundle; missing sections, changed bytes, symlinks and hardlinks are rejected. This helper reads local evidence and grants no execution, approval or control authority. Model messages contain selected views, not command logs or a general filesystem-reading tool. Archives include these bundles through the existing scientific member inventory.

Architecture regressions compare deterministic and optimistic-provider review of negative matrix errors, missing/malformed matrix data and failed/malformed run input. Provider failure must retain Host warnings. Real role requests must receive frozen remediation/history, and caller mutation must not alter retained context. Existing CLI workflows also check immutable ledger extension and reject modified budget/verification journals even when their outer intent digests are recomputed. Application credential tests verify that SDK clients receive the application key without exporting it to child environments.

`python scripts/measure_context.py` measures fixed offline request character sizes (messages and compact JSON Schema separately) and 50 invocations of the current eight-point numerical program. These are payload sizes and local computation timings, not tokenizer counts, API latency, cache hit rates or scientific quality estimates. Explicitly authorized provider qualification is still required for this build; ordinary checks do not spend API credits.

## Project collaboration verification

The research SDK tests run the actual SDK Runner with deterministic SDK Model outputs or an in-memory HTTP transport. They do not establish live model quality. Tests cover per-effect admission/settlement, unknown usage, tool/model cancellation cleanup, bounded turns, no nested agents, independent reviewer input, issue persistence and attributable references. Scientific revision tests exercise real control cycles and budget exhaustion, preserving the human gate and final report evidence.

Project/library tests cover empty installation, CAS edits, immutable versions, source/validation binding, atomic reviewed method snapshots, conflicting dispositions, admission idempotency, multiple content-addressed coding bases, producer-scoped captures and read-only history after execution storage loss. The replica-observable test executes an actual isolated synthetic program and checks Host arithmetic plus retained physics limitations. Candidate registration checks cannot substitute for independently executed numerical validation.

The arXiv/INSPIRE tests use transport fixtures and retain source/hash/page behavior. External service availability, paper figure reading and paid live PI/Postdoc/Reviewer runs are separate qualifications and are not implied by offline passes. Failed/unregistered role traces remain in the original Host and are not claimed as captured project artifacts. Full project issue context has an explicit 24,000-byte ceiling; each role currently has at most two model turns. Required initial evidence still uses the existing bounded request builder.
