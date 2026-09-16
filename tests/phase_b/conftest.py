"""Load the local evidence writer without altering the global pytest configuration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import pytest_evidence


def pytest_configure(config):
    if not config.pluginmanager.hasplugin("harness.pytest_evidence"):
        pytest_evidence.pytest_configure(config)


def pytest_unconfigure(config):
    pytest_evidence.pytest_unconfigure(config)
