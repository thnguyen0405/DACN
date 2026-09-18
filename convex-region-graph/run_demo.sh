#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p outputs

echo "[1/3] Map -> ACD convex regions -> safe-portal GCR"
python3 build_graph.py example_map.json \
  --regions-output convex_regions.json \
  --output graph.json \
  --svg graph.svg

echo "[2/3] LLM/mock prior -> Dijkstra route -> SVG + C++ sampling prior"
python3 llm_region_planner.py graph.json \
  --response examples/mock_llm_region_prior.json \
  --svg outputs/llm_route.svg \
  --sampling-prior-output outputs/sampling_prior.json

echo "[3/3] Tests"
python3 -m unittest -v test_build_graph.py test_llm_region_planner.py

echo
echo "Done."
echo "Open graph.svg for: input map -> ACD convex regions -> graph"
echo "Open outputs/llm_route.svg for: LLM prior + selected route"
echo "C++ interface: outputs/sampling_prior.json"
