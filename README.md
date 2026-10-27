# LQCD Agent

An AI Research Partner for LQCD with controlled planning, code/analysis work, scientific review, human decisions and attributable results. Offline mode uses deterministic roles and a Fake coding backend. Explicit live mode uses OpenAI Responses for planning/review and an independent Codex SDK backend for bounded coding proposals. Software checks do not establish physics readiness.

## Use

```bash
source .venv/bin/activate
lqcd-agent --help
lqcd-agent start --key example
lqcd-agent run --case-config configs/example.json --key science
lqcd-agent-demo --port 8000
```

The demo binds to `127.0.0.1`. CLI, demo and scientific cases use the same canonical engine. The CLI returns the Host, Run and Pause identifiers needed for resume, cancel, fork and replay; see each subcommand's `--help`.

## Application API and coding

Create a private `.env` from `.env.example`, set `OPENAI_API_KEY`, and run `chmod 600 .env`. The file is ignored by Git. Planner, reviewer and Codex use this application key; models default to `gpt-6-luna`. Nothing depends on your interactive Codex session or login.

```bash
lqcd-agent run --case-config configs/example.json --live --key live-science
lqcd-agent start --workflow code --live --key live-code
lqcd-agent status --host HOST --case case --run RUN
lqcd-agent resume --host HOST --case case --run RUN --pause PAUSE --key consume-code
```

Copy Host, Run and Pause identifiers from the JSON output. Poll `status` until `coding_backend.status` is `completed`, then resume within the 240-second coding window. Resume applies the bounded proposal, seals it, independently checks syntax and consumes it through the existing control path. Use `cancel` with the same identifiers to stop the original job. Status does not call a model or renew a lease. Backend failures are retained under the private Host's `coding_jobs` directory.

The current coding workflow is a small integration example: change `sample.py` so `value()` returns integer 2. The Host checks its exact allowed AST before execution. Codex proposes UTF-8 files; it cannot run commands or directly edit the workspace. The backend supports macOS process identity and termination as well as Linux. Neither deployment enables arbitrary generated-program execution; OLCF additionally disables the user namespaces needed by Codex command sandboxes. Scientific case planning that requires a new analysis implementation still pauses for a scoped implementation decision; a sample program is never substituted for scientific code.

Live requests transmit the supplied task and selected context to OpenAI and incur API usage. Codex's private job records contain turn IDs and reported token usage; control `llm_calls` counts logical invocations, not transport retries. SDK jobs have a time limit, not a guaranteed dollar/token cap. Use project spending limits for billing control. See [security boundaries](docs/SECURITY_AND_DATA_POLICY.md).

## Develop

```bash
python scripts/check.py                          # 12 critical checks
python scripts/check.py tests/test_analysis_programs.py
python scripts/check.py --integration            # current tests once + numerical benchmark
```

The runner selects this checkout's `.venv`; it never imports a previous checkout. After source edits it regenerates the build manifest once. Standalone CLI users must run `python scripts/build_manifest.py` after editing runtime source; installed builds include the manifest.

Dependencies live in [pyproject.toml](pyproject.toml) and [requirements.lock](requirements.lock). The existing OLCF checkout contains its own ignored `.runtime` and `.venv`. For another installation, create a Python 3.12+ virtual environment, install the lock and this package, and supply an operator-owned storage profile with a supported SQLite runtime. See [verification](docs/VERIFICATION_GUIDE.md).

Current control declarations live in [contracts/control.json](contracts/control.json); regenerate with `python scripts/generate_protocol.py`. Only current Runs are supported. Old runtime paths, historical acceptance, ticket archives and old demo/benchmark implementations have been removed.

[Current state](docs/REPO_CURRENT_STATE.md) · [Architecture](docs/ARCHITECTURE.md) · [Data and security](docs/SECURITY_AND_DATA_POLICY.md)
