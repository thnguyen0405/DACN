#!/usr/bin/env python3
"""Merge GCR polygons and validated LLM region scores for the C++ sampler."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from export_sampling_corridor import validated_polygon
from graph_utils import load_json_object, prepare_planning_graph, require_region
from llm_region_prior import validate_region_scores
from llm_weight_provider import LLMProviderError


def build_sampling_prior(
    raw_graph: dict[str, Any], prior: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    graph = prepare_planning_graph(raw_graph)
    start_region, goal_region = prior.get("start_region"), prior.get("goal_region")
    if not isinstance(start_region, str) or not isinstance(goal_region, str):
        raise ValueError("Region-prior file needs string start_region and goal_region")
    require_region(graph, start_region, "start")
    require_region(graph, goal_region, "goal")
    scores, missing = validate_region_scores(prior, graph)

    polygons = {
        vertex["id"]: validated_polygon(vertex["id"], vertex.get("polygon"))
        for vertex in raw_graph["vertices"]
    }
    return {
        "start_region": start_region,
        "goal_region": goal_region,
        "regions": [
            {
                "id": vertex["id"],
                "score": scores[vertex["id"]],
                "polygon": polygons[vertex["id"]],
            }
            for vertex in graph["vertices"]
        ],
    }, missing


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path, help="Part 1 graph.json")
    parser.add_argument("--prior", required=True, type=Path, help="Validated region_prior.json")
    parser.add_argument("--output", required=True, type=Path, help="Sampling-prior output JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        sampling_prior, missing = build_sampling_prior(
            load_json_object(args.graph), load_json_object(args.prior)
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(sampling_prior, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Exported {len(sampling_prior['regions'])} scored regions to {args.output}")
        if missing:
            print(f"Applied documented fallback scores to: {', '.join(missing)}")
        return 0
    except (OSError, ValueError, LLMProviderError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
