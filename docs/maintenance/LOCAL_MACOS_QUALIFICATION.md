# Local macOS qualification

This contract-preserving maintenance fixes local execution on the current canonical workflow. Milestone status remains in [Current state](../REPO_CURRENT_STATE.md).

## Defects and repair

- The Codex backend used Linux `/proc` for every process identity, boot identity and process-group query. On macOS, dispatch and stop could not complete. It now reads the native BSD process start timestamp, including microseconds, and enumerates live process-group members with the native `ps` command. Unknown or unreadable identity is rejected rather than treated as verified termination.
- The macOS Host clock generated a random epoch per CLI process. Resume could not recognize a still-valid monotonic interval from Start. Host clock and Code backend now share the OS boot identity; the per-process random fallback was removed. Unsupported or unavailable boot identity fails before dispatch.
- The SDK worker test intercepted every subprocess launch. It now intercepts only the worker it intends to simulate, allowing native identity queries to execute normally.

The Code backend interface, frozen protocol, path permissions, proposal-only execution, PID fence, stop ownership and scientific acceptance policy are unchanged. No second workflow or unrestricted execution fallback was added.

## Evidence

The local `.venv` is independently installed from `requirements.lock`. The private `.env` is ignored, has mode `0600`, and its key is absent from tracked files and child environments.

- `check-results/integration.json`: latest full-suite attempt; its referenced fresh root retains the raw JUnit and benchmark when executed. The original failed attempt remains under `/private/tmp/lqcd-agent-check-1651evpf/`.
- `check-results/offline-scientific-local.json`: canonical offline preparation with registered effective-mass analysis and scientific review. Seven adjacent-time estimates reproduce the known synthetic mass `0.4`; this is a numerical calibration, not physics acceptance.
- `check-results/outbound-prompt-preview.json` and `outbound-scope.json`: request previews generated without API calls. They contain the synthetic case and program interfaces, with no real research data.
- `check-results/live-codex-local.json`: actual operator-authorized SDK generation, Host application/sealing, independent syntax verification and fresh Analysis returning `2`. Read-only status and byte-identical repeated Resume passed. The check reported 9,885 total tokens and took 55.29 seconds.
- `check-results/live-scientific-local.json`: actual Responses planning and scientific review around registered numerical analysis of the explicit synthetic CSV. Both provider traces identify OpenAI and `gpt-6-luna`; all seven mass estimates match `0.4`. The Run remains at Human Gate and the review labels its conclusion as calibration only.
- `check-results/local-qualification.json`: combined qualification, current application build, and credential scan. No application key was found in scanned local runtime evidence or tracked files; the SDK persisted no `auth.json`.
- `check-results/run_local_qualification.py`: the operator-authorized live check used for the two results above. The earlier OLCF ignored reports are not present in this checkout; their recorded claims remain distinct from this local execution.

The real process checks cover stopping a worker and a child that ignores SIGTERM, refusing changed PID/boot identities before signalling, repeat dispatch conflicts, cancellation, and stable clock epochs in a fresh CLI process. Linux-specific runtime behavior has not been rerun on this macOS machine.

## Remaining boundary

The CLI coding task remains `sample.py`. This maintenance does not implement a general execution sandbox or automatic scientific-code development. A missing analysis implementation still pauses, and scientific acceptance still belongs to the human researcher. The operator supplied the additional outbound authorization, and both local live checks executed successfully; that authorization does not constitute a scientific acceptance decision.
