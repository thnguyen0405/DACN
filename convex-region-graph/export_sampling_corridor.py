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


def build_sampling_corridor(
    graph: dict[str, Any], route: dict[str, Any]
) -> dict[str, Any]:
    """Return selected graph polygons in exactly ``route.sequence`` order."""

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

    return {
        "sequence": list(sequence),
        "regions": [
            {"id": region_id, "polygon": polygons[region_id]}
            for region_id in sequence
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path, help="Part 1 graph.json")
    parser.add_argument("--route", required=True, type=Path, help="Part 3 route.json")
    parser.add_argument("--output", required=True, type=Path, help="Corridor output JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        corridor = build_sampling_corridor(
            _load_json_object(args.graph), _load_json_object(args.route)
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
