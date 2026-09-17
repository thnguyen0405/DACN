"""Dependency-free SVG rendering for a weighted directed route."""

from __future__ import annotations

import html
import math
from typing import Any


def route_svg(
    graph: dict[str, Any], edge_weights: dict[tuple[str, str], float], route: dict[str, Any],
    width: int = 1000, height: int = 700,
) -> str:
    vertices = graph["vertices"]
    polygon_points = [p for vertex in vertices for p in vertex.get("polygon", [])]
    if not polygon_points:
        polygon_points = [vertex["centroid"] for vertex in vertices]
    min_x, max_x = min(p[0] for p in polygon_points), max(p[0] for p in polygon_points)
    min_y, max_y = min(p[1] for p in polygon_points), max(p[1] for p in polygon_points)
    span_x, span_y = max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)
    margin = 80
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)

    def transform(point: list[float]) -> tuple[float, float]:
        used_w, used_h = span_x * scale, span_y * scale
        offset_x, offset_y = (width - used_w) / 2, (height - used_h) / 2
        return (
            offset_x + (point[0] - min_x) * scale,
            height - offset_y - (point[1] - min_y) * scale,
        )

    selected = {(edge["source"], edge["target"]) for edge in route["edges"]}
    positions = {vertex["id"]: transform(vertex["centroid"]) for vertex in vertices}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/></marker><marker id="route-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#dc2626"/></marker></defs>',
        '<text x="500" y="32" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700">LLM-weighted directed GCR route</text>',
    ]
    for vertex in vertices:
        polygon = vertex.get("polygon", [])
        if polygon:
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in map(transform, polygon))
            lines.append(f'<polygon points="{points}" fill="#dbeafe" fill-opacity="0.52" stroke="#94a3b8" stroke-width="1.5"/>')

    for edge in graph["directed_edges"]:
        source, target = edge["source"], edge["target"]
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        dx, dy = x2 - x1, y2 - y1
        length = max(math.hypot(dx, dy), 1e-9)
        ux, uy = dx / length, dy / length
        offset = 5 if source < target else -5
        px, py = -uy * offset, ux * offset
        sx, sy = x1 + ux * 25 + px, y1 + uy * 25 + py
        tx, ty = x2 - ux * 25 + px, y2 - uy * 25 + py
        is_selected = (source, target) in selected
        color, marker, stroke = ("#dc2626", "route-arrow", 3.6) if is_selected else ("#64748b", "arrow", 1.2)
        lines.append(f'<line x1="{sx:.2f}" y1="{sy:.2f}" x2="{tx:.2f}" y2="{ty:.2f}" stroke="{color}" stroke-width="{stroke}" marker-end="url(#{marker})"/>')
        mx, my = (sx + tx) / 2 - uy * 7, (sy + ty) / 2 + ux * 7
        weight = edge_weights[(source, target)]
        lines.append(f'<text x="{mx:.2f}" y="{my:.2f}" text-anchor="middle" font-family="Arial" font-size="10" fill="{color}" paint-order="stroke" stroke="#f8fafc" stroke-width="3">{weight:.2f}</text>')

    route_regions = set(route["sequence"])
    for vertex in vertices:
        cx, cy = positions[vertex["id"]]
        on_route = vertex["id"] in route_regions
        fill = "#fee2e2" if on_route else "#e2e8f0"
        stroke = "#dc2626" if on_route else "#334155"
        lines.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="22" fill="{fill}" stroke="{stroke}" stroke-width="{3 if on_route else 2}"/>')
        label = html.escape(vertex["id"])
        lines.append(f'<text x="{cx:.2f}" y="{cy+5:.2f}" text-anchor="middle" font-family="Arial" font-size="14" font-weight="700">{label}</text>')

    sequence = " → ".join(route["sequence"]) if route["valid"] else route.get("reason", "No route")
    lines.append(f'<text x="500" y="680" text-anchor="middle" font-family="Arial" font-size="15" fill="#0f172a">{html.escape(sequence)}</text>')
    lines.append("</svg>")
    return "\n".join(lines)
