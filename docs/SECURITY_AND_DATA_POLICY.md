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
- the Phase 10C internal statistical command `analysis:run_synthetic_benchmark:<scenario_path>` only when the exact command string is configured in the case allowlist
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

Phase 10C statistical benchmark runs may write support files such as `synthetic_benchmark_input.json`, `synthetic_data.csv`, and `fit_summary.json` under `analysis_outputs/`. These files are audit support artifacts; they are not accepted results and do not enter the Phase 4 expected-output acceptance contract unless a future validator explicitly adds them.

## Secrets Policy

Real provider credentials must be local-only and must not be committed, printed, logged, or copied into artifacts. `.env`, `.env.*`, and other local secret files are ignored by git except for `.env.example`, which contains placeholder variable names only.

Phase 10 provider configuration reads already-exported environment variables and may load a repo-local `.env` file without overriding exported values. This local `.env` loading is implemented without adding a dotenv dependency. The provider dry-run CLI reports only provider readiness, live-test opt-in status, missing environment variable names, and non-secret configuration metadata; it must never print loaded values.

To configure local credentials safely, copy placeholder names from `.env.example` into a repo-local `.env` or export them in the shell. Do not paste real values into tracked files. Live provider calls are disabled unless `RUN_LIVE_LLM_TESTS=1` is set and the provider-specific key and model variables are present.

## LLM Provider Policy

The deterministic agent path remains the default test path. Phase 10 adds a provider abstraction and secure dry-run configuration for OpenAI and DeepSeek. Phase 10B allows Method Planner, Scientific Reviewer, and Decision Coordinator to call provider-backed structured output only when a provider is injected by tests or `--llm-provider-config` is supplied for the graph CLI. Provider outputs must be validated as structured artifacts before they affect routing. If provider output is invalid JSON or fails schema validation, the caller must write a structured error artifact instead of silently continuing or routing on free-form text.

Provider-backed execution must not downgrade local safety evidence. Reviewer and decision prompts use bounded artifact summaries, not raw numeric data or unbounded logs. Provider reviewer warnings must be structured and evidence-grounded; context-only or ungrounded non-severe cautions are not allowed to become route-changing warning evidence. The Decision Coordinator applies deterministic local evidence policy after provider schema validation: severe warnings, severe diagnostic flags, failed runs, high/critical local evidence, and unusable artifacts remain pending or Human-Gate-routed even if a provider proposes low risk. Unsupported provider Human Gate escalation is also constrained when local evidence only supports low or medium risk. Accepted memory is still allowed only for low-risk structured decisions or valid human approval.

## Human Approval Policy

High and critical risk outcomes require human approval before accepted memory or accepted-result promotion. Medium risk is allowed to proceed to report generation but must remain pending or review-recommended unless a future policy changes this behavior.

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
