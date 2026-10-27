"""Inspect the actual deployment without loading credentials or calling a model."""
from contextlib import closing
from importlib import metadata
import platform
import sqlite3
import tempfile
from pathlib import Path

from .control.coordinator import Coordinator
from .control.storage import execution_scratch_root
from .settings import workspace_root


def doctor():
    parent = execution_scratch_root()
    with tempfile.TemporaryDirectory(prefix='lqcd-agent-doctor-', dir=parent) as scratch:
        with closing(Coordinator(Path(scratch))) as coordinator:
            pragmas = {name: coordinator.connection.execute('PRAGMA ' + name).fetchone()[0]
                       for name in ('journal_mode', 'synchronous', 'foreign_keys')}
            filesystem = coordinator.filesystem
    return {'passed': True, 'platform': platform.system(), 'python': platform.python_version(),
        'sqlite': sqlite3.sqlite_version, 'filesystem': filesystem, 'pragmas': pragmas,
        'workspace': str(workspace_root()), 'scratch_parent': str(parent),
        'dependencies': {name: metadata.version(name) for name in ('lqcd-agent', 'openai', 'openai-codex')},
        'live_api_called': False}
