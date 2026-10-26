# LQCD Agent

An AI Research Partner for LQCD with controlled planning, code/analysis work, scientific review, human decisions and attributable results. This version uses deterministic scientific roles and a Fake coding backend; it makes no real-provider or physics-readiness claim.

## Use

```bash
source .venv/bin/activate
lqcd-agent --help
lqcd-agent start --key example
lqcd-agent run --case-config configs/example.json --key science
lqcd-agent-demo --port 8000
```

The demo binds to `127.0.0.1`. CLI, demo and scientific cases use the same canonical engine. The CLI returns the Host, Run and Pause identifiers needed for resume, cancel, fork and replay; see each subcommand's `--help`.

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
