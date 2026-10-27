# Local macOS qualification

This contract-preserving maintenance fixes local execution on the current canonical workflow. Milestone status remains in [Current state](../REPO_CURRENT_STATE.md).

## Current-version closeout, 2026-10-27

Runtime execution now targets the operator's MacBook. Retired cluster storage configuration, mount admission and configuration overrides were deleted. The canonical scratch parent is `/private/tmp`; unsupported runtime platforms are rejected. Native disk, private-directory, PID/boot, WAL/FULL, immutable publication and human-confirmation checks remain unchanged. Platform-specific tests that returned early on macOS were replaced with actual native checks; the lower suite count does not remove Mac behavior coverage.

- `check-results/integration.json` references the final raw report `/private/tmp/lqcd-agent-check-448sa7xc/result.json`. The affected selection also passed 15 tests. The first edit of the new permission test targeted the trusted Coordinator rather than public Host lookup; the corrected test checks the actual public permission boundary. Its failed attempt remains in `/private/tmp/lqcd-agent-check-gpgoy27p/`.
- `check-results/macbook-current/doctor.json` verifies the native filesystem and actual SQLite pragmas without an API call.
- `check-results/macbook-current/live-codex-local.json` records the authorized bounded proposal, Host application and verification, read-only status, idempotent Resume and absence of persisted SDK authentication. It completed in 53.59 seconds with 9,916 reported tokens.
- `check-results/macbook-current/live-scientific-local.json` records authorized Responses planning and scientific review on the existing synthetic calibration CSV. Seven mass estimates match `0.4`; the Run remains at Human Gate with pending approval and no terminal scientific acceptance. It completed in 33.96 seconds.
- `check-results/macbook-current/outbound-review.json` records the explicitly approved outbound scope; previous live evidence below was not overwritten.
- `check-results/macbook-current/local-qualification.json` combines the matching source/build identity and outcomes. The exact application key was absent from 389 scanned tracked/evidence files across both live Hosts. The private `.env` remains mode `0600`; it, synthetic raw data and local evidence remain ignored.
- The previous HEAD's [remote CI run](https://github.com/Xiaowei251129/lqcd-agent/actions/runs/40572049478) failed before starting a job. The invalid job-level `runner.temp` expression was moved to each Linux run step, where that context is available. A regression check covers job-level contexts; remote verification requires a new push.

## Defects and repair

- The Codex backend used Linux `/proc` for every process identity, boot identity and process-group query. On macOS, dispatch and stop could not complete. It now reads the native BSD process start timestamp, including microseconds, and enumerates live process-group members with the native `ps` command. Unknown or unreadable identity is rejected rather than treated as verified termination.
- The macOS Host clock generated a random epoch per CLI process. Resume could not recognize a still-valid monotonic interval from Start. Host clock and Code backend now share the OS boot identity; the per-process random fallback was removed. Unsupported or unavailable boot identity fails before dispatch.
- The SDK worker test intercepted every subprocess launch. It now intercepts only the worker it intends to simulate, allowing native identity queries to execute normally.

The Code backend interface, frozen protocol, path permissions, proposal-only execution, PID fence, stop ownership and scientific acceptance policy are unchanged. No second workflow or unrestricted execution fallback was added.

## Earlier local evidence

The local `.venv` is independently installed from `requirements.lock`. The private `.env` is ignored, has mode `0600`, and its key is absent from tracked files and child environments.

- `check-results/integration.json`: latest full-suite attempt; its referenced fresh root retains the raw JUnit and benchmark when executed. The original failed attempt remains under `/private/tmp/lqcd-agent-check-1651evpf/`.
- `check-results/offline-scientific-local.json`: canonical offline preparation with registered effective-mass analysis and scientific review. Seven adjacent-time estimates reproduce the known synthetic mass `0.4`; this is a numerical calibration, not physics acceptance.
- `check-results/outbound-prompt-preview.json` and `outbound-scope.json`: request previews generated without API calls. They contain the synthetic case and program interfaces, with no real research data.
- `check-results/live-codex-local.json`: actual operator-authorized SDK generation, Host application/sealing, independent syntax verification and fresh Analysis returning `2`. Read-only status and byte-identical repeated Resume passed. The check reported 9,885 total tokens and took 55.29 seconds.
- `check-results/live-scientific-local.json`: actual Responses planning and scientific review around registered numerical analysis of the explicit synthetic CSV. Both provider traces identify OpenAI and `gpt-6-luna`; all seven mass estimates match `0.4`. The Run remains at Human Gate and the review labels its conclusion as calibration only.
- `check-results/local-qualification.json`: combined qualification, current application build, and credential scan. No application key was found in scanned local runtime evidence or tracked files; the SDK persisted no `auth.json`.
- `check-results/run_local_qualification.py`: the operator-authorized live check used for the two results above.

The real process checks cover stopping a worker and a child that ignores SIGTERM, refusing changed PID/boot identities before signalling, repeat dispatch conflicts, cancellation, and stable clock epochs in a fresh CLI process. Current runtime qualification is native macOS.

## Remaining boundary

The CLI coding task remains `sample.py`. This maintenance does not implement a general execution sandbox or automatic scientific-code development. A missing analysis implementation still pauses, and scientific acceptance still belongs to the human researcher. The operator supplied the additional outbound authorization, and both local live checks executed successfully; that authorization does not constitute a scientific acceptance decision.
