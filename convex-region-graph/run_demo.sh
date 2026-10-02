#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p outputs

echo "[1/4] Map -> ACD convex regions -> safe-portal GCR"
python3 build_graph.py example_map.json \
  --regions-output convex_regions.json \
  --output graph.json \
  --svg graph.svg

echo "[2/4] Offline mock scores -> Dijkstra route -> C++ sampling prior"
python3 llm_region_planner.py graph.json \
  --response examples/mock_llm_region_prior.json \
  --svg outputs/llm_route.svg \
  --map example_map.json \
  --plan-output outputs/region_plan.json \
  --sampling-prior-output outputs/sampling_prior.json

echo "[3/4] Ordered sequence -> mixed sequence/global sampling strategy"
python3 export_sampling_corridor.py \
  --graph graph.json \
  --route outputs/region_plan.json \
  --prior outputs/region_plan.json \
  --guided-probability 0.8 \
  --portal-probability 0.2 \
  --output outputs/sampling_corridor.json

echo "[4/4] Tests"
python3 -m unittest discover -v
python3 export_scoring_dataset.py graph.json --output outputs/scoring_tasks.jsonl

echo
echo "Done."
echo "Open graph.svg for: input map -> ACD convex regions -> graph"
echo "Open outputs/llm_route.svg for: LLM prior + selected route"
echo "C++ interface: outputs/sampling_prior.json"
echo "Sequence strategy: outputs/sampling_corridor.json"
