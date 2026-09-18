#!/usr/bin/env python3
"""Turn a safe-portal graph into an LLM-guided region prior and route.

The LLM may rank existing regions and/or existing directed safe-portal edges.
It never creates geometry or edges: topology validation and Dijkstra remain
deterministic local code.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from build_graph import regions_from_map


class PlanningError(ValueError):
    """Raised when a graph or model response is unsafe or malformed."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanningError(f"Cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlanningError(f"{path} must contain one JSON object")
    return value


def is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def point_on_segment(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float], tol: float) -> bool:
    cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
    if abs(cross) > tol:
        return False
    return (
        min(a[0], b[0]) - tol <= point[0] <= max(a[0], b[0]) + tol
        and min(a[1], b[1]) - tol <= point[1] <= max(a[1], b[1]) + tol
    )


def point_in_polygon(point: tuple[float, float], polygon: list[list[float]], tol: float = 1e-9) -> bool:
    """Inclusive ray-casting test; a point on a region boundary is accepted."""
    vertices = [(float(p[0]), float(p[1])) for p in polygon]
    for index, a in enumerate(vertices):
        if point_on_segment(point, a, vertices[(index + 1) % len(vertices)], tol):
            return True
    x, y = point
    inside = False
    for index, a in enumerate(vertices):
        b = vertices[(index + 1) % len(vertices)]
        if (a[1] > y) == (b[1] > y):
            continue
        if a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) > x:
            inside = not inside
    return inside


def prepare_safe_portal_graph(raw_graph: dict[str, Any]) -> dict[str, Any]:
    """Validate and retain only directed edges that are real safe portals."""
    raw_vertices = raw_graph.get("vertices")
    raw_edges = raw_graph.get("directed_edges")
    if raw_graph.get("directed") is not True:
        raise PlanningError("Graph must declare directed: true")
    if not isinstance(raw_vertices, list) or not isinstance(raw_edges, list):
        raise PlanningError("Graph needs 'vertices' and 'directed_edges' lists")

    vertices: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, vertex in enumerate(raw_vertices):
        if not isinstance(vertex, dict) or not isinstance(vertex.get("id"), str):
            raise PlanningError(f"Vertex {index} needs a string id")
        region_id = vertex["id"]
        centroid = vertex.get("centroid")
        polygon = vertex.get("polygon")
        if region_id in ids:
            raise PlanningError(f"Duplicate region id: {region_id}")
        if not isinstance(centroid, list) or len(centroid) != 2 or not all(is_number(v) for v in centroid):
            raise PlanningError(f"Region {region_id} needs a numeric centroid")
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise PlanningError(f"Region {region_id} needs a polygon with at least 3 vertices")
        if any(not isinstance(p, list) or len(p) != 2 or not all(is_number(v) for v in p) for p in polygon):
            raise PlanningError(f"Region {region_id} has an invalid polygon")
        ids.add(region_id)
        vertices.append(dict(vertex))

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, edge in enumerate(raw_edges):
        if not isinstance(edge, dict):
            raise PlanningError(f"Directed edge {index} must be an object")
        source, target = edge.get("source"), edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str) or source not in ids or target not in ids:
            raise PlanningError(f"Directed edge {index} has an unknown endpoint")
        if edge.get("relation") != "safe_portal":
            raise PlanningError(f"Directed edge {source}->{target} is not a safe_portal")
        if not is_number(edge.get("safe_portal_width")) or float(edge["safe_portal_width"]) <= 0.0:
            raise PlanningError(f"Directed edge {source}->{target} needs a positive safe_portal_width")
        key = (source, target)
        if key in seen:
            raise PlanningError(f"Duplicate directed edge: {source}->{target}")
        seen.add(key)
        edges.append(dict(edge))

    planning = raw_graph.get("planning")
    if planning is not None and not isinstance(planning, dict):
        raise PlanningError("Graph planning metadata must be an object")
    return {"directed": True, "vertices": vertices, "directed_edges": edges, "planning": planning or {}}


def resolve_region(graph: dict[str, Any], role: str, explicit_id: str | None) -> str:
    """Use an explicit region or locate the map start/goal inside an ACD piece."""
    known = {vertex["id"] for vertex in graph["vertices"]}
    if explicit_id is not None:
        if explicit_id not in known:
            raise PlanningError(f"Unknown {role} region: {explicit_id}")
        return explicit_id

    point = graph["planning"].get(role)
    if not isinstance(point, list) or len(point) != 2 or not all(is_number(v) for v in point):
        raise PlanningError(f"Provide --{role}-region, or include planning.{role} in graph.json")
    candidates = sorted(
        vertex["id"]
        for vertex in graph["vertices"]
        if point_in_polygon((float(point[0]), float(point[1])), vertex["polygon"])
    )
    if not candidates:
        raise PlanningError(f"planning.{role} is not inside any convex region")
    # A point on a decomposition boundary belongs to more than one closed region.
    # Use lexical ordering so identical graph input always yields the same plan.
    return candidates[0]


def parse_response(response: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    region_scores = response.get("region_scores", [])
    edge_costs = response.get("edge_costs", [])
    if not isinstance(region_scores, list) or not isinstance(edge_costs, list):
        raise PlanningError("LLM response fields region_scores and edge_costs must be lists")
    if not region_scores and not edge_costs:
        raise PlanningError("LLM response must include at least one region score or edge cost")
    return region_scores, edge_costs


def validate_model_response(
    response: dict[str, Any], graph: dict[str, Any]
) -> tuple[dict[str, float], dict[tuple[str, str], float], list[str], list[tuple[str, str]]]:
    """Reject invented IDs/edges; fill only omitted values with deterministic defaults."""
    raw_scores, raw_costs = parse_response(response)
    ids = {vertex["id"] for vertex in graph["vertices"]}
    valid_edges = {(edge["source"], edge["target"]) for edge in graph["directed_edges"]}
    scores: dict[str, float] = {}
    costs: dict[tuple[str, str], float] = {}

    for index, item in enumerate(raw_scores):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not is_number(item.get("score")):
            raise PlanningError(f"region_scores[{index}] needs string id and numeric score")
        region_id, score = item["id"], float(item["score"])
        if region_id not in ids:
            raise PlanningError(f"LLM score references unknown region: {region_id}")
        if region_id in scores:
            raise PlanningError(f"Duplicate LLM score for region: {region_id}")
        if not 0.0 <= score <= 1.0:
            raise PlanningError(f"Score for {region_id} must be between 0 and 1")
        scores[region_id] = score

    for index, item in enumerate(raw_costs):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("source"), str)
            or not isinstance(item.get("target"), str)
            or not is_number(item.get("cost"))
        ):
            raise PlanningError(f"edge_costs[{index}] needs source, target and numeric cost")
        key = (item["source"], item["target"])
        cost = float(item["cost"])
        if key not in valid_edges:
            raise PlanningError(f"LLM cost references nonexistent safe portal: {key[0]}->{key[1]}")
        if key in costs:
            raise PlanningError(f"Duplicate LLM cost for edge: {key[0]}->{key[1]}")
        if not 0.0 <= cost <= 1.0:
            raise PlanningError(f"Cost for {key[0]}->{key[1]} must be between 0 and 1")
        costs[key] = cost

    missing_scores = sorted(ids - scores.keys())
    for region_id in missing_scores:
        scores[region_id] = 0.5
    missing_costs = sorted(valid_edges - costs.keys())
    for source, target in missing_costs:
        # High region importance means an attractive destination, hence lower cost.
        costs[(source, target)] = 1.0 - (scores[source] + scores[target]) / 2.0
    return scores, costs, missing_scores, missing_costs


def sampling_prior(scores: dict[str, float], temperature: float, exploration: float) -> dict[str, float]:
    """Convert scores to probabilities while preserving a non-zero exploration floor."""
    if temperature <= 0.0:
        raise PlanningError("temperature must be positive")
    if not 0.0 <= exploration < 1.0:
        raise PlanningError("exploration must be in [0, 1)")
    max_score = max(scores.values())
    exponentials = {region_id: math.exp((score - max_score) / temperature) for region_id, score in scores.items()}
    total = sum(exponentials.values())
    uniform = 1.0 / len(scores)
    return {
        region_id: (1.0 - exploration) * exponentials[region_id] / total + exploration * uniform
        for region_id in sorted(scores)
    }


def dijkstra(graph: dict[str, Any], costs: dict[tuple[str, str], float], start: str, goal: str) -> dict[str, Any]:
    adjacency: dict[str, list[tuple[str, float]]] = {vertex["id"]: [] for vertex in graph["vertices"]}
    for edge in graph["directed_edges"]:
        key = (edge["source"], edge["target"])
        adjacency[key[0]].append((key[1], costs[key]))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[1], item[0]))

    distances = {region_id: math.inf for region_id in adjacency}
    previous: dict[str, str] = {}
    distances[start] = 0.0
    queue: list[tuple[float, str]] = [(0.0, start)]
    while queue:
        cost, current = heapq.heappop(queue)
        if cost != distances[current]:
            continue
        if current == goal:
            break
        for neighbor, edge_cost in adjacency[current]:
            candidate = cost + edge_cost
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = current
                heapq.heappush(queue, (candidate, neighbor))

    if math.isinf(distances[goal]):
        return {"valid": False, "sequence": [], "edges": [], "total_cost": None, "reason": f"No safe directed path from {start} to {goal}."}
    sequence = [goal]
    while sequence[-1] != start:
        sequence.append(previous[sequence[-1]])
    sequence.reverse()
    return {
        "valid": True,
        "sequence": sequence,
        "edges": [
            {"source": source, "target": target, "cost": round(costs[(source, target)], 8)}
            for source, target in zip(sequence, sequence[1:])
        ],
        "total_cost": round(distances[goal], 8),
    }


def plan_regions(
    raw_graph: dict[str, Any], response: dict[str, Any], start_region: str | None = None,
    goal_region: str | None = None, temperature: float = 0.25, exploration: float = 0.12,
) -> dict[str, Any]:
    """Build the LLM region prior and a topology-valid region sequence."""
    graph = prepare_safe_portal_graph(raw_graph)
    start = resolve_region(graph, "start", start_region)
    goal = resolve_region(graph, "goal", goal_region)
    scores, costs, missing_scores, missing_costs = validate_model_response(response, graph)
    prior = sampling_prior(scores, temperature, exploration)
    route = dijkstra(graph, costs, start, goal)
    return {
        "schema": "llm_region_prior/v1",
        "start_region": start,
        "goal_region": goal,
        "sampling_prior": [
            {"id": region_id, "score": round(scores[region_id], 8), "probability": round(prior[region_id], 8)}
            for region_id in sorted(scores)
        ],
        "prior_parameters": {"temperature": temperature, "exploration": exploration},
        "edge_costs": [
            {"source": source, "target": target, "cost": round(cost, 8)}
            for (source, target), cost in sorted(costs.items())
        ],
        "model_completion": {
            "neutral_score_regions": missing_scores,
            "derived_edge_costs": [{"source": s, "target": t} for s, t in missing_costs],
        },
        "route": {"start_region": start, "goal_region": goal, **route},
    }


def load_dotenv(path: Path) -> None:
    """Load a small local .env without replacing an existing environment value."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def compact_llm_input(graph: dict[str, Any], start: str, goal: str) -> dict[str, Any]:
    return {
        "start_region": start,
        "goal_region": goal,
        "regions": [
            {"id": vertex["id"], "centroid": vertex["centroid"], "area": vertex.get("area")}
            for vertex in graph["vertices"]
        ],
        "safe_portals": [
            {
                "source": edge["source"], "target": edge["target"],
                "width": edge["safe_portal_width"], "clearance": edge.get("required_clearance", 0.0),
            }
            for edge in graph["directed_edges"]
        ],
    }


def call_openai(graph: dict[str, Any], start: str, goal: str, prompt_path: Path, model: str, api_key: str) -> dict[str, Any]:
    """Call an OpenAI Responses model with a strict JSON schema; optional at runtime."""
    prompt = prompt_path.read_text(encoding="utf-8").rstrip() + "\n\nGRAPH DATA:\n" + json.dumps(
        compact_llm_input(graph, start, goal), ensure_ascii=False
    )
    schema = {
        "type": "object",
        "properties": {
            "region_scores": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "score": {"type": "number"}, "reason": {"type": "string"}}, "required": ["id", "score", "reason"], "additionalProperties": False}},
            "edge_costs": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "target": {"type": "string"}, "cost": {"type": "number"}, "reason": {"type": "string"}}, "required": ["source", "target", "cost", "reason"], "additionalProperties": False}},
        },
        "required": ["region_scores", "edge_costs"],
        "additionalProperties": False,
    }
    request_body = {
        "model": model,
        "input": prompt,
        "store": False,
        "text": {"format": {"type": "json_schema", "name": "region_prior", "strict": True, "schema": schema}},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as http_response:
            payload = json.loads(http_response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise PlanningError(f"OpenAI API returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PlanningError(f"OpenAI API request failed: {exc}") from exc
    output_text = payload.get("output_text")
    if not isinstance(output_text, str):
        raise PlanningError("OpenAI response did not contain output_text")
    try:
        response = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise PlanningError(f"OpenAI returned invalid JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise PlanningError("OpenAI response must be a JSON object")
    return response


def route_svg(graph: dict[str, Any], plan: dict[str, Any], width: int = 1000, height: int = 700) -> str:
    """Render a compact review artifact; red means the selected region sequence."""
    vertices = graph["vertices"]
    points = [point for vertex in vertices for point in vertex["polygon"]]
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span_x, span_y = max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)
    margin = 70
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)

    def transform(point: list[float]) -> tuple[float, float]:
        return margin + (point[0] - min_x) * scale, height - margin - (point[1] - min_y) * scale

    prior = {item["id"]: item["probability"] for item in plan["sampling_prior"]}
    selected = {(edge["source"], edge["target"]) for edge in plan["route"]["edges"]}
    positions = {vertex["id"]: transform(vertex["centroid"]) for vertex in vertices}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/></marker><marker id="route" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#dc2626"/></marker></defs>',
        '<text x="500" y="30" text-anchor="middle" font-family="Arial" font-size="21" font-weight="700">LLM-guided safe-region prior and route</text>',
    ]
    for vertex in vertices:
        shade = int(235 - min(prior[vertex["id"]] * 700, 150))
        polygon = " ".join(f"{x:.2f},{y:.2f}" for x, y in (transform(point) for point in vertex["polygon"]))
        lines.append(f'<polygon points="{polygon}" fill="rgb({shade},{shade + 8},255)" stroke="#94a3b8" stroke-width="1.2"/>')
    for edge in graph["directed_edges"]:
        source, target = edge["source"], edge["target"]
        x1, y1, x2, y2 = *positions[source], *positions[target]
        dx, dy = x2 - x1, y2 - y1
        length = max(math.hypot(dx, dy), 1e-9)
        ux, uy = dx / length, dy / length
        selected_edge = (source, target) in selected
        color, marker, stroke = ("#dc2626", "route", 3.5) if selected_edge else ("#64748b", "arrow", 1.0)
        lines.append(f'<line x1="{x1 + ux * 18:.2f}" y1="{y1 + uy * 18:.2f}" x2="{x2 - ux * 18:.2f}" y2="{y2 - uy * 18:.2f}" stroke="{color}" stroke-width="{stroke}" marker-end="url(#{marker})"/>')
    route_regions = set(plan["route"]["sequence"])
    for vertex in vertices:
        x, y = positions[vertex["id"]]
        on_route = vertex["id"] in route_regions
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="19" fill="{"#fee2e2" if on_route else "#e2e8f0"}" stroke="{"#dc2626" if on_route else "#334155"}" stroke-width="{3 if on_route else 1.5}"/>')
        lines.append(f'<text x="{x:.2f}" y="{y + 4:.2f}" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">{vertex["id"]}</text>')
        lines.append(f'<text x="{x:.2f}" y="{y + 34:.2f}" text-anchor="middle" font-family="Arial" font-size="10">P={prior[vertex["id"]]:.2f}</text>')
    sequence = " → ".join(plan["route"]["sequence"]) if plan["route"]["valid"] else plan["route"]["reason"]
    lines.append(f'<text x="500" y="680" text-anchor="middle" font-family="Arial" font-size="14" fill="#0f172a">{sequence}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def combined_svg(
    graph: dict[str, Any], plan: dict[str, Any], map_geometry: dict[str, Any],
    width: int = 1500, height: int = 700,
) -> str:
    """Put the input map and the LLM-weighted graph in one reviewable SVG."""
    panel_width = width / 2.0
    boundary = map_geometry["boundary"]
    obstacles = map_geometry["obstacles"]
    points = [tuple(point) for point in boundary]
    min_x, max_x = min(point[0] for point in points), max(point[0] for point in points)
    min_y, max_y = min(point[1] for point in points), max(point[1] for point in points)
    span_x, span_y = max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)
    margin = 70
    scale = min((panel_width - 2 * margin) / span_x, (height - 2 * margin) / span_y)
    used_width, used_height = span_x * scale, span_y * scale
    offset_x, offset_y = (panel_width - used_width) / 2, (height - used_height) / 2

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        return offset_x + (point[0] - min_x) * scale, height - offset_y - (point[1] - min_y) * scale

    def polygon_points(polygon: list[tuple[float, float]]) -> str:
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in (transform(point) for point in polygon))

    # Reuse the tested graph/LLM renderer, then place it in the right panel.
    graph_markup = route_svg(graph, plan, width=width - int(panel_width), height=height)
    graph_body = graph_markup[graph_markup.find(">") + 1 : graph_markup.rfind("</svg>")]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<line x1="{panel_width:.2f}" y1="24" x2="{panel_width:.2f}" y2="{height - 24}" stroke="#cbd5e1" stroke-width="2"/>',
        f'<text x="{panel_width / 2:.2f}" y="32" text-anchor="middle" font-family="Arial" font-size="21" font-weight="700">Input map</text>',
        f'<text x="{panel_width + (width - panel_width) / 2:.2f}" y="32" text-anchor="middle" font-family="Arial" font-size="21" font-weight="700">Graph + LLM prior + route</text>',
        f'<polygon points="{polygon_points([tuple(point) for point in boundary])}" fill="#dbeafe" stroke="#0f172a" stroke-width="3"/>',
    ]
    for obstacle in obstacles:
        lines.append(
            f'<polygon points="{polygon_points([tuple(point) for point in obstacle])}" fill="#334155" stroke="#0f172a" stroke-width="2"/>'
        )
    planning = map_geometry.get("planning", {})
    for label, color in (("start", "#16a34a"), ("goal", "#dc2626")):
        point = planning.get(label)
        if point is None:
            continue
        x, y = transform((float(point[0]), float(point[1])))
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="9" fill="{color}" stroke="white" stroke-width="3"/>')
        lines.append(f'<text x="{x + 13:.2f}" y="{y + 5:.2f}" fill="{color}" font-family="Arial" font-size="15" font-weight="700">{label}</text>')
    lines.append(f'<g transform="translate({panel_width:.2f},0)">{graph_body}</g>')
    lines.append("</svg>")
    return "\n".join(lines)


def export_sampling_prior(graph: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Build the small C++ sampler interface without exposing raw LLM JSON artifacts."""
    probability = {item["id"]: item["probability"] for item in plan["sampling_prior"]}
    return {
        "start_region": plan["start_region"],
        "goal_region": plan["goal_region"],
        "regions": [
            {
                "id": vertex["id"],
                "score": round(probability[vertex["id"]], 8),
                "polygon": vertex["polygon"],
            }
            for vertex in graph["vertices"]
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path, help="Safe-portal graph.json produced by build_graph.py")
    parser.add_argument("--response", type=Path, help="Offline LLM JSON response; no network call")
    parser.add_argument("--provider", choices=["openai"], help="Call a model when --response is absent")
    parser.add_argument("--start-region", help="Override automatic start-region lookup")
    parser.add_argument("--goal-region", help="Override automatic goal-region lookup")
    parser.add_argument("--temperature", type=float, default=0.25, help="Softmax temperature for region scores")
    parser.add_argument("--exploration", type=float, default=0.12, help="Uniform probability mixed into the prior")
    parser.add_argument("--svg", type=Path, default=Path("outputs/llm_route.svg"), help="Visible LLM prior/route SVG")
    parser.add_argument(
        "--sampling-prior-output",
        type=Path,
        default=Path("outputs/sampling_prior.json"),
        help="Internal C++ sampler interface; this is not a raw LLM output",
    )
    parser.add_argument("--map", type=Path, help="Original map JSON; enables a combined map + graph + LLM SVG")
    parser.add_argument("--prompt", type=Path, default=Path(__file__).parent / "prompts" / "region_prior_prompt.txt")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw_graph = load_json(args.graph)
        graph = prepare_safe_portal_graph(raw_graph)
        start = resolve_region(graph, "start", args.start_region)
        goal = resolve_region(graph, "goal", args.goal_region)
        if args.response:
            response = load_json(args.response)
            source = f"offline response: {args.response}"
        else:
            if args.provider != "openai":
                raise PlanningError("Provide --response for offline use, or choose --provider openai")
            load_dotenv(args.env_file)
            api_key, model = os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_MODEL")
            if not api_key or not model:
                raise PlanningError("OPENAI_API_KEY and OPENAI_MODEL must be set for --provider openai")
            response = call_openai(graph, start, goal, args.prompt, model, api_key)
            source = f"OpenAI model: {model}"
        plan = plan_regions(raw_graph, response, start, goal, args.temperature, args.exploration)
        plan["model_source"] = source
        args.svg.parent.mkdir(parents=True, exist_ok=True)
        if args.map:
            _regions_data, map_geometry = regions_from_map(load_json(args.map))
            args.svg.write_text(combined_svg(graph, plan, map_geometry), encoding="utf-8")
            svg_description = "combined map + graph + LLM SVG"
        else:
            args.svg.write_text(route_svg(graph, plan), encoding="utf-8")
            svg_description = "LLM route SVG"
        args.sampling_prior_output.parent.mkdir(parents=True, exist_ok=True)
        args.sampling_prior_output.write_text(
            json.dumps(export_sampling_prior(graph, plan), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Start region: {start}; goal region: {goal}")
        print("Sequence: " + (" -> ".join(plan["route"]["sequence"]) if plan["route"]["valid"] else plan["route"]["reason"]))
        print(f"{svg_description}: {args.svg}")
        print(f"C++ sampling prior: {args.sampling_prior_output}")
        return 0 if plan["route"]["valid"] else 2
    except (OSError, PlanningError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
