#!/usr/bin/env python3
"""Build a directed Graph of Convex Regions from 2D convex polygons.

The implementation intentionally uses only the Python standard library so the
demo is easy to run on a clean machine.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path
from typing import Iterable

Point = tuple[float, float]
Polygon = list[Point]


def cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def signed_area(poly: Polygon) -> float:
    return 0.5 * sum(
        poly[i][0] * poly[(i + 1) % len(poly)][1]
        - poly[(i + 1) % len(poly)][0] * poly[i][1]
        for i in range(len(poly))
    )


def polygon_area(poly: Polygon) -> float:
    return abs(signed_area(poly))


def normalize_polygon(raw: Iterable[Iterable[float]], tol: float) -> Polygon:
    poly = [(float(p[0]), float(p[1])) for p in raw]
    if len(poly) > 1 and distance(poly[0], poly[-1]) <= tol:
        poly.pop()
    if len(poly) < 3:
        raise ValueError("Each region must contain at least three distinct points")
    if signed_area(poly) < 0:
        poly.reverse()
    if polygon_area(poly) <= tol:
        raise ValueError("A region has zero or near-zero area")
    if not is_convex(poly, tol):
        raise ValueError("All input regions must be convex polygons")
    return poly


def is_convex(poly: Polygon, tol: float) -> bool:
    signs = []
    for i in range(len(poly)):
        value = cross(poly[i], poly[(i + 1) % len(poly)], poly[(i + 2) % len(poly)])
        if abs(value) > tol:
            signs.append(value > 0)
    return bool(signs) and all(s == signs[0] for s in signs)


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def edges(poly: Polygon):
    for i, point in enumerate(poly):
        yield point, poly[(i + 1) % len(poly)]


def point_on_segment(p: Point, a: Point, b: Point, tol: float) -> bool:
    if abs(cross(a, b, p)) > tol:
        return False
    return (
        min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol
        and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol
    )


def segments_intersect(a: Point, b: Point, c: Point, d: Point, tol: float) -> bool:
    c1, c2, c3, c4 = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    if ((c1 > tol and c2 < -tol) or (c1 < -tol and c2 > tol)) and (
        (c3 > tol and c4 < -tol) or (c3 < -tol and c4 > tol)
    ):
        return True
    return any(
        (
            abs(value) <= tol and point_on_segment(point, x, y, tol)
            for value, point, x, y in (
                (c1, c, a, b),
                (c2, d, a, b),
                (c3, a, c, d),
                (c4, b, c, d),
            )
        )
    )


def collinear_overlap_length(a: Point, b: Point, c: Point, d: Point, tol: float) -> float:
    if abs(cross(a, b, c)) > tol or abs(cross(a, b, d)) > tol:
        return 0.0
    axis = 0 if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else 1
    lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
    hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
    projected = max(0.0, hi - lo)
    base_projection = abs(b[axis] - a[axis])
    if base_projection <= tol:
        return 0.0
    return projected * distance(a, b) / base_projection


def line_intersection(s: Point, e: Point, a: Point, b: Point, tol: float) -> Point:
    sx, sy = e[0] - s[0], e[1] - s[1]
    ax, ay = b[0] - a[0], b[1] - a[1]
    denominator = sx * ay - sy * ax
    if abs(denominator) <= tol:
        return e
    t = ((a[0] - s[0]) * ay - (a[1] - s[1]) * ax) / denominator
    return s[0] + t * sx, s[1] + t * sy


def convex_intersection(subject: Polygon, clip: Polygon, tol: float) -> Polygon:
    """Sutherland-Hodgman clipping; both polygons must be CCW and convex."""
    output = subject[:]
    for a, b in edges(clip):
        input_points, output = output, []
        if not input_points:
            break
        s = input_points[-1]
        for e in input_points:
            inside_e = cross(a, b, e) >= -tol
            inside_s = cross(a, b, s) >= -tol
            if inside_e:
                if not inside_s:
                    output.append(line_intersection(s, e, a, b, tol))
                output.append(e)
            elif inside_s:
                output.append(line_intersection(s, e, a, b, tol))
            s = e
    return output


def intersection_relation(a: Polygon, b: Polygon, tol: float) -> tuple[str | None, float]:
    """Return an adjacency relation, excluding positive-area polygon overlap."""
    clipped = convex_intersection(a, b, tol)
    area = polygon_area(clipped) if len(clipped) >= 3 else 0.0
    if area > tol:
        return None, 0.0

    shared_length = max(
        (collinear_overlap_length(a1, a2, b1, b2, tol) for a1, a2 in edges(a) for b1, b2 in edges(b)),
        default=0.0,
    )
    if shared_length > tol:
        return "shared_edge", 0.0

    if any(segments_intersect(a1, a2, b1, b2, tol) for a1, a2 in edges(a) for b1, b2 in edges(b)):
        return "point_contact", 0.0
    return None, 0.0


def centroid(poly: Polygon) -> Point:
    area6 = 6.0 * signed_area(poly)
    if abs(area6) < 1e-12:
        return (
            sum(p[0] for p in poly) / len(poly),
            sum(p[1] for p in poly) / len(poly),
        )
    cx = sum(
        (poly[i][0] + poly[(i + 1) % len(poly)][0])
        * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1])
        for i in range(len(poly))
    ) / area6
    cy = sum(
        (poly[i][1] + poly[(i + 1) % len(poly)][1])
        * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1])
        for i in range(len(poly))
    ) / area6
    return cx, cy


def connected_components(vertex_ids: list[str], directed_edges: list[dict]) -> list[list[str]]:
    """Compute weakly connected components from the directed graph."""
    adjacency = {v: set() for v in vertex_ids}
    for edge in directed_edges:
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])
    unseen, components = set(vertex_ids), []
    while unseen:
        start = min(unseen)
        queue, component = deque([start]), []
        unseen.remove(start)
        while queue:
            u = queue.popleft()
            component.append(u)
            for v in sorted(adjacency[u]):
                if v in unseen:
                    unseen.remove(v)
                    queue.append(v)
        components.append(component)
    return components


def build_graph(data: dict, tol: float = 1e-9) -> dict:
    regions = []
    seen = set()
    for item in data["regions"]:
        region_id = str(item["id"])
        if region_id in seen:
            raise ValueError(f"Duplicate region id: {region_id}")
        seen.add(region_id)
        polygon = normalize_polygon(item["polygon"], tol)
        regions.append({"id": region_id, "polygon": polygon, "centroid": centroid(polygon)})

    directed = []
    connection_count = 0
    for i, left in enumerate(regions):
        for right in regions[i + 1 :]:
            relation, area = intersection_relation(left["polygon"], right["polygon"], tol)
            if relation:
                edge = {
                    "source": left["id"],
                    "target": right["id"],
                    "relation": relation,
                    "intersection_area": round(area, 12),
                }
                directed.append(edge)
                directed.append({**edge, "source": right["id"], "target": left["id"]})
                connection_count += 1

    vertices = [
        {
            "id": r["id"],
            "centroid": [round(r["centroid"][0], 8), round(r["centroid"][1], 8)],
            "polygon": [[x, y] for x, y in r["polygon"]],
        }
        for r in regions
    ]
    return {
        "directed": True,
        "vertices": vertices,
        "directed_edges": directed,
        "connected_components": connected_components([r["id"] for r in regions], directed),
        "connection_count": connection_count,
    }


COLORS = ["#ef767a", "#56c271", "#5b9cf0", "#ac72d6", "#f4a259", "#49bec7", "#ed6b9f", "#9bcf53"]


def unique_connections(graph: dict) -> list[dict]:
    """Return one representative edge for each bidirectional region connection."""
    seen: set[tuple[str, str]] = set()
    connections = []
    for edge in graph["directed_edges"]:
        key = tuple(sorted((edge["source"], edge["target"])))
        if key in seen:
            continue
        seen.add(key)
        connections.append(edge)
    return connections


def svg_visualization(graph: dict, width: int = 1200, height: int = 650) -> str:
    vertices = graph["vertices"]
    connections = unique_connections(graph)
    points = [p for v in vertices for p in v["polygon"]]
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span_x, span_y = max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)

    panel_w, margin = width / 2, 55

    def transform(p: Point, panel: int) -> Point:
        scale = min((panel_w - 2 * margin) / span_x, (height - 2 * margin) / span_y)
        used_w, used_h = span_x * scale, span_y * scale
        offset_x = panel * panel_w + (panel_w - used_w) / 2
        offset_y = (height - used_h) / 2
        return offset_x + (p[0] - min_x) * scale, height - offset_y - (p[1] - min_y) * scale

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<line x1="{panel_w}" y1="28" x2="{panel_w}" y2="{height-28}" stroke="#cbd5e1"/>',
        f'<text x="{panel_w/2}" y="30" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700">Convex regions</text>',
        f'<text x="{panel_w+panel_w/2}" y="30" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700">Graph of Convex Regions</text>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/></marker></defs>',
    ]

    for idx, vertex in enumerate(vertices):
        polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (transform(tuple(p), 0) for p in vertex["polygon"]))
        color = COLORS[idx % len(COLORS)]
        lines.append(f'<polygon points="{polygon_points}" fill="{color}" fill-opacity="0.48" stroke="#334155" stroke-width="2"/>')
        cx, cy = transform(tuple(vertex["centroid"]), 0)
        lines.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="18" fill="#0f172a"/>')
        lines.append(f'<text x="{cx:.2f}" y="{cy+5:.2f}" text-anchor="middle" fill="white" font-family="Arial" font-size="13">{vertex["id"]}</text>')

    positions = {v["id"]: transform(tuple(v["centroid"]), 1) for v in vertices}
    for edge in connections:
        x1, y1 = positions[edge["source"]]
        x2, y2 = positions[edge["target"]]
        dx, dy = x2 - x1, y2 - y1
        length = max(math.hypot(dx, dy), 1e-9)
        ux, uy = dx / length, dy / length
        # Two slightly offset arrows show that traversal is bidirectional.
        px, py = -uy * 4, ux * 4
        for reverse in (False, True):
            if reverse:
                sx, sy, tx, ty = x2 - ux * 23 - px, y2 - uy * 23 - py, x1 + ux * 23 - px, y1 + uy * 23 - py
            else:
                sx, sy, tx, ty = x1 + ux * 23 + px, y1 + uy * 23 + py, x2 - ux * 23 + px, y2 - uy * 23 + py
            lines.append(f'<line x1="{sx:.2f}" y1="{sy:.2f}" x2="{tx:.2f}" y2="{ty:.2f}" stroke="#64748b" stroke-width="1.8" marker-end="url(#arrow)"/>')

    for idx, vertex in enumerate(vertices):
        cx, cy = positions[vertex["id"]]
        color = COLORS[idx % len(COLORS)]
        lines.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="22" fill="{color}" stroke="#334155" stroke-width="2"/>')
        lines.append(f'<text x="{cx:.2f}" y="{cy+5:.2f}" text-anchor="middle" fill="#0f172a" font-family="Arial" font-size="14" font-weight="700">{vertex["id"]}</text>')

    counts = {}
    for edge in connections:
        counts[edge["relation"]] = counts.get(edge["relation"], 0) + 1
    summary = ", ".join(f"{key}: {value}" for key, value in sorted(counts.items())) or "no intersections"
    lines.append(f'<text x="{width/2}" y="{height-14}" text-anchor="middle" font-family="Arial" font-size="13" fill="#475569">{len(vertices)} regions · {len(connections)} connections · {summary}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing a 'regions' list")
    parser.add_argument("--output", type=Path, default=Path("graph.json"), help="Output graph JSON")
    parser.add_argument("--svg", type=Path, default=Path("graph.svg"), help="Output visualization SVG")
    parser.add_argument("--tolerance", type=float, default=1e-9, help="Geometry tolerance")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    graph = build_graph(data, args.tolerance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.svg.write_text(svg_visualization(graph), encoding="utf-8")
    print(f"Built {len(graph['vertices'])} vertices and {graph['connection_count']} bidirectional connections")
    print(f"Connected components: {graph['connected_components']}")
    print(f"JSON: {args.output}")
    print(f"SVG:  {args.svg}")


if __name__ == "__main__":
    main()
