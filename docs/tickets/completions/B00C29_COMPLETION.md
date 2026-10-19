# B00C29 Completion Record

2026-10-19: completed. The user explicitly authorized “把300 秒限制改成450秒”. This approval supersedes only the shared outer pytest runner's historical 300-second restriction. The ready body is frozen in the worktree and `/private/tmp/lqcd-pytest-timeout-450-20261019-c3jyn79c/ready-ticket.md`; there is no committed snapshot. Its body SHA-256 is `96d635b660b4d26c3311db3ccc9ef493927cf41382aeea8ca2d0ff670ec1bc05`; only YAML lifecycle changed after freezing.

The implementation changes exactly one literal in `tests/phase_b/harness/pytest_evidence.py`: `timeout=300` to `timeout=450`. Existing batch and collection callers share that same path. No configuration knob, wrapper, fallback, new test implementation or production optimization was added. Existing tests/assertions, helpers, source generation, golden bytes, validators, Session binding, production budgets/deadlines, other child limits, protocol/catalog/matrix/owners and historical ticket/completion records remain unchanged.

Verification on the frozen tested input `d8ecdb29931504a72f45e270a5240e986e4f4193e0152e574e79b485cfef346c`:

- Existing evidence/final and process-hook modules: **37 passed in 30.69 seconds**, no failures/errors/skips.
- Existing `test_acceptance_foundation.py::test_meta_004`: **1 passed in 4.04 seconds**. Its original real subprocess probes reject skip/xfail/xpass, setup/teardown failures, stale/unknown/duplicate evidence and deselection while accepting the valid case.
- Original C21 `test_product_retry_has_exact_sources[triple_success]` through actual `run_pytest_batches(batch_size=1)`: **1 passed in 395.88 child-pytest seconds** under the new **450-second** subprocess cap. All original two-fresh-source, authorization/grant, exact-trace and idempotence assertions remain. Original envelope/observation validators and Session unchanged checks pass; no B04 ownership is claimed.
- The outer formal phase takes 424.17 seconds including input loading and post-validation; its child has the actual 450-second cap. The earlier 422.545-second direct result remains bound to its old input and is not retagged. These runs are not a controlled speedup comparison.
- All three commands verify unchanged repository inputs. This is **39 passing outer checks**, not a full 4,785-node run. Production source bytes and runtime fingerprint remain unchanged, so no expected hashes need synchronization.

Evidence: `/private/tmp/lqcd-pytest-timeout-450-20261019-c3jyn79c`, including ready ticket/authorization, before and tested manifests, tested snapshot/proof, quick command/log/XML/result, formal command/result and `c21-session/` raw requests/envelopes/stdout, rejection command/log/XML/result and verification summary. Formal fixture sources are retained under `/private/tmp`; their ownership ledger is `/private/tmp/lqcd-agent-pytest-0hhfa5rz/directories.jsonl`.

Current README/index/state, verification guide, decision log, maintenance record, Phase B overview and B05 review draft are synchronized. Compile, relative links, diff and final scope checks are saved with the separate delivery manifest; subsequent documentation/lifecycle changes do not relabel the tested input. B05 remains review and unimplemented; complete current-input regression and its original integration acceptance remain pending. No commit or push was performed.
