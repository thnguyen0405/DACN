"""Shared deterministic scoring and feature normalisation.

This module is deliberately separate from provider code: its outputs are a
heuristic baseline/fallback and must never be described as LLM inference.
"""

from __future__ import annotations

import math
from typing import Any

NEUTRAL_REGION_SCORE = 0.5
MIN_EDGE_COST = 0.01


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _normalizer(values: list[float | None]):
    known = [value for value in values if value is not None]
    if not known or math.isclose(min(known), max(known)):
        return lambda value: 0.5
    low, high = min(known), max(known)
    return lambda value: 0.5 if value is None else (value - low) / (high - low)


def _distance(a: list[float], b: list[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _required_bottlenecks(graph: dict[str, Any], start: str, goal: str) -> set[str]:
    adjacency = {vertex["id"]: set() for vertex in graph["vertices"]}
    for edge in graph["directed_edges"]:
        adjacency[edge["source"]].add(edge["target"])

    required: set[str] = set()
    for removed in adjacency:
        if removed in (start, goal):
            continue
        queue = [start]
        seen = {removed, start}
        while queue:
            current = queue.pop()
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        if goal not in seen:
            required.add(removed)
    return required


def deterministic_region_score_records(
    graph: dict[str, Any], start: str, goal: str
) -> list[dict[str, Any]]:
    """Return explainable non-AI scores in [0, 1] for comparison/testing."""

    vertices = graph["vertices"]
    by_id = {vertex["id"]: vertex for vertex in vertices}
    start_c = by_id[start]["centroid"]
    goal_c = by_id[goal]["centroid"]
    route_span = max(_distance(start_c, goal_c), 1e-12)

    areas = [_finite(vertex.get("area") or vertex.get("descriptors", {}).get("area")) for vertex in vertices]
    clearances = [_finite(vertex.get("descriptors", {}).get("mean_clearance")) for vertex in vertices]
    degrees = [_finite(vertex.get("descriptors", {}).get("safe_degree")) for vertex in vertices]
    aspects = [_finite(vertex.get("descriptors", {}).get("aspect_ratio")) for vertex in vertices]
    compactness = [_finite(vertex.get("descriptors", {}).get("compactness")) for vertex in vertices]
    norm_area, norm_clearance = _normalizer(areas), _normalizer(clearances)
    norm_degree, norm_aspect, norm_compact = _normalizer(degrees), _normalizer(aspects), _normalizer(compactness)
    bottlenecks = _required_bottlenecks(graph, start, goal)

    records: list[dict[str, Any]] = []
    for index, vertex in enumerate(vertices):
        region_id = vertex["id"]
        distance_to_goal = _distance(vertex["centroid"], goal_c)
        progress = max(0.0, min(1.0, 1.0 - distance_to_goal / route_span))
        detour = max(0.0, min(1.0, (distance_to_goal - route_span) / route_span))
        shape_quality = 1.0 - 0.5 * (norm_aspect(aspects[index]) + norm_compact(compactness[index]))
        contributions = {
            "base": 0.20,
            "goal_progress": 0.24 * progress,
            "connectivity": 0.14 * norm_degree(degrees[index]),
            "clearance": 0.14 * norm_clearance(clearances[index]),
            "size": 0.08 * norm_area(areas[index]),
            "shape": 0.08 * shape_quality,
            "detour_penalty": -0.12 * detour,
            "required_bottleneck": 0.20 if region_id in bottlenecks else 0.0,
            "endpoint": 0.12 if region_id in (start, goal) else 0.0,
        }
        score = max(0.0, min(1.0, sum(contributions.values())))
        active = ", ".join(f"{key}={value:+.3f}" for key, value in contributions.items() if value)
        records.append({
            "id": region_id,
            "score": round(score, 8),
            "reason": "Deterministic heuristic (not LLM): " + active,
            "contributions": {key: round(value, 8) for key, value in contributions.items()},
        })
    return records


def deterministic_edge_cost_records(
    graph: dict[str, Any], region_scores: dict[str, float], goal: str
) -> list[dict[str, Any]]:
    """Score only existing directed edges using geometry plus destination score."""

    by_id = {vertex["id"]: vertex for vertex in graph["vertices"]}
    goal_c = by_id[goal]["centroid"]
    lengths = [_distance(by_id[e["source"]]["centroid"], by_id[e["target"]]["centroid"]) for e in graph["directed_edges"]]
    widths = [_finite(e.get("portal_width")) for e in graph["directed_edges"]]
    safe_widths = [_finite(e.get("safe_portal_width")) for e in graph["directed_edges"]]
    traversability = [_finite(e.get("safe_traversability")) for e in graph["directed_edges"]]
    norm_length, norm_width = _normalizer(lengths), _normalizer(widths)
    norm_safe_width, norm_traversability = _normalizer(safe_widths), _normalizer(traversability)

    records: list[dict[str, Any]] = []
    for index, edge in enumerate(graph["directed_edges"]):
        source, target = edge["source"], edge["target"]
        before = _distance(by_id[source]["centroid"], goal_c)
        after = _distance(by_id[target]["centroid"], goal_c)
        scale = max(before, after, 1e-12)
        progress = max(-1.0, min(1.0, (before - after) / scale))
        components = {
            "base": 0.18,
            "relative_length": 0.22 * norm_length(lengths[index]),
            "portal_width_penalty": 0.15 * (1.0 - norm_width(widths[index])),
            "safe_width_penalty": 0.15 * (1.0 - norm_safe_width(safe_widths[index])),
            "clearance_penalty": 0.12 * (1.0 - norm_traversability(traversability[index])),
            "goal_progress": -0.10 * progress,
            "detour_penalty": 0.08 * max(0.0, -progress),
            "destination_score": 0.10 * (1.0 - region_scores.get(target, NEUTRAL_REGION_SCORE)),
        }
        cost = max(MIN_EDGE_COST, min(1.0, sum(components.values())))
        active = ", ".join(f"{key}={value:+.3f}" for key, value in components.items() if value)
        records.append({
            "source": source,
            "target": target,
            "cost": round(cost, 8),
            "reason": "Deterministic heuristic (not LLM): " + active,
            "contributions": {key: round(value, 8) for key, value in components.items()},
        })
    return records


def deterministic_scoring(graph: dict[str, Any], start: str, goal: str) -> dict[str, Any]:
    regions = deterministic_region_score_records(graph, start, goal)
    scores = {record["id"]: record["score"] for record in regions}
    return {
        "scoring_mode": "deterministic_heuristic",
        "region_scores": regions,
        "edge_costs": deterministic_edge_cost_records(graph, scores, goal),
    }
