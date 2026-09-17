"""Deterministic shortest-path search over a weighted directed GCR."""

from __future__ import annotations

import heapq
import math
from typing import Any


def dijkstra_region_path(
    graph: dict[str, Any],
    edge_weights: dict[tuple[str, str], float],
    start_region: str,
    goal_region: str,
) -> dict[str, Any]:
    """Find the minimum-cost directed path and return a route record."""

    adjacency: dict[str, list[tuple[str, float]]] = {
        vertex["id"]: [] for vertex in graph["vertices"]
    }
    for edge in graph["directed_edges"]:
        key = (edge["source"], edge["target"])
        if key not in edge_weights:
            raise ValueError(f"No validated weight for {key[0]}->{key[1]}")
        adjacency[key[0]].append((key[1], edge_weights[key]))

    distances = {region_id: math.inf for region_id in adjacency}
    distances[start_region] = 0.0
    previous: dict[str, str] = {}
    queue: list[tuple[float, str]] = [(0.0, start_region)]

    while queue:
        cost, current = heapq.heappop(queue)
        if cost != distances[current]:
            continue
        if current == goal_region:
            break
        for neighbor, weight in adjacency[current]:
            candidate = cost + weight
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = current
                heapq.heappush(queue, (candidate, neighbor))

    if math.isinf(distances[goal_region]):
        return {
            "start_region": start_region,
            "goal_region": goal_region,
            "sequence": [],
            "edges": [],
            "total_cost": None,
            "valid": False,
            "reason": f"No directed path exists from {start_region} to {goal_region}.",
        }

    sequence = [goal_region]
    while sequence[-1] != start_region:
        sequence.append(previous[sequence[-1]])
    sequence.reverse()

    route_edges = []
    for source, target in zip(sequence, sequence[1:]):
        route_edges.append(
            {"source": source, "target": target, "weight": edge_weights[(source, target)]}
        )
    return {
        "start_region": start_region,
        "goal_region": goal_region,
        "sequence": sequence,
        "edges": route_edges,
        "total_cost": round(distances[goal_region], 12),
        "valid": True,
    }
