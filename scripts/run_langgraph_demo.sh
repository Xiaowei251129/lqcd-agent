#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${LQCD_AGENT_OUTPUT_DIR:-outputs}"
RUN_ID="${LQCD_AGENT_RUN_ID:-golden_demo_$(date -u +%Y%m%d_%H%M%S)}"

cd "${REPO_ROOT}"

python -m lqcd_agent.graph.run_graph \
  --case configs/cases/l64c64a076_m140.yaml \
  --output-dir "${OUTPUT_DIR}" \
  --run-id "${RUN_ID}"

echo "demo_output=${OUTPUT_DIR}/l64c64a076_m140/${RUN_ID}"
