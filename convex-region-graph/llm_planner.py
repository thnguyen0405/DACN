#!/usr/bin/env python3
"""Assign LLM edge costs and find a valid directed region sequence."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

from graph_utils import load_json_object, prepare_planning_graph, require_region
from llm_weight_provider import (
    DuplicateEdgeWeightWarning,
    LLMProviderError,
    LLMWeightProvider,
    OpenRouterWeightProvider,
    load_dotenv,
    validate_edge_weights,
)
from route_visualization import route_svg
from weighted_search import dijkstra_region_path


def plan_route(
    raw_graph: dict[str, Any],
    start_region: str,
    goal_region: str,
    weight_response: dict[str, Any] | None = None,
    provider: LLMWeightProvider | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, str], float], list[tuple[str, str]]]:
    graph = prepare_planning_graph(raw_graph)
    require_region(graph, start_region, "start")
    require_region(graph, goal_region, "goal")
    if weight_response is None:
        if provider is None:
            raise LLMProviderError("A weight response or LLM provider is required")
        weight_response = provider.get_edge_weights(graph, start_region, goal_region)
    weights, missing = validate_edge_weights(weight_response, graph)
    route = dijkstra_region_path(graph, weights, start_region, goal_region)
    return route, graph, weights, missing


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path, help="GCR JSON file")
    parser.add_argument("--start", required=True, help="Start region ID")
    parser.add_argument("--goal", required=True, help="Goal region ID")
    parser.add_argument("--provider", choices=["openrouter"], default="openrouter")
    parser.add_argument("--weights", type=Path, help="Reuse a JSON weight response; skips the API")
    parser.add_argument("--weights-output", type=Path, default=Path("outputs/llm_weights.json"))
    parser.add_argument("--route-output", type=Path, default=Path("outputs/route.json"))
    parser.add_argument("--svg-output", type=Path, default=Path("outputs/route.svg"))
    parser.add_argument("--prompt", type=Path, default=Path(__file__).parent / "prompts" / "edge_weight_prompt.txt")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        print("Loading GCR...")
        raw_graph = load_json_object(args.graph)
        graph = prepare_planning_graph(raw_graph)
        print(f"\nStart region: {args.start}\nGoal region: {args.goal}\n")
        print(f"Directed edges loaded: {len(graph['directed_edges'])}\n")

        provider = None
        if args.weights:
            print(f"Reusing weights from {args.weights}; API call skipped.")
            response = load_json_object(args.weights)
        else:
            load_dotenv(args.env_file)
            print("Calling LLM API...")
            provider = OpenRouterWeightProvider(args.prompt)
            response = provider.get_edge_weights(graph, args.start, args.goal)
            metadata = response.get("provider_metadata", {})
            requested_model = metadata.get("requested_model") or provider.model
            print(f"Requested model: {requested_model}")
            resolved_model = metadata.get("resolved_model")
            if resolved_model:
                print(f"Resolved model: {resolved_model}")
            args.weights_output.parent.mkdir(parents=True, exist_ok=True)
            args.weights_output.write_text(
                json.dumps(response, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"Saved LLM response to {args.weights_output}")

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DuplicateEdgeWeightWarning)
            route, graph, weights, missing = plan_route(
                raw_graph, args.start, args.goal, weight_response=response, provider=provider
            )
        duplicate_count = sum(
            issubclass(item.category, DuplicateEdgeWeightWarning)
            for item in caught_warnings
        )
        if duplicate_count:
            noun = "record" if duplicate_count == 1 else "records"
            print(
                f"Warning: ignored {duplicate_count} identical duplicate "
                f"LLM edge-weight {noun}."
            )
        print(f"\nValidated weights for {len(weights)} directed edges.")
        if missing:
            print(f"Warning: assigned neutral weight 0.5 to {len(missing)} missing edges.")
        print("Running Dijkstra...\n")

        args.route_output.parent.mkdir(parents=True, exist_ok=True)
        args.route_output.write_text(
            json.dumps(route, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        args.svg_output.parent.mkdir(parents=True, exist_ok=True)
        args.svg_output.write_text(route_svg(graph, weights, route), encoding="utf-8")
        if route["valid"]:
            print("Selected region sequence:\n")
            print(" -> ".join(route["sequence"]))
            print(f"\nTotal LLM cost: {route['total_cost']}")
        else:
            print(route["reason"])
        print(f"Route JSON: {args.route_output}\nRoute SVG:  {args.svg_output}")
        return 0 if route["valid"] else 2
    except (OSError, ValueError, LLMProviderError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
