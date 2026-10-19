# Test Infrastructure Maintenance

Current (2026-10-19): B00C29 is completed under the user's explicit authorization: the shared pytest runner timeout is 450 seconds. C21 triple_success passes through the actual runner in 395.88 child-pytest seconds with the original validators; 37 existing evidence/process-hook tests and the original real rejection probe pass on the same unchanged input. This is a waiting-budget adjustment, not an additional production optimization. The earlier ledger-stage 259/259 and legacy 325/325 retain their earlier inputs and original 300-second policy. Default collection remains 4,785; no new full-suite pass is claimed. B05 remains review and unimplemented. Dated historical entries are preserved.

## 2026-10-18 — Scope and implementation

User authorization: implement test layering, repeated AST parsing reduction and temporary-data lifecycle management while preserving existing assertions, coverage and acceptance standards. This is contract-preserving maintenance, not execution or completion of B05.

- Add the opt-in `smoke` marker to four existing canonical checks; document smoke, focused-module and full-regression entry points. Default collection remains complete. Frozen ticket acceptance remains mandatory.
- Reuse parsed ASTs by exact source bytes in each matrix/inventory validation call. Reread bytes and check path containment and qualified names for every reference; discard the cache on return. No result/proof or cross-session cache.
- Consolidate 88 direct Phase B directory allocations into one ownership-aware allocator. Keep the frozen direct `/private/tmp` root rule, prefixes and material contents unchanged. Nested pytest and spawned processes append under a file lock to the outer pytest's ledger.
- Clean only successfully completed ordinary pytest runs after session-finish consumers return and no multiprocessing child remains. Check each directory's device/inode and reject replacement/symlink deletion. Preserve failures, interruption, formal evidence, active children and uncertain cleanup. Never scan/delete historical roots.
- Add twelve regression cases for AST freshness/qualified names/path replacement and successful/failed/formal/interrupted/active-child/nested-pytest/replaced-directory/symlink directory lifecycles.

Unchanged: `src/`, protocol/catalog and their digests, frozen ticket bodies and completion records, scenario/owner/case inventory, matrix/registry/final obligations, expected traces, default full selection, all existing assertions, evidence schemas/normalizers/authority, timeouts and Phase B completion criteria. No Backend/provider/network change or new dependency. B00–B04 remain completed; B05 remains draft; Phase B remains incomplete.

Baseline: `057a836`, 4,749 collected tests. Audit before modification measured approximately 22.7 seconds for `load_inputs`; profiling attributed 17.5/28.1 seconds to 2,814 `callable_ref` calls. Measurements are local diagnostics, not acceptance results or guaranteed speedups.

Execution evidence directory: `/private/tmp/lqcd-test-maintenance-6j_16mcm`. The pre-change file digests/assertion ASTs, post-change collection and regression outputs are kept outside repository inputs. Verification results follow below after execution; historical B04 results are not retagged as current-input passes.

## Verification results and remaining gate

- Development smoke: **4 passed**, approximately **24.18 seconds**. Default selection is unchanged; deselection was explicit only for this development command.
- Focused schema/acceptance-foundation/infrastructure command: **80 passed** in **133.79 seconds**. An additional directory-replacement deletion guard was then added; the final infrastructure module passed **12/12** in **3.90 seconds**. The two focused results cover **81 distinct nodes**, with 11 overlapping; they are development verification, not a merged formal acceptance Session.
- One fresh formal B04 case, `artifact.projection_publication.after.committed_result_replay`, passed both mapped scenarios and the original pytest, observation and runtime validators after the child pytest exited (**17.803 seconds**). `session.unchanged()` passed; its source trees remained readable. See `formal-sample-report.json` and its raw Session evidence.
- Full regression was attempted without exclusions. The retained final attempt was interrupted after **301 passed / 12 failed**, approximately **906 seconds**, once the pre-existing golden gate was confirmed blocked. This is **not** a complete full-suite run or a full-suite pass. All 12 observed failed nodeids were individually reproduced on a `git archive` snapshot of unmodified **057a836**, using the same absolute Python interpreter; the selected failure sets match. The normal A05 normalized actual is also exactly equal between baseline and current code. The C12 parent failure is the same `check_failed:pytest:exit_code`; the other eleven are `invalid_evidence:trace:exact`. No expected fixture or assertion was changed to turn these green. Unexecuted tests are not certified.
- Evidence: `full-suite-final.{log,xml}`, the four `baseline-*.log` comparisons, `baseline-failure-set-comparison.json`, `golden-{baseline,current}-actual.json`, `focused.{log,xml}` and `infrastructure-final.{log,xml}`. The first interrupted attempt is retained separately in `full-suite.{log,xml}`. Failed-run ownership ledgers and source directories remain retained.
- AST audit: existing test assertions are unchanged. Protected runtime/config/evaluation/frozen-ticket/expected-trace and inventory files remain byte-identical to the pre-change manifest. The prior 4,749 default nodeids remain present, with 12 new infrastructure cases only.
- Local input-loading measurement: approximately **8.16 seconds**, versus the pre-change **22.7 seconds**. This measures `load_inputs`, not the entire suite, and is not a general speedup guarantee.
- Phase A validator passed all original checks, 101 semantic + 3 structural mutations, 178 publication-order mutations and 6 JSON/catalog negatives; protocol/catalog SHA-256 remain unchanged. Generated protocol is byte-equal. Compilation directed bytecode outside the repository; documentation relative links and `git diff --check` passed.

Remaining delivery gate: investigate the **baseline** golden mismatches under the applicable approved scope, then rerun the complete deterministic suite and applicable frozen acceptance. This maintenance neither repairs nor waives those mismatches, implements B05, nor changes Phase B status. Validation artifacts bind their actual input stages; subsequent documentation and the additional test are recorded separately, never retagged as the earlier formal Session.

## 2026-10-19 — Golden environment diagnosis and B05 preparation

User authorization: revise B05 locally using remote `codex/b05-ticket@9e7aa184265211c50ae5378cd54a985c148e1e99`, clarify the historical reader and batch-capacity scope, resolve the twelve observed baseline golden failures, and include the test maintenance in the next baseline. B05 implementation and its final acceptance are not authorized by this preparation request.

- The local B05 revision specifies moving the existing minimal `Archived03Reader` into the future CLI Host and sharing that single implementation with its tests. Fixture writers stay in tests; `ChildOperations` keeps its independent source checks and existing eligibility. No reader or CLI has been moved or implemented in this preparation.
- It also permits a capacity-only check point in the existing `run_pytest_batches` loop. Selection, timeout, evidence authority and validation remain frozen. The check point and B05 adapters have not been implemented.
- Diagnosis identified the recorded runtime fingerprint versions: the existing A05 Task semantic digest is reproduced exactly with the unchanged `057a836` application/graph build and LangGraph **1.1.5**, SQLite checkpointer **3.1.0**. The current shared environment actually contains **1.2.10 / 3.1.1**. Dependency versions are material to the existing codec; treating their differences as ephemeral would weaken acceptance and is not permitted.
- A separate temporary virtual environment reproduced all four original A05 goldens, the Human prefix and both Human continuation goldens without modifying expected bytes. Its twelve-case diagnostic finished **8 passed / 4 failed**: three isolated-child checks could not import the uninstalled project, and the mixed source retained the actual interpreter/configuration difference. This diagnostic is not a passing delivery run. Shared Python packages were not changed.
- The mixed-source tool policy also records the real interpreter and Python version. Historical tickets name `/opt/anaconda3/bin/python`, which is absent on this machine. A new baseline must record the actual trusted configuration and preserve its exact checks; substituting a fake interpreter/fingerprint or excluding configuration fields is not a fix.
- Review candidates are generated outside tests, using actual fresh source material and the unchanged strict normalizer. For the seven version-only goldens, reconstruct the old semantic preimage DAG by changing only the two explicit dependency version literals, then derive the candidate from the original expected via the resulting semantic-head map. Any unexplained difference rejects the candidate. The mixed source additionally requires independent fresh execution of the unmodified `057a836` archive in the current environment and exact equality with the maintenance tree, alongside review of the real tool configuration and unchanged domain/control assertions. No old raw or sealed evidence is rewritten or claimed to have been recovered.
- Intended verification environment: Python **3.12.7**, `/Users/xiang/.local/python_vev/bin/python`, pytest **9.0.3**, LangGraph **1.2.10**, SQLite checkpointer **3.1.1**. Full installed-package and runtime manifests are retained with the evidence; no dependency declaration, production source or codec change is part of the repair.

Preparation evidence: `/private/tmp/lqcd-b05-preparation-20261019-8oj6hzyu`. It contains the pre-change 5,656-file snapshot/manifest, remote ticket identity, old/current runtime diagnosis, diagnostic failures, reviewed source pairs, semantic preimages and candidate differences. The pending baseline is `057a836` plus the authorized test maintenance, reviewed golden repair and local B05 revision; it is not yet a committed frozen ticket or B05 completion. Final validation and delivery manifests are recorded below once obtained.

## Reviewed repair and bounded regression diagnosis

The original twelve observed failures all passed in the next complete-selection attempt. That attempt stopped at an additional pre-existing C15 golden mismatch: **406 passed / 1 failed in 5,432.78 seconds**. Its input digest was `954a6c781c4323a73e74e476d43d5ea3b958b18f48ceb2c557cc25f754366868`; the input remained unchanged. This is a failed full attempt, not a full-suite pass.

A separate remaining-node diagnostic selected exactly the 4,354 nodes not executed in that attempt. After **265 passed / 36 failed in 7,134.22 seconds**, it was interrupted deliberately because the independent legacy run had already established an unavailable external acceptance input. The one deselection was the already-executed C15 failure, not an acceptance exemption. The diagnostic input remained unchanged; unexecuted nodes are not certified. These runs are neither combined into a passing full run nor reused as formal B05 acceptance.

The observed additional failures share reviewed environment-bound expected bytes, except for one confirmed C16 child timeout at the existing 300-second limit. The Code dual-fresh test eagerly constructed a success fixture even for three modes which never used it. It now obtains that fixture only for the success mode. Both fresh source executions, all original assertions, nodeids and timeouts remain unchanged. No production/normalizer optimization or proof-result cache is introduced.

Twenty-seven expected files are reviewed for the actual environment: A05 four; mixed one; Human prefix/continuations three; C15 two; C18 three; C16 Code four; C20 one; C21 nine. Seven original fixtures and the C15/C18/C20 fixtures are derived strictly by propagating the two dependency version literals through the actual semantic preimages. The empty Code fixtures and failed C21 fixture additionally require original producer/raw canonical preimages and the existing resolved-input sorting rule; their entire differences are reconstructed. Unmodified archive tests also pass under the historical dependency versions for these groups. Read-only audit helpers live outside repository inputs; the runtime and normalizer are unchanged.

Mixed, successful Code and successful C21 sources also execute the actual Python analysis tool. Two independent fresh roots, including an unmodified `057a836` archive, produce exactly equal normalized traces and domain facts under the same real interpreter. The actual tool configuration and successful outcome were inspected. Remaining changes are semantic digest references downstream of that Analysis invocation; event order, outcomes, owner/epoch/revision relations, budgets and all non-digest fields are unchanged. Historical tool-configuration preimages are unavailable, so these are explicitly reviewed new Host-configuration baselines, not claimed version-only derivations or recovered old evidence. No unchecked actual-to-expected overwrite occurs during acceptance.

Detailed source pairs, raw/semantic preimages, field differences and approval digests are in `golden-repair-final-manifest.json` and the `golden-review`, `additional-golden-review`, `additional-c18-golden-review`, `additional-code-golden-review`, `additional-c20-golden-review`, and `additional-c21-golden-review` directories under the preparation evidence root. All candidates were fixed before repaired-input regression began. Original failed runs and source trees remain retained.

## External legacy reference gate

The independent original legacy selection finished **324 passed / 1 failed (325 total)**. The sole failure is `tests/test_graph_smoke.py::test_golden_demo_graph_writes_pending_report_and_approval_packet`, which requires seven original reference files. The local sibling directory is absent. Public `xgao19/lat-hadron-analysis` was checked on main, classical, develop and analysis-DA; there are no remote tags. Only `analysis-DA@f7277044bc49cf24d4bfabbf9f7e4e0004ff9b2b` contains the old directory, with six of seven files. The missing original is:

`examples/l64c64a076_m140/analysis/1-c2pt-fit/results_nstate_fit_2state_rerun/l64c64a076_m140_fit_pz5/l64c64a076_m140_fit_pz5_symmetric_summary.txt`

The exact missing path has no commit history in the checked remote branches or local refs. Evidence: `sibling-remote-reference-check.json`, `legacy-baseline.log` and `legacy-external-dependency.json`. The user acknowledged that a backup may no longer be available. No partial fixture, synthetic replacement, config change, skip, fallback or relaxed assertion was introduced; the dirty sibling checkout was not modified. This remains an unmet full-regression/B05 entry gate, not a waiver.

B05 remains **review**. Its local revision names the three exact historical-reader callers, keeps the sole future implementation shared, limits capacity checks to the existing batch loop, and explicitly retains both the missing-reference gate and the single-node 300-second limit. No B05 CLI, reader move, capacity hook, exit adapter or final acceptance was implemented. B00–B04 lifecycle and historical records remain unchanged.

## Baseline provenance retained in the repository

The actual runtime fingerprint for this reviewed baseline is:

```json
{
  "control_protocol": "7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8",
  "application_build": "df2cd8314c25a0d391278c705cb6c97c206e91dbe5b5b8e18ff6684f07ba0f61",
  "graph_topology": "d288a0c865f97f9ff84bf507f29e04739325f8d49a980dc74ef0c580302a2fbc",
  "state_schema": "0.4",
  "execution_schema": "0.4",
  "artifact_schema": "0.1",
  "langgraph": "1.2.10",
  "checkpointer": "langgraph.checkpoint.sqlite:3.1.1",
  "serializer": "lqcd_agent.control.checkpoints.CanonicalCheckpointSerializer:0.4"
}
```

The mixed and successful Code/C21 sources use this actual trusted Analysis configuration; the historical configuration preimage remains unavailable:

```json
{
  "command": [
    "/Users/xiang/.local/python_vev/bin/python",
    "-I",
    "-S",
    "-c",
    "import runpy; print(runpy.run_path('sample.py')['value']())"
  ],
  "environment": {
    "inherited_environment": false,
    "network": "disabled",
    "python_isolated": true
  },
  "outputs": [],
  "runtime": {
    "executable": "/Users/xiang/.local/python_vev/bin/python",
    "python": "3.12.7 (main, Oct  1 2024, 02:05:46) [Clang 15.0.0 (clang-1500.3.9.4)]"
  }
}
```

The actual subprocess returned 0; stdout is `2\n` (SHA-256 `53c234e5e8472b6ac51c1ae1cab3fe06fad053beb8ebfd8977b010655bfdd3c3`) and stderr is empty. Unmodified `057a836` and the maintenance tree produce exactly equal normalized traces for these reviewed sources in this environment.

All paths below are relative to `tests/phase_b/expected_traces/`. These are fixed reviewed expected bytes.

| Expected | Original SHA-256 | Reviewed SHA-256 |
| --- | --- | --- |
| `a05_failed.json` | `56db51fed72ea3269d502c986ab85fa6c500ebdc6a2ccd60b3f9bedf82727cc3` | `aa8c4861822b18fe3366b741667ea219c1885604eac37087ba970c72483a2243` |
| `a05_normal.json` | `aac3930f15eecdb97f78f6e938005628dd45b3b05aa7696ebef8c8666e7ca51f` | `2033ee7d8534da52d87ea064352fb54fdc9b1cf2c12f112494f77b6116c67b67` |
| `a05_timeout.json` | `317ef77e55fbffa54f30153253020e6d39a2b3c7aedd28ae16fe915d2f9ac7f6` | `5cba85a83801b2f9c53b158f70b46c74d964a5efb1cbe5bdeb8e34155d72f772` |
| `a05_unavailable.json` | `47ec3d860b3369d42f3964f096118d335e3ddb2a6e356ae4760815022494ba8b` | `f02e7cde037af3d25b1d838e33bb7d490a697f59c5a41f40f5ab89a1f9e06105` |
| `b00c10/mixed.json` | `244b337d985ff50bac0526767d326be18dc92645773e28e9a10280033f1f30d9` | `59536d7ee63b079c96193cf44c61c2768f87d7e2a0774bacca4e5d5dd55162aa` |
| `b00c15/failure.json` | `05fc7baee190b21f2adad335df376038dce07ae2858bc5553d9458c254055fef` | `6cc07ff1e4722bc54c21baa34e57bca8923a5b9548495bdb2fbd5ebf4081eb3a` |
| `b00c15/grant.json` | `324d2f86de2202e259f22136670c7418e54bafc69aa76907aa339930760bdaca` | `e999ef8b9043652673b9725a93474590357aaf64c888c11b4656adca24ffa806` |
| `b00c16/approve_rerun.json` | `bc878b0f3be62fc59b183d91c0c6a8691963a58e1208b4aaf40c729d44b3debb` | `2c020d9f27b0095e98243dbd83f9650d1898f1245d3d682b54fbb90865bd6a1e` |
| `b00c16/code_empty.json` | `4054e5f6000e59b0f4c390c176021450b727f2e67b8f9fb86b4eb128c7e7818b` | `f20981454c75951b50694f841985fca12283f4efacdc4aaaa5baa8c3105544de` |
| `b00c16/code_repeat_empty.json` | `992393da6c66d1bd0bee89f082d0c29927de47959ea2cb983981f8ffdae7c334` | `0da555e0c7c82cb7875bf3d8c57a3a7efcf797c24b3490096cf99aa326cdd804` |
| `b00c16/code_repeat_success.json` | `e6b351ba4158f3eb255aaa8ba08a6aca568f0fd5682a924c89b6887604d7be91` | `4a27a67c57713384a71ac39f446265b4f3f3372c6f73967720021f15bf73757a` |
| `b00c16/code_success.json` | `95048e7de73f9ad419d55a5523ad457f95c22312f36e820e1a25cf47e7a9759e` | `3d6101e504a5ca51bf3938b79240ab74f62620da8667df6c71a4f37b5ac836ed` |
| `b00c16/human_prefix.json` | `f31d9b28daa1afa2fb759d3aae13b74e94e26aa124bd1d650f9aa7d710b93f10` | `317e8da22fdf680b1d74a28eaf7469efc64a4652f048dd681d51a31f6f1da9a9` |
| `b00c16/reject_or_hold.json` | `a128adddda6d2f5d855dfe698c075426766bcd68f2939256b1d3ca417203a016` | `ba4ac650cda1cb2f9adde38be02e3144e1f8b22aea37c8761d4ecb7a30ef8426` |
| `b00c18/ordinary_corrected.json` | `4db37f10e215d25a255a6f91638f6d80046630f0afbee564c2e63eece69b7bbf` | `7387e18cc3f4a8e10f7a57d9eb85a06d7098311a899c165b8041825dac861750` |
| `b00c18/ordinary_insufficient.json` | `4b934bc444de4534e30a480ef098a70bc131e65846be7a3aff681db1eabf857c` | `b12131a7897a5c57ada49928c87c4f628aa6591d27939058695105503aaac6d3` |
| `b00c18/terminal_corrected.json` | `5680206826ca61a1a485d66f0fd31749d0bea75e523aafcdff4428aced0ba75d` | `0870dae588abc050d21a5b39560e3989274321f86983db3b2f8202dbf1690fb1` |
| `b00c20/failure.json` | `ac37b0c75556af7501c351ac6bd4e73ea6bb57bede70ed3110a6ad57c4610cee` | `5a3922b3133dba2a40b197df0116e14018753ccf873db8bce1dc1c90bf22b378` |
| `b00c21/budget_exhausted.json` | `3ea79ea7321015df3785e45aa5f4d76d0a3ba237b484f1d9a0e355cbc99e88cd` | `c083ca51adb6055c5a3fbe2d54527f4c47f2ceedfec035b52f89f09976561c80` |
| `b00c21/needs_human.json` | `2180cbfd129a80dfb43192b06453d597666c4c4355e09a723264a9b01fac8b71` | `90c8b3436b7c5b348f34027cfc7d5af7ec0907e21c888ff7765b779fcb2774dc` |
| `b00c21/needs_input.json` | `2e4331fd7e8a973da50a939533f564344454ff6cfec302573ee72327eb77735d` | `9bbdaf53481b5d418394d59b5925b686c511d3de5b7795ed88f9de92a10478d6` |
| `b00c21/no_change.json` | `88257ca88a6217cb2016c24ac7af9d0093b72d7e18d81ebf024fe1fc9ca97c40` | `dd0d1ec00e75f782e08c7e1c2ddf3f1d2e0d00f469c830c790bdc3b09902b48c` |
| `b00c21/policy_blocked.json` | `34564076ffe6a78ab892253d9666ed1269f98179c0e755a87e624429734fa528` | `a4b6cc9eee51e2827670670d8ff73b3f93bddb9cdec1bfacb36cb733f8b3bf7d` |
| `b00c21/retry_failed.json` | `8be4e6a10d29358e4d94bc55c36f51c4123662b7abc9dc0262d2b635f2fc2b83` | `cec69604e35e18947d0954fd62ea3aa93884d5874615340284bb4b066487c73e` |
| `b00c21/retry_success.json` | `0c25d6e2369b6d1363434237845b1dd0b860dcc6b70f7c1379854d8f179d5ecc` | `67100359026eaa0c804636a839edd694484df0f893b9f2a078a29dc70a0c16fd` |
| `b00c21/timeout_retry.json` | `bcc902003231cdd66635585b16481e6f6bb4123883e5a85a476eeaa296169be9` | `63eb046724159c46adf0f81847ec44bbf3d3ae91539695419f00adb1b76558a8` |
| `b00c21/triple_success.json` | `41dd41c94b63f553090aff2018b0193437cf46a5382ef286e27da9b23b1cd82d` | `b6b51804f069f951626f259868c4c75db2e04fad201b666b10d019b992c592c0` |

## Repaired-input verification and delivery

The fixed repaired input `e55f99505c0326a785e06f72cf157b08aabfa5ccbfdf83da95b012fb8c6dbc2f` ran the exact **61-node** focused selection: the original twelve failures, all 37 distinct additional observed failures, and the twelve infrastructure regressions. Result: **60 passed / 1 failed in 7625.73 seconds**. All original twelve passed again. The input remained unchanged throughout. This is focused verification, not a complete full-suite run or B05 final Session. Evidence: `repaired-regression-input.json`, `repaired-regression.log`, `repaired-regression.xml`, `repaired-regression-result.json` and `repaired-regression-summary.json`.

The exact 5,656-file tested input is retained separately as `repaired-input-manifest.json` and `repaired-input-snapshot/`. Its original harness worktree digest matches the bound input exactly (`repaired-input-snapshot-proof.json`); subsequent result documentation has a separate delivery manifest and snapshot.

Remaining focused failures:

- `tests/phase_b/test_b00c16_trace_consumers.py::test_formal_meta_uses_current_session[repeat_success]`

The direct double-fresh repeat-success node took **386.285 seconds** in this diagnostic run; it was not subject to the formal runner. A two-second read-only native stack sample was retained as `c16-repeat-success-stack.txt`; it is not a Python-level root-cause profile or acceptance evidence. The formal child still enforces its original 300-second limit. Removing the unused fixture is a verified simplification, but it does **not** establish that the timing gate is resolved. No formal timeout increase, assertion reduction, source reuse, runtime refactor or test-selection exemption was used. Further performance diagnosis is needed before B05 approval.

Final scope checks preserve all 142 original assertion ASTs and all 4,749 original nodes; the only new nodes remain the twelve infrastructure checks (4,761 total). All 27 expected files match their reviewed fixed SHA-256 above. Strict finite JSON/duplicate-key checks, affected Markdown links, compilation with bytecode outside repository inputs and `git diff --check` pass. Shared `pip freeze --all` is byte-identical before and after. Production, normalizers, protocol/catalog, runtime inventories/owners, dependencies, frozen ticket bodies/completion history, legacy tests/configuration, evaluation and the existing presentation are unchanged.

Measured nodes over 300 seconds are listed below as a B05 scheduling prerequisite, separately from actual test failures. These wall times include fixture/parent validation and are local diagnostics, not formal runner receipts; passing here does not prove the complete node fits a 300-second batch. Preserve the checks and limit while diagnosing the cost before B05 execution.

| Pytest class / node | Seconds |
| --- | ---: |
| `tests.phase_b.test_b00c21_prior_code_evidence::test_product_retry_has_exact_sources[triple_success]` | 839.398 |
| `tests.phase_b.test_b00c21_prior_code_evidence::test_product_retry_has_exact_sources[no_change]` | 613.878 |
| `tests.phase_b.test_b00c21_prior_code_evidence::test_product_retry_has_exact_sources[needs_input]` | 517.538 |
| `tests.phase_b.test_b00c16_canonical_code_audit_sources::test_dual_fresh_canonical_sources[repeat_success]` | 386.285 |
| `tests.phase_b.test_b00c21_prior_code_evidence::test_product_retry_has_exact_sources[retry_success]` | 365.465 |
| `tests.phase_b.test_b00c21_prior_code_evidence::test_product_retry_has_exact_sources[policy_blocked]` | 353.324 |
| `tests.phase_b.test_b00c21_prior_code_evidence::test_product_retry_has_exact_sources[needs_human]` | 324.324 |
| `tests.phase_b.test_b00c21_prior_code_evidence::test_product_retry_has_exact_sources[budget_exhausted]` | 319.769 |
| `tests.phase_b.test_b00c16_trace_consumers::test_formal_meta_uses_current_session[repeat_success]` | 310.598 |

The failed full attempt, interrupted remaining-node diagnostic, independent legacy run and repaired-input focused verification retain their own actual inputs and outcomes. Subsequent documentation is a separate delivery input, never relabeled as a tested Session. No complete current-input full-regression pass is claimed; unexecuted nodes remain uncertified. Restore the missing original legacy material, resolve the remaining formal timing failure and obtain a new complete regression before treating this baseline as a passing B05 entry. B05 stays review and unimplemented; no commit or push was requested.

## 2026-10-19 — Original reference restoration and legacy rerun

The user supplied `/Users/xiang/Downloads/l64c64a076_m140_fit_pz5_symmetric_summary.txt` and authorized moving it into the required reference directory. It was moved to the exact `analysis/1-c2pt-fit/results_nstate_fit_2state_rerun/l64c64a076_m140_fit_pz5/` path under `/Users/xiang/Desktop/codes/lat-hadron-analysis/examples/l64c64a076_m140`. Its 1,247 bytes have SHA-256 `8da12ee2d1d28c9b082d23d01d3c147ff72b66a29229d75d34de70da7ca53f90`, verified before and after the move. Its provenance is the user-supplied file; no independently recorded historical digest was available for that summary.

The other six configured reference files were restored from the existing Git objects of the previously checked remote `analysis-DA@f7277044bc49cf24d4bfabbf9f7e4e0004ff9b2b`. Each was verified against its exact Git blob SHA-1 before publication. Only the seven configured reference files were restored into the previously absent subtree; no existing sibling files were overwritten. The sibling branch remains `classical` and its existing tracked changes are byte-identical. No substitute fixture, test/configuration change, fallback or relaxed assertion was introduced.

With the existing canonical interpreter `/Users/xiang/.local/python_vev/bin/python`, `PYTHONDONTWRITEBYTECODE=1`, `RUN_LIVE_LLM_TESTS=0` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, the original legacy selection `python -m pytest -q --ignore=tests/phase_b` passed **325/325 in 88.44 seconds**, with zero failures, errors or skips. Temporary test roots, cache, JUnit XML and logs were directed outside the repository. The formerly failing `test_golden_demo_graph_writes_pending_report_and_approval_packet` passed. Repository inputs and all seven reference digests remained unchanged during this run; subsequent status/documentation updates are separate from the tested input.

Evidence: `/private/tmp/lqcd-golden-reference-restore-20261019-f93ghngb`, including `restore-result.json` (all seven paths, sizes, digests and provenance), `agent-input-manifest.json`, `legacy-command.json`, `legacy.log`, `legacy.xml` and `legacy-verification.json`. The earlier 324/1 legacy result and other failed/interrupted runs remain historical facts. This closes the missing-reference gate for the current local legacy selection; it does not establish a full-repository pass. C16 and the previously listed slow-node timing checks still require resolution and a fresh complete regression. B05 remains `review` and unimplemented; no commit or push was performed.

## 2026-10-19 — C16/C21 performance diagnosis, without implementation

User authorization: locate the C16/C21 bottlenecks first. No production, test, expected, configuration, dependency, timeout, assertion or acceptance change was made. B05 remains review and unimplemented.

The two unchanged direct pytest nodes were run with a diagnostic-only plugin outside the repository: `test_b00c16_canonical_code_audit_sources.py::test_dual_fresh_canonical_sources[repeat_success]` and `test_b00c21_prior_code_evidence.py::test_product_retry_has_exact_sources[triple_success]`. Both original tests, including their two fresh sources and exact golden assertions, passed: **2 passed in 1,013.18 seconds**. The command used the existing canonical Python and opt-out environment documented above. Python 3.12 selective `sys.monitoring` counters and approximately 20 ms Python stack sampling measured the existing paths without modifying their source. These are instrumented local diagnostics, not a formal acceptance Session, an uninstrumented benchmark or a speedup claim. The formal 300-second child limit was unchanged and the failing formal C16 parent was not rerun.

| Diagnostic node | Node wall seconds | Ledger core seconds | Ledger share | `parse_ledger` calls | Full replay calls | `.values` reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C16 repeat_success | 377.074 | 227.072 | 60.2% | 3,148 | 4,747 | 3,776 |
| C21 triple_success | 632.274 | 413.816 | 65.4% | 4,009 | 5,533 | 5,045 |

Ledger core time sums exclusive time among the selected functions in `control/execution.py`; nested cumulative times are not added twice. Node wall times come from JUnit. Selective instrumentation and sampling have overhead, and local timings vary with machine load. The earlier 386/839-second measurements retain their original inputs and conditions; no implementation changed between them and this diagnostic.

### Primary cost: repeated decoding and validation of the same ledger prefixes

- `control/execution.py:218` parses every line with `parse_record(...).value`, then `replay` enters `_checked_replay` at line 23 and validates the decoded records again. Each `ValidatedValue.value` read performs strict JSON decoding and canonical re-encoding. `ExecutionReplay.values` at line 18 repeats record parsing and validation on every access. `append_record_bytes` at line 223 reads the old validated values and replays the enlarged prefix again.
- Read-only `cProfile` probes on retained genuine source bytes confirm the duplication: one `parse_ledger` followed by two detached `.values` reads causes **440 record validations for 110 C16 records**, and **652 validations for 163 C21 records**. The returned copies remained distinct and equal, and source bytes remained unchanged. These probes establish repeated work, not permission to accept unchecked data or return shared mutable records.
- Over the complete two-source tests, `_checked_replay` visited **283,124 / 520,345 records** and `.values` reparsed **223,797 / 459,787 records** for C16/C21. The largest individual ledgers had only **110 / 163 records**. Increasing retry count grows both the ledger and the number of guards that process it.
- `InvocationLeases._activation` at `control/capabilities.py:347` is the leading direct caller of `parse_ledger`: **1,404 / 1,770 calls**, taking **57.649 / 105.745 seconds** in that callee alone. `ArtifactEffectPort.write_member` at line 103 fences authority, directory creation and publication repeatedly; each fence re-enters activation. Other material callers are append, integrity validation and the product runtime's `_records`. These checks have ownership and freshness purposes; the profile does not justify deleting their boundaries.

### Secondary cost: repeated Git reads during Analysis preparation verification

`InvocationLeases._activation` also calls `preparation_adapter.verify_preparation`, which reaches `AnalysisHandoff._verify_source` / `_source` and `workspace.immutable_git_tree`. Main-thread stack samples contained `immutable_git_tree` for **16.4% / 5.3%** of C16/C21 samples. These are approximate inclusive sample shares, not disjoint CPU times to add to the table.

The unchanged Git reader invokes `rev-parse`, `ls-tree`, and one `cat-file` subprocess per file. A read-only probe of the genuine one-file base confirmed **five identical tree reads caused 15 subprocesses**, approximately **0.522 seconds** under `cProfile`. The repeated guard path amplifies that per-read cost. It must continue to reject source drift, replaced object authority, escaped paths and altered bundle bytes; a previously valid receipt alone cannot replace a fresh ownership/freshness check.

### Lower-priority work and bounded follow-up

The measured budget projection took only **2.555 / 3.087 seconds**. `ControlTrace.finish` took **4.406 / 10.554 seconds**; all trace normalization calls took **13.353 / 18.616 seconds**. These cumulative timings overlap nested ledger work and must not be summed as independent costs. Source generation itself accounted for **363.490 / 613.587 seconds**. The main opportunity is therefore in the production validation path, not further test selection changes.

Recommended follow-up, not implemented:

1. First consolidate the pure ledger pipeline so the same exact byte snapshot is decoded, record-validated and replayed without redundant intermediate revalidation. Preserve strict parsing, duplicate/non-finite/canonical rejection, hash chains, all state/budget checks and detached public values. Use one canonical path; do not introduce a reusable proof/authority cache, fallback or parallel implementation.
2. Then evaluate repeated immutable-base and preparation work within the existing guard path. Preserve each required lease/epoch/revision/head/terminal and tamper check. Any cross-boundary reuse requires a separately justified binding/invalidation argument; this diagnosis authorizes no weaker contract. Git subprocess fan-out is also a scaling concern for larger bases, but batching alone does not remove the three-process cost of this one-file fixture.
3. Verify each actual optimization against the unchanged direct tests, original formal C16 parent, all nine previously measured slow nodes and the complete regression. Optimizing `.values` alone cannot establish the timing target: even eliminating its entire measured **62.704 seconds** would leave this C16 run above 300 seconds. No gain or full timing closure is claimed in advance.

Evidence: `/private/tmp/lqcd-c16-c21-profile-20261019-7jjaw7d_`, including `command.json`, `input-manifest.json`, `profile-tests.log`, `profile-tests.xml`, `result.json`, `final.json`, `diagnosis-summary.json`, `perf_probe.py`, `run_profile.py`, and the `ledger-decode`, `c21-ledger-decode` and `immutable-git-tree` cProfile files/text/summary JSON. The first profiler setup failed before running any test because `PY_UNWIND` is a global-only monitoring event; its logs are retained separately as `instrumentation-setup-failure-*`. The external plugin was corrected and the full two-node diagnostic then passed. This was a tooling setup failure, not an additional repository test failure.

All repository inputs remained byte-identical throughout the successful diagnostic; the only subsequent repository edit is this maintenance record. Production and all existing assertions, expected bytes, test configuration and timeouts remain unchanged. The known formal timing failure and complete-regression gate remain open; this diagnosis does not mark B05 ready or Phase B complete. No commit or push was performed.

## 2026-10-19 — Ledger pipeline consolidation and C16/C21 rerun

User authorization: first merge repeated ledger processing, preserve fencing, tamper detection, detached copies and all existing assertions, keep the 300-second limit, rerun C16/C21, and do not execute B05. This is contract-preserving maintenance. No architecture, public schema, protocol, catalog, owner, acceptance, configuration or dependency change is introduced.

### Removed duplication and preserved boundaries

- `control/records.py` keeps one field-validation body in `_validate_record`; the public `validate_record` retains its original `ValidatedValue` return contract. An AST comparison confirms that every original validation predicate is unchanged.
- `control/execution.py` strictly decodes external ledger bytes and then validates/replays through the existing path. It retains each record's newly validated immutable canonical bytes, decodes that exact internal snapshot without another strict round trip, reuses those bytes in the returned snapshot, and computes chain heads directly from those bytes instead of re-encoding the same object. It removes the redundant `parse_record(...).value` and canonical encoding steps from this pipeline, not their validation predicates.
- Public `.values` still strictly parses and record-validates each byte record and returns fresh detached objects on every call, including manually constructed `ExecutionReplay` inputs. `append_record_bytes` still fully validates the old prefix before replaying the enlarged prefix. No proof/authority/result cache, stale-prefix shortcut, fallback, second replay implementation or configuration knob is added.
- All existing freshness/fencing calls, lease/epoch/revision/head checks, budget/state/lifecycle predicates, coordinator/publication paths, immutable Git/preparation checks and the formal 300-second harness are unchanged. The two source files are the only production changes.

### Build-bound golden synchronization

The real runtime fingerprint hashes production source bytes. Its `application_build` changes from `df2cd8314c25a0d391278c705cb6c97c206e91dbe5b5b8e18ff6684f07ba0f61` to `dbe26a2f18dfcecf5e11c6410adfae26234eff5f5e8ac7436eb109e701503d4f`; the other eight fingerprint components remain unchanged. Python 3.12.7, LangGraph 1.2.10 and SQLite checkpointer 3.1.1 remain the real environment. The final `pip freeze --all --local` output is byte-identical to the before list. An initial comparison against default `pip freeze` differed only because that command omits pip and includes external LHAPDF metadata; the original lists and exact-command comparison are retained, without changing the environment.

Twenty-seven existing expected traces are derived from retained genuine original-build raw/semantic preimages, first proving that each source normalizes to its original expected bytes. The derivation changes only the real build component and recomputes its dependent hashes with the existing input-ordering rule. Every changed expected leaf is a `semantic_sha256:` value; event order, outcomes, ownership, budgets, scientific content and every non-digest field are unchanged. No fingerprint spoof, normalizer change or unchecked actual-to-expected overwrite is used. The reviewed candidates were fixed before final regression.

The groups remain A05 four, mixed one, C15 two, C16 seven (Code four and Human three), C18 three, C20 one and C21 nine. `build-golden-candidates.json`, `applied-build-golden-audit.json`, `derive_build_goldens.py` and `build-golden-review/` under the final evidence directory retain the original sources, before/after file hashes, dependent preimages and per-leaf differences.

### Verification on the final frozen input

The final tested worktree digest is `6478802887a63e8895308a8511012d033d7b38d89532d079c30a90e31505edb4` (5,663 input files). Both regression commands verify it before and after execution. The self-contained `tested-input-snapshot/`, `tested-input-manifest.json` and `tested-input-proof.json` retain that exact input; subsequent documentation is a separate delivery input and does not relabel either tested run.

- Old/new comparison on 13 retained genuine C16/C21 ledgers covers **1,318 valid prefixes and 39 appends**: canonical record bytes, canonical projections and detached values are identical, original source bytes are unchanged, and record-validation predicate ASTs match. Invalid-input rejection is separately exercised by the new and existing tests; the valid-prefix corpus is not claimed as a tamper corpus.
- Add **24** focused cases for immutable/detached snapshots, parse/replay/append equivalence, strict duplicate/non-finite/noncanonical input rejection, schema/identity/hash/clock/payload tampering, directly constructed snapshots and changed-prefix append rejection. All **216 existing Python test files are byte-identical** to this maintenance turn's starting input; no original assertion, nodeid, selection or timeout is removed or relaxed.
- Final focused command: **259 passed / 0 failed / 0 errors / 0 skipped in 3,708.78 seconds**. It includes the original formal C16 parent (1), new pipeline cases (24), execution foundation (25), invocation artifacts (2), child control (23), legacy source compatibility (55), A05 source traces (55), full C16 canonical-source module (31) and full C21 prior-code module (43).
- The original formal C16 parent takes **258.338 seconds** including its surrounding work. Its unchanged child actually reports **242.95 seconds**, exit 0, under the original **300-second** limit. The direct C16 `repeat_success` test, including both fresh sources, takes **237.991 seconds**. Original source-observation evidence was archived before successful ordinary fixture cleanup: one attested source tree, 153 files, complete SQLite durability unit and archive member hashes verified. The original test still asserts two distinct fresh sources; the archive is not claimed to contain both.
- Independent unchanged legacy selection `python -m pytest -q --ignore=tests/phase_b`: **325 passed / 0 failed / 0 errors / 0 skipped in 105.08 seconds**. All seven original reference-file digests and repository inputs remain unchanged.
- Default collection is **4,785** (all previous 4,761 plus 24 new cases). Strict canonical JSON checks pass for the 27 changed expected files; compilation of the two changed production modules and new test module passes with bytecode outside the repository. Diff, relative-link and final scope checks are recorded separately with the delivery manifest. Existing fencing/harness, protocol/catalog/owners, evaluation, configuration, dependencies, completed/frozen tickets, historical completion records and the existing report deck are unchanged.

C21 original dual-fresh test durations from final JUnit, in seconds:

| Mode | Seconds |
| --- | ---: |
| retry_success | 231.032 |
| retry_failed | 116.125 |
| triple_success | 422.545 |
| no_change | 219.594 |
| needs_input | 210.653 |
| needs_human | 223.704 |
| budget_exhausted | 199.077 |
| policy_blocked | 205.815 |
| timeout_retry | 211.190 |

The only node above 300 seconds in this **259-node selection** is C21 `triple_success` at **422.545 seconds**. Its functional assertions pass, but its slow-node timing risk remains open. This result cannot establish that no other node in the unrun full suite is slow. The earlier instrumented 377.074/632.274-second diagnosis has different measurement conditions; these figures are not a controlled speedup comparison.

### Intermediate attempt and remaining work

An intermediate implementation used build `0a4cafe14930a31dfbc93e85566cb0e65013c21d6a0ede92d3591ab1ccf806fa` and tested input `ca5e607a1c5302d27789e5fba39bcfd2849ffe784644973a38de121caf48f9c4`. Its 124-node command was deliberately interrupted after **4 passed in 582.97 seconds**, exit 2, before consolidating the last duplicate chain-head encoding. Its original formal child passed in 262.64 seconds. That input, archive and actual interrupted result remain in the parent evidence directory; they are not a passing 124-node run or evidence for the final input. No source mutation occurred while either regression was active.

The authorized first consolidation is complete. C21's remaining long path and a fresh complete 4,785-node regression still need resolution before a passing B05 entry can be claimed. Repeated immutable-base/Git/preparation work identified in the preceding diagnosis was not changed in this scope. Any follow-up must retain each current fencing and tamper boundary; no cross-boundary cache or weakened proof is implied by these results. B05 remains `review` and unimplemented; B00–B04 historical completion states and Phase B incomplete status are unchanged. No commit or push was performed.

Final evidence: `/private/tmp/lqcd-ledger-pipeline-20261019-efo3bbvh/final`, including `regression-command.json`, `regression.log`, `regression.xml`, `regression-result.json`, `legacy-command.json`, `legacy.log`, `legacy.xml`, `legacy-result.json`, `verification-summary.json`, `prefix-equivalence.json`, `changed-file-qa.json`, `runtime-fingerprint.json`, `environment-list-comparison.json`, `formal-c16-preserved-sources.json`, `formal-c16-source-trees.tar.gz`, the reviewed golden derivation and the separate delivery scope/manifest/snapshot. Earlier stage failures and interruptions remain in the parent directory and the dated records above.

## 2026-10-19 — User-authorized pytest timeout policy

The user explicitly requested changing 300 seconds to 450 seconds. B00C29 freezes this narrow corrective scope and overrides only the shared outer pytest runner limit, including its existing batch and collection callers. This is an acceptance-time-budget adjustment, not an additional runtime optimization. Existing tests, helpers, golden bytes, source generation, validators, Session binding, production budgets and other child limits remain unchanged. Formal verification and delivery are recorded separately in `../completions/B00C29_COMPLETION.md`; B05 is not executed. Earlier 300-second records remain historical facts.

Verification completed on input `d8ecdb29931504a72f45e270a5240e986e4f4193e0152e574e79b485cfef346c`: 37 existing evidence/final/process-hook tests passed in 30.69 seconds; the original `test_meta_004` real subprocess rejection probe passed in 4.04 seconds, covering the existing pass/skip/xfail/xpass/setup/teardown/stale/unknown/duplicate/deselect cases. The actual `run_pytest_batches(batch_size=1)` invocation of C21 triple_success passed in 395.88 child-pytest seconds under 450 seconds; original `validate_pytest`, `validate_observations` and Session unchanged checks pass. The outer formal phase, including input loading and post-validation, took 424.17 seconds. No assertion or golden change was needed. Evidence and the separate delivery manifest are in `/private/tmp/lqcd-pytest-timeout-450-20261019-c3jyn79c`; the retained formal ownership ledger is `/private/tmp/lqcd-agent-pytest-0hhfa5rz/directories.jsonl`. Current full 4,785-node regression remains pending and B05 stays review.
