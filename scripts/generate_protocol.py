"""Generate the runtime declaration from the standalone current contract."""
import argparse
import hashlib
import json
from pathlib import Path
import pprint

ROOT = Path(__file__).resolve().parents[1]

def render():
    raw = (ROOT / "contracts/control.json").read_bytes()
    value = json.loads(raw)
    assert value["state_machines"]["control_operation"]["operations"]
    source = next(row for row in value["evidence_unions"] if row["union_id"] == "SourceSnapshotProof")
    assert source["valid_schema_revision_combinations"]
    assert all(row["source_schema"] == "0.4" for row in source["valid_schema_revision_combinations"])
    header = '"""Generated from contracts/control.json; do not edit."""\nfrom types import MappingProxyType\n\ndef _freeze(value):\n    if isinstance(value, dict):\n        return MappingProxyType({key: _freeze(item) for key, item in value.items()})\n    if isinstance(value, list):\n        return tuple(_freeze(item) for item in value)\n    return value\n\n'
    return header + 'PROTOCOL_SHA256 = ' + repr(hashlib.sha256(raw).hexdigest()) + '\nPROTOCOL = _freeze(' + pprint.pformat(value, sort_dicts=False, width=110) + ')\n'

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "src/lqcd_agent/control/_generated_protocol.py"
    expected = render()
    if args.check:
        if output.read_text() != expected:
            raise SystemExit("Regenerate with python scripts/generate_protocol.py")
    else:
        output.write_text(expected)
