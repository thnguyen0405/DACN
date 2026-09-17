"""Loading and validation helpers for Part 3 planning graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GraphValidationError(ValueError):
    """Raised when a GCR cannot safely be used by the planner."""


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GraphValidationError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GraphValidationError(f"Expected a JSON object in {path}")
    return value


def prepare_planning_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Return a validated copy of the directed graph supplied by Part 1.

    ``undirected_edges`` is intentionally never read here.  A directed edge is
    identified by its (source, target) pair, which also makes weight lookup
    unambiguous.
    """

    vertices = graph.get("vertices")
    directed_edges = graph.get("directed_edges")
    if not isinstance(vertices, list):
        raise GraphValidationError("Graph field 'vertices' must be a list")
    if not isinstance(directed_edges, list):
        raise GraphValidationError("Graph field 'directed_edges' must be a list")

    region_ids: set[str] = set()
    clean_vertices: list[dict[str, Any]] = []
    for index, vertex in enumerate(vertices):
        if not isinstance(vertex, dict) or not isinstance(vertex.get("id"), str):
            raise GraphValidationError(f"Vertex {index} must have a string 'id'")
        region_id = vertex["id"]
        if region_id in region_ids:
            raise GraphValidationError(f"Duplicate region id: {region_id}")
        centroid = vertex.get("centroid")
        if (
            not isinstance(centroid, list)
            or len(centroid) != 2
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in centroid)
        ):
            raise GraphValidationError(f"Region {region_id} must have a numeric 2D centroid")
        region_ids.add(region_id)
        clean_vertices.append(dict(vertex))

    clean_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    for index, edge in enumerate(directed_edges):
        if not isinstance(edge, dict):
            raise GraphValidationError(f"Directed edge {index} must be an object")
        source, target, relation = edge.get("source"), edge.get("target"), edge.get("relation")
        if not isinstance(source, str) or not isinstance(target, str):
            raise GraphValidationError(f"Directed edge {index} needs string source and target")
        if source not in region_ids or target not in region_ids:
            raise GraphValidationError(f"Directed edge {source}->{target} references an unknown region")
        if not isinstance(relation, str):
            raise GraphValidationError(f"Directed edge {source}->{target} needs a relation")
        key = (source, target)
        if key in seen_edges:
            raise GraphValidationError(f"Duplicate directed edge: {source}->{target}")
        seen_edges.add(key)
        clean_edges.append(dict(edge))

    return {
        "directed": True,
        "vertices": clean_vertices,
        "directed_edges": clean_edges,
    }


def require_region(graph: dict[str, Any], region_id: str, role: str) -> None:
    known = {vertex["id"] for vertex in graph["vertices"]}
    if region_id not in known:
        raise GraphValidationError(f"Unknown {role} region: {region_id}")
