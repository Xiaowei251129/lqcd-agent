"""Load all acceptance inputs and verify independent contract and inventory seals."""
import importlib.util
from pathlib import Path

from .contracts import ROOT, DIGEST_KEYS, load_contracts, required_ids
from .strict_json import read, sha, require
from .matrix import validate_matrix
from .inventory import validate_inventory

PATHS = {
    "protocol": "docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json",
    "catalog": "docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json",
    "generated_protocol": "src/lqcd_agent/control/_generated_protocol.py",
    "matrix": "tests/phase_b/acceptance_matrix.json",
    "registry": "tests/phase_b/failpoint_registry.json",
    "final_obligations": "tests/phase_b/final_obligations.json",
}


def load_inputs(root=ROOT):
    root = Path(root).resolve()
    protocol, catalog = load_contracts(root)
    spec = importlib.util.spec_from_file_location("phase_b_generator", root / "scripts/generate_phase_b_protocol.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    require((root / PATHS["generated_protocol"]).read_bytes() == generator.render(protocol), "projection", "byte_equal")
    matrix, registry, obligations = (read(root / PATHS[k]) for k in ("matrix", "registry", "final_obligations"))
    slices, covered = validate_matrix(matrix, catalog, root)
    specs = validate_inventory(registry, obligations, protocol, root, matrix["scenarios"])
    return {"root": root, "protocol": protocol, "catalog": catalog, "matrix": matrix, "registry": registry,
            "obligations": obligations, "specs": specs, "slices": slices, "covered": covered,
            "required": required_ids(catalog), "digests": {k: sha((root / p).read_bytes()) for k, p in PATHS.items()}}
