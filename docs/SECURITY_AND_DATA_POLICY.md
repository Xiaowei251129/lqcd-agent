# Security and Data Policy

## Raw Data Policy

`raw_data/` is immutable and read-only. Agents, command runners, and implementation tasks must not write to it.

During Phase 0 through MVP:

- Real raw numeric data must not be read.
- Raw-data manifests, descriptions, and checksums may be read.
- Synthetic evaluation data must not be stored in `raw_data/`.

Future raw-data-backed evaluation cases require explicit policy and ticket approval.

## Output Policy

Derived actual-run outputs must be written under `<output_root>/<case_id>/<run_id>/` once outputs exist. Repo-local `outputs/` is the ignored actual-run output root and is not a reference-output location. Runs must not overwrite previous runs unless a ticket explicitly allows a force mode and defines its safety behavior.

CLI verification should prefer temporary output roots such as `/private/tmp/lqcd-agent-...`. When `--run-id` is omitted, the CLI generates a timestamped run id. When an explicit run id points to a directory with completed or decision artifacts, the CLI refuses to reuse that run directory.

Future curated evaluation baselines belong under `evaluation/reference_outputs/`, and expected behavior belongs under `evaluation/expected_behavior/`; neither belongs under `outputs/`.

Accepted results and human decisions are append-only or versioned.

## Command Policy

MVP command execution is restricted to an allowlist of mock, test, smoke, and Phase 4 analysis commands.

Analysis execution uses `src/lqcd_agent/tools/command_runner.py`. It may run:

- internal `mock:` commands implemented in the runner, such as the deterministic synthetic matrix-element writer
- local commands only when the exact command string is configured in the case/task allowlist

The analysis command runner blocks shell control operators, commands that are not exact-allowlisted, and paths that reference `raw_data/` or `accepted_results/`. It runs subprocess commands with `shell=False`.

The command runner must record:

- command
- working directory
- timeout
- return code
- stdout/stderr summary
- produced files
- warnings and errors

Commands must not modify `raw_data/`, accepted results, human decision files, secrets, or dependency files unless a future ticket explicitly allows the relevant operation. Analysis run artifacts are written under `<output_root>/<case_id>/<run_id>/`; existing `run_result.json`, `manifest.json`, and `run.log` are not overwritten unless the caller explicitly enables force behavior.

## Secrets Policy

Real provider credentials must be local-only and must not be committed, printed, logged, or copied into artifacts. Live provider tests are disabled by default and require explicit opt-in after provider integration.

## LLM Provider Policy

The deterministic mock provider is the default through MVP. Real providers are deferred until the provider integration phase. Provider outputs must be validated as structured artifacts before they affect routing.

## Human Approval Policy

High and critical risk outcomes require human approval before accepted memory or accepted-result promotion. Medium risk is allowed to proceed to report generation but must remain pending or review-recommended unless a future policy changes this behavior.

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
