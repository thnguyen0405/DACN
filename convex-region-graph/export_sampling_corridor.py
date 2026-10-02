#!/usr/bin/env python3
"""Export the Part 3 route as the strict polygon corridor consumed by Part 2."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


class CorridorExportError(ValueError):
    """Raised when graph/route data cannot form a sampling corridor."""


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorridorExportError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorridorExportError(f"Expected a JSON object in {path}")
    return value


def validated_polygon(region_id: str, polygon: Any) -> list[list[float]]:
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise CorridorExportError(
            f"Region {region_id} must have a polygon with at least three points"
        )

    clean: list[list[float]] = []
    for index, point in enumerate(polygon):
        if (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in point
            )
        ):
            raise CorridorExportError(
                f"Region {region_id} polygon point {index} must contain two finite numbers"
            )
        clean.append([float(point[0]), float(point[1])])
    return clean


def validated_point(label: str, point: Any) -> list[float]:
    if (
        not isinstance(point, (list, tuple))
        or len(point) != 2
        or any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(float(value)) for value in point)
    ):
        raise CorridorExportError(f"{label} must contain two finite numbers")
    return [float(point[0]), float(point[1])]


def build_sampling_corridor(
    graph: dict[str, Any], route: dict[str, Any], prior: dict[str, Any] | None = None,
    guided_probability: float = 0.8, portal_probability: float = 0.2,
) -> dict[str, Any]:
    """Return an ordered sequence strategy while preserving the legacy corridor fields."""

    if not math.isfinite(guided_probability) or not 0.0 <= guided_probability <= 1.0:
        raise CorridorExportError("guided_probability must be in [0, 1]")
    if not math.isfinite(portal_probability) or not 0.0 <= portal_probability <= 1.0:
        raise CorridorExportError("portal_probability must be in [0, 1]")

    if isinstance(route.get("route"), dict):
        route = route["route"]
    vertices = graph.get("vertices")
    if not isinstance(vertices, list):
        raise CorridorExportError("Graph field 'vertices' must be a list")

    polygons: dict[str, list[list[float]]] = {}
    for index, vertex in enumerate(vertices):
        if not isinstance(vertex, dict) or not isinstance(vertex.get("id"), str):
            raise CorridorExportError(f"Graph vertex {index} must have a string 'id'")
        region_id = vertex["id"]
        if region_id in polygons:
            raise CorridorExportError(f"Duplicate graph region id: {region_id}")
        polygons[region_id] = validated_polygon(region_id, vertex.get("polygon"))

    sequence = route.get("sequence")
    if not isinstance(sequence, list) or not sequence:
        raise CorridorExportError("Route field 'sequence' must be a non-empty list")
    if any(not isinstance(region_id, str) for region_id in sequence):
        raise CorridorExportError("Every route sequence entry must be a string region id")
    if len(set(sequence)) != len(sequence):
        raise CorridorExportError("Route sequence must not contain duplicate region ids")

    unknown = [region_id for region_id in sequence if region_id not in polygons]
    if unknown:
        raise CorridorExportError(
            "Route references unknown graph region(s): " + ", ".join(unknown)
        )

    scores = {region_id: 1.0 for region_id in sequence}
    if prior is not None:
        records = prior.get("sampling_prior", prior.get("region_scores"))
        if not isinstance(records, list):
            raise CorridorExportError("Prior needs a sampling_prior or region_scores list")
        supplied: dict[str, float] = {}
        for item in records:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise CorridorExportError("Each prior record needs a string id")
            value = item.get("probability", item.get("score"))
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise CorridorExportError(f"Prior score for {item['id']} must be in [0, 1]")
            if item["id"] in supplied:
                raise CorridorExportError(f"Duplicate prior region id: {item['id']}")
            supplied[item["id"]] = float(value)
        missing = [region_id for region_id in sequence if region_id not in supplied]
        if missing:
            raise CorridorExportError("Prior is missing sequence region(s): " + ", ".join(missing))
        scores = {region_id: supplied[region_id] for region_id in sequence}
        if not any(scores.values()):
            raise CorridorExportError("At least one sequence region must have a positive score")

    edge_lookup = {
        (edge.get("source"), edge.get("target")): edge
        for edge in graph.get("directed_edges", [])
        if isinstance(edge, dict)
    }
    route_portals = []
    if edge_lookup:
        for source, target in zip(sequence, sequence[1:]):
            edge = edge_lookup.get((source, target))
            if edge is None:
                raise CorridorExportError(f"Sequence uses nonexistent directed edge {source}->{target}")
            portal = edge.get("safe_portal")
            if not isinstance(portal, list) or len(portal) != 2:
                raise CorridorExportError(f"Directed edge {source}->{target} has no safe_portal segment")
            route_portals.append({
                "source": source,
                "target": target,
                "segment": [validated_point(f"portal {source}->{target} endpoint", portal[0]),
                            validated_point(f"portal {source}->{target} endpoint", portal[1])],
                "safe_portal_width": edge.get("safe_portal_width"),
            })

    return {
        "schema": "sequence-guided-sampling/v1",
        "sequence": list(sequence),
        "start_region": route.get("start_region", sequence[0]),
        "goal_region": route.get("goal_region", sequence[-1]),
        "guided_probability": guided_probability,
        "global_exploration_probability": round(1.0 - guided_probability, 12),
        "portal_probability_within_guidance": portal_probability,
        "regions": [
            {"id": region_id, "score": scores[region_id], "sequence_index": index,
             "polygon": polygons[region_id]}
            for index, region_id in enumerate(sequence)
        ],
        "portals": route_portals,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path, help="Part 1 graph.json")
    parser.add_argument("--route", required=True, type=Path, help="Part 3 route.json")
    parser.add_argument("--prior", type=Path, help="Optional scored prior/plan JSON")
    parser.add_argument("--guided-probability", type=float, default=0.8)
    parser.add_argument("--portal-probability", type=float, default=0.2)
    parser.add_argument("--output", required=True, type=Path, help="Corridor output JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        corridor = build_sampling_corridor(
            _load_json_object(args.graph), _load_json_object(args.route),
            _load_json_object(args.prior) if args.prior else None,
            args.guided_probability, args.portal_probability,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(corridor, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            f"Exported {len(corridor['regions'])} corridor regions to {args.output}"
        )
        return 0
    except (OSError, CorridorExportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
