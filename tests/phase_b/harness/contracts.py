"""Read the independently frozen Phase A contract, never a test-defined substitute."""
from functools import lru_cache
import importlib.util
from pathlib import Path

from .strict_json import Invalid, require, sha, loads

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_DIR = ROOT / "docs/tickets/phase-a-control-contracts"
PROTOCOL_SHA = "7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8"
CATALOG_SHA = "ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726"
META_IDS = tuple(f"A07-META-{n:03d}" for n in range(1, 16))
TICKETS = ("B00", "B01", "B02", "B03", "B04")
EXIT_CHECKS = tuple([f"layer_{n}" for n in range(6)] + [
    "cross_system_fault_concurrency", "phase_b_suite", "full_pytest", "compileall",
    "synthetic_tests", "full_mock_benchmark", "legacy_regression", "cli_smoke", "documentation_scope",
])
DIGEST_KEYS = ("protocol", "catalog", "generated_protocol", "matrix", "registry", "final_obligations", "worktree_inputs")


@lru_cache(maxsize=1)
def design():
    spec = importlib.util.spec_from_file_location(
        "phase_a_frozen_validator", ROOT / "scripts/validate_phase_a_control_protocol.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_contracts(root=ROOT):
    directory = Path(root) / "docs/tickets/phase-a-control-contracts"
    raw_protocol = (directory / "CONTROL_PROTOCOL_0_4.json").read_bytes()
    raw_catalog = (directory / "PHASE_B_REQUIREMENT_CATALOG.json").read_bytes()
    require(sha(raw_protocol) == PROTOCOL_SHA, "protocol", "sha256")
    require(sha(raw_catalog) == CATALOG_SHA, "catalog", "sha256")
    protocol, catalog = loads(raw_protocol), loads(raw_catalog)
    try:
        design()._validate_protocol(protocol)
        design()._validate_catalog(catalog, PROTOCOL_SHA)
    except design().ValidationError as exc:
        raise Invalid("contract", "semantics") from exc
    return protocol, catalog


def required_ids(catalog):
    return [r["requirement_id"] for r in catalog["requirements"] if r["required"]]


def projection(protocol):
    excluded = {"source_documents", "status", "digest_policy"}
    return {key: value for key, value in protocol.items() if key not in excluded}
