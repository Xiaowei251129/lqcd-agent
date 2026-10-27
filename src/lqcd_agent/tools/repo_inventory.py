"""Installed scientific capabilities in an operator-owned workspace."""
from pathlib import Path
from lqcd_agent.analysis_programs import program_inventory


def build_repo_inventory(root):
    return {'schema_version': '0.1', 'repo_root': str(Path(root)),
        'implementation_gaps': [], 'analysis_programs': program_inventory(),
        'analysis_program_guidance': 'Reuse existing analysis_programs entries when possible. A missing implementation requires a scoped coding decision.'}
