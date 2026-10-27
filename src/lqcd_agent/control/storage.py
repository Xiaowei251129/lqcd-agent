"""The fixed, canonical macOS scratch parent for local execution."""
from pathlib import Path
import sys

from .strict_json import require


def execution_scratch_root():
    """Use the native Mac parent; caller environment cannot select a write root."""
    require(sys.platform == "darwin", "Execution requires the qualified macOS platform")
    root = Path("/private/tmp")
    require(root.is_absolute() and root.is_dir() and root == root.resolve() and not root.is_symlink(),
            "Execution scratch must be an existing canonical directory")
    return root
