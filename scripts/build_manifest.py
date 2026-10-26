"""Record immutable build inputs once, outside the invocation path."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/lqcd_agent"

def render():
    sources = {str(p.relative_to(PACKAGE)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(PACKAGE.rglob("*.py")) if "demo" not in p.relative_to(PACKAGE).parts}
    return json.dumps({"schema_version": "1", "application_build": hashlib.sha256(
        json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "graph_topology": sources["graph/analysis_graph.py"], "sources": sources}, indent=2) + "\n"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = PACKAGE / "_build_manifest.json"
    value = render()
    if args.check:
        if output.read_text() != value:
            raise SystemExit("Regenerate with python scripts/build_manifest.py")
    else:
        output.write_text(value)
