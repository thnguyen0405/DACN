#!/usr/bin/env python3
"""Decompose a 2D map into convex regions and build their adjacency graph.

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

#ABxCD
def cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
#cross > 0 = CCW, cross < 0 = CW, cross = 0 = collinear

#Define a polygon is CCW or CW by shoelace formula. 
def signed_area(poly: Polygon) -> float:
    return 0.5 * sum(
        poly[i][0] * poly[(i + 1) % len(poly)][1]
        - poly[(i + 1) % len(poly)][0] * poly[i][1]
        for i in range(len(poly))
    )
#A>0 => CCW, A<0 => CW, A=0 => collinear
#Take the absolute value.  
def polygon_area(poly: Polygon) -> float:
    return abs(signed_area(poly))


def normalize_polygon(raw: Iterable[Iterable[float]], tol: float) -> Polygon:
    poly = [(float(p[0]), float(p[1])) for p in raw]
    if len(poly) > 1 and distance(poly[0], poly[-1]) <= tol:
        poly.pop() #delete the last point if it is the same as the first point
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
        #convex => turn the same direction => all cross have same sign
        if abs(value) > tol:
            signs.append(value > 0)
    return bool(signs) and all(s == signs[0] for s in signs)


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

#traverse the edges
def edges(poly: Polygon):
    for i, point in enumerate(poly):
        yield point, poly[(i + 1) % len(poly)]
#make the last edge connect to the first point

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
        #check if the two segments straddle each other
    ):
        #A va B nam 2 phia khac nhau C va D
        return True
    return any(
        (
            #check if any endpoint of one segment lies on the other segment
            abs(value) <= tol and point_on_segment(point, x, y, tol)
            for value, point, x, y in (
                (c1, c, a, b),
                (c2, d, a, b),
                (c3, a, c, d),
                (c4, b, c, d),
            )
        )
    )


def normalize_map_polygon(raw: Iterable[Iterable[float]], tol: float) -> Polygon:
    """Normalize a simple map boundary without requiring it to be convex."""
    poly = [(float(p[0]), float(p[1])) for p in raw]
    if len(poly) > 1 and distance(poly[0], poly[-1]) <= tol:
        poly.pop()

    cleaned: Polygon = []
    for point in poly:
        if not cleaned or distance(point, cleaned[-1]) > tol:
            cleaned.append(point)
    poly = cleaned

    changed = True
    while changed and len(poly) >= 3:
        changed = False
        for i in range(len(poly)):
            previous = poly[i - 1]
            current = poly[i]
            following = poly[(i + 1) % len(poly)]
            if abs(cross(previous, current, following)) <= tol and point_on_segment(
                current, previous, following, tol
            ):
                poly.pop(i)
                changed = True
                break

    if len(poly) < 3:
        raise ValueError("The map boundary must contain at least three distinct points")
    if polygon_area(poly) <= tol:
        raise ValueError("The map boundary has zero or near-zero area")
    if signed_area(poly) < 0:
        poly.reverse()

    count = len(poly)
    for i, (a, b) in enumerate(edges(poly)):
        for j, (c, d) in enumerate(edges(poly)):
            if j <= i or j == i + 1 or (i == 0 and j == count - 1):
                continue
            if segments_intersect(a, b, c, d, tol):
                raise ValueError("The map boundary must be a simple polygon without self-intersections")
    return poly


def point_in_triangle(point: Point, a: Point, b: Point, c: Point, tol: float) -> bool:
    """Return True when a point is inside or on a CCW triangle."""
    return (
        cross(a, b, point) >= -tol
        and cross(b, c, point) >= -tol
        and cross(c, a, point) >= -tol
    )


def same_point(a: Point, b: Point, tol: float) -> bool:
    return distance(a, b) <= tol


def point_in_polygon(point: Point, poly: Polygon, tol: float) -> bool:
    """Return True for points inside or on the boundary of a polygon."""
    for a, b in edges(poly):
        if point_on_segment(point, a, b, tol):
            return True

    x, y = point
    inside = False
    for a, b in edges(poly):
        if (a[1] > y) == (b[1] > y):
            continue
        intersection_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        if intersection_x > x:
            inside = not inside
    return inside


def rings_intersect(a: Polygon, b: Polygon, tol: float) -> bool:
    return any(segments_intersect(a1, a2, b1, b2, tol) for a1, a2 in edges(a) for b1, b2 in edges(b))


def bridge_is_visible(
    hole_point: Point,
    outer_point: Point,
    combined: Polygon,
    obstacles: list[Polygon],
    outer_boundary: Polygon,
    tol: float,
) -> bool:
    """Check whether a bridge stays entirely inside navigable free space."""
    if same_point(hole_point, outer_point, tol):
        return False

    for ring in [combined, *obstacles]:
        for a, b in edges(ring):
            if not segments_intersect(hole_point, outer_point, a, b, tol):
                continue
            if collinear_overlap_length(hole_point, outer_point, a, b, tol) > tol:
                return False
            touches_bridge_endpoint = any(
                same_point(left, right, tol)
                for left in (hole_point, outer_point)
                for right in (a, b)
            )
            if not touches_bridge_endpoint:
                return False

    for fraction in (0.1, 0.25, 0.5, 0.75, 0.9):
        sample = (
            hole_point[0] + fraction * (outer_point[0] - hole_point[0]),
            hole_point[1] + fraction * (outer_point[1] - hole_point[1]),
        )
        if not point_in_polygon(sample, outer_boundary, tol):
            return False
        if any(point_in_polygon(sample, obstacle, tol) for obstacle in obstacles):
            return False
    return True


def connect_holes_to_boundary(
    outer_boundary: Polygon,
    obstacles: list[Polygon],
    tol: float,
) -> Polygon:
    """Convert a polygon with holes into a weakly simple ring using visibility bridges."""
    combined = outer_boundary[:]
    outer_candidates = outer_boundary[:]

    for obstacle in obstacles:
        best: tuple[float, Point, Point] | None = None
        for hole_point in obstacle:
            for outer_point in outer_candidates:
                if not bridge_is_visible(
                    hole_point,
                    outer_point,
                    combined,
                    obstacles,
                    outer_boundary,
                    tol,
                ):
                    continue
                candidate = (distance(hole_point, outer_point), hole_point, outer_point)
                if best is None or candidate[0] < best[0]:
                    best = candidate

        if best is None:
            raise ValueError("Could not find a collision-free bridge from an obstacle to the map boundary")

        _, hole_point, outer_point = best
        outer_index = next(i for i, point in enumerate(combined) if same_point(point, outer_point, tol))
        hole_index = next(i for i, point in enumerate(obstacle) if same_point(point, hole_point, tol))
        ordered_hole = obstacle[hole_index:] + obstacle[:hole_index]
        combined = (
            combined[: outer_index + 1]
            + ordered_hole
            + [hole_point, outer_point]
            + combined[outer_index + 1 :]
        )
    return combined


def triangulate_polygon(poly: Polygon, tol: float) -> list[Polygon]:
    """Triangulate a simple CCW polygon with the ear-clipping algorithm."""
    if len(poly) == 3:
        return [poly[:]]

    remaining = poly[:]
    triangles: list[Polygon] = []
    guard = 0
    while len(remaining) > 3:
        ear_found = False
        for i, current in enumerate(remaining):
            previous = remaining[i - 1]
            following = remaining[(i + 1) % len(remaining)]
            if cross(previous, current, following) <= tol:
                continue

            triangle = [previous, current, following]
            excluded_indices = {i - 1 if i > 0 else len(remaining) - 1, i, (i + 1) % len(remaining)}
            contains_vertex = any(
                point_in_triangle(point, previous, current, following, tol)
                for j, point in enumerate(remaining)
                if j not in excluded_indices
                and not any(same_point(point, vertex, tol) for vertex in triangle)
            )
            if contains_vertex:
                continue

            triangles.append(triangle)
            remaining.pop(i)
            ear_found = True
            break

        guard += 1
        if not ear_found or guard > len(poly) * len(poly):
            raise ValueError("Could not decompose the map boundary; check for invalid or repeated vertices")

    triangles.append(remaining)
    return triangles


def convex_hull(points: Iterable[Point], tol: float) -> Polygon:
    """Compute the CCW convex hull with Andrew's monotone-chain algorithm."""
    unique: list[Point] = []
    for point in sorted(points):
        if not unique or distance(point, unique[-1]) > tol:
            unique.append(point)
    if len(unique) < 3:
        return unique

    lower: list[Point] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= tol:
            lower.pop()
        lower.append(point)

    upper: list[Point] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= tol:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def merge_convex_regions(regions: list[Polygon], tol: float) -> list[Polygon]:
    """Greedily merge adjacent pieces whenever their union remains convex."""
    merged = [region[:] for region in regions]
    changed = True
    while changed:
        changed = False
        for i in range(len(merged)):
            for j in range(i + 1, len(merged)):
                if not any(
                    collinear_overlap_length(a, b, c, d, tol) > tol
                    for a, b in edges(merged[i])
                    for c, d in edges(merged[j])
                ):
                    continue
                hull = convex_hull(merged[i] + merged[j], tol)
                combined_area = polygon_area(merged[i]) + polygon_area(merged[j])
                area_tolerance = max(tol, combined_area * 1e-9)
                if len(hull) >= 3 and abs(polygon_area(hull) - combined_area) <= area_tolerance:
                    merged[i] = hull
                    merged.pop(j)
                    changed = True
                    break
            if changed:
                break
    return merged


def approximate_convex_decomposition(
    raw: Iterable[Iterable[float]],
    obstacles_raw: Iterable[Iterable[Iterable[float]]] | None = None,
    tol: float = 1e-9,
) -> list[Polygon]:
    """Decompose a map boundary minus polygon obstacles into convex polygons."""
    boundary = normalize_map_polygon(raw, tol)
    obstacles = [normalize_map_polygon(raw_obstacle, tol) for raw_obstacle in (obstacles_raw or [])]
    for obstacle in obstacles:
        if not all(point_in_polygon(point, boundary, tol) for point in obstacle) or rings_intersect(
            obstacle, boundary, tol
        ):
            raise ValueError("Every obstacle must be fully inside the map boundary")
        obstacle.reverse()  # Holes must be clockwise while the outer boundary is CCW.

    for i, obstacle in enumerate(obstacles):
        for other in obstacles[i + 1 :]:
            if rings_intersect(obstacle, other, tol) or point_in_polygon(obstacle[0], other, tol) or point_in_polygon(other[0], obstacle, tol):
                raise ValueError("Obstacles must not overlap or touch each other")

    if not obstacles and is_convex(boundary, tol):
        return [boundary]
    free_space_ring = connect_holes_to_boundary(boundary, obstacles, tol) if obstacles else boundary
    triangles = triangulate_polygon(free_space_ring, tol)
    return merge_convex_regions(triangles, tol)


def collinear_overlap_length(a: Point, b: Point, c: Point, d: Point, tol: float) -> float:
#Check if the two segments are collinear and return the length of their overlap
    if abs(cross(a, b, c)) > tol or abs(cross(a, b, d)) > tol:
        return 0.0
    axis = 0 if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else 1
    #project onto x if axis = 0, otherwise project onto y
    lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
    hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
    projected = max(0.0, hi - lo)
    base_projection = abs(b[axis] - a[axis])
    if base_projection <= tol:
        return 0.0
    return projected * distance(a, b) / base_projection
    #calculate the overlap length in the original coordinate system


def collinear_overlap_segment(
    a: Point, b: Point, c: Point, d: Point, tol: float
) -> tuple[Point, Point] | None:
    """Return the endpoints of the positive-length shared part of two collinear segments."""
    if abs(cross(a, b, c)) > tol or abs(cross(a, b, d)) > tol:
        return None

    axis = 0 if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else 1
    denominator = b[axis] - a[axis]
    if abs(denominator) <= tol:
        return None

    lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
    hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
    if hi - lo <= tol:
        return None

    def point_at(projected: float) -> Point:
        t = (projected - a[axis]) / denominator
        return a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])

    return point_at(lo), point_at(hi)


def shared_portal(a: Polygon, b: Polygon, tol: float) -> tuple[Point, Point] | None:
    """Return the longest positive-length boundary segment shared by two convex regions."""
    candidates = (
        collinear_overlap_segment(a1, a2, b1, b2, tol)
        for a1, a2 in edges(a)
        for b1, b2 in edges(b)
    )
    return max((segment for segment in candidates if segment is not None), key=lambda segment: distance(*segment), default=None)


def erode_portal(portal: tuple[Point, Point], clearance: float, tol: float) -> tuple[Point, Point] | None:
    """Remove clearance from both ends of a portal so samples stay away from its vertices."""
    start, end = portal
    length = distance(start, end)
    if length - 2.0 * clearance <= tol:
        return None
    unit_x = (end[0] - start[0]) / length
    unit_y = (end[1] - start[1]) / length
    return (
        start[0] + unit_x * clearance,
        start[1] + unit_y * clearance,
    ), (
        end[0] - unit_x * clearance,
        end[1] - unit_y * clearance,
    )


def point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    """Return the Euclidean distance from a point to a closed segment."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        return distance(point, start)
    t = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared))
    closest = start[0] + t * dx, start[1] + t * dy
    return distance(point, closest)


def point_clearance(point: Point, boundary: Polygon, obstacles: list[Polygon]) -> float:
    """Return the distance from a free-space point to the nearest map boundary or obstacle."""
    distances = [point_to_segment_distance(point, start, end) for start, end in edges(boundary)]
    distances.extend(
        point_to_segment_distance(point, start, end)
        for obstacle in obstacles
        for start, end in edges(obstacle)
    )
    return min(distances)


def validate_robot_state(
    point: Point,
    label: str,
    boundary: Polygon,
    obstacles: list[Polygon],
    required_clearance: float,
    tol: float,
) -> None:
    """Reject a start or goal that is outside free space or too close to geometry."""
    if not point_in_polygon(point, boundary, tol) or any(point_in_polygon(point, obstacle, tol) for obstacle in obstacles):
        raise ValueError(f"{label} must lie in free space")
    clearance = point_clearance(point, boundary, obstacles)
    if clearance + tol < required_clearance:
        raise ValueError(
            f"{label} clearance {clearance:.6g} is below required clearance {required_clearance:.6g}"
        )


def line_intersection(s: Point, e: Point, a: Point, b: Point, tol: float) -> Point:
    #this function will be used later in the Sutherland-Hodgman clipping algorithm to find the intersection point of two lines
    sx, sy = e[0] - s[0], e[1] - s[1]
    ax, ay = b[0] - a[0], b[1] - a[1]
    denominator = sx * ay - sy * ax #(SE x AB) 
    if abs(denominator) <= tol:
        return e
    t = ((a[0] - s[0]) * ay - (a[1] - s[1]) * ax) / denominator #(A-S x AB) / (SE x AB)
    #t determines the intersection point on SE
    return s[0] + t * sx, s[1] + t * sy
    #if denominator is zero, the lines are parallel, return e as a fallback
    #if not, calculate the intersection point using the parameter t and return it


def convex_intersection(subject: Polygon, clip: Polygon, tol: float) -> Polygon:
    """Sutherland-Hodgman clipping; both polygons must be CCW and convex."""
    #define if 2 polygons intersect. 
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

#Define relationship between two polygons: a traversable shared edge or none.
def intersection_relation(a: Polygon, b: Polygon, tol: float) -> tuple[str | None, float]:
    clipped = convex_intersection(a, b, tol)
    area = polygon_area(clipped) if len(clipped) >= 3 else 0.0
    if area > tol:
        # Convex regions produced by ACD must not overlap in area.
        # Overlapping inputs are ignored instead of becoming graph neighbors.
        return None, area

    if shared_portal(a, b, tol) is not None:
        return "shared_edge", 0.0
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


def regions_from_map(data: dict, tol: float = 1e-9) -> tuple[dict, dict]:
    """Run ACD for a map input and return data accepted by build_graph."""
    map_data = data["map"]
    obstacles_raw = map_data.get("obstacles", [])
    raw_boundary = map_data.get("boundary") or map_data.get("free_space") or map_data.get("polygon")
    if raw_boundary is None:
        raise ValueError("Map input must contain map.boundary")

    boundary = normalize_map_polygon(raw_boundary, tol)
    obstacles = [normalize_map_polygon(raw_obstacle, tol) for raw_obstacle in obstacles_raw]
    robot_radius = float(map_data.get("robot_radius", 0.0))
    safety_margin = float(map_data.get("safety_margin", 0.0))
    if robot_radius < 0 or safety_margin < 0:
        raise ValueError("robot_radius and safety_margin must be non-negative")
    required_clearance = robot_radius + safety_margin

    start = map_data.get("start")
    goal = map_data.get("goal")
    if (start is None) != (goal is None):
        raise ValueError("Provide both map.start and map.goal, or neither")
    if start is not None:
        start = (float(start[0]), float(start[1]))
        goal = (float(goal[0]), float(goal[1]))
        validate_robot_state(start, "start", boundary, obstacles, required_clearance, tol)
        validate_robot_state(goal, "goal", boundary, obstacles, required_clearance, tol)

    pieces = approximate_convex_decomposition(boundary, obstacles_raw, tol)
    regions = [
        {
            "id": f"C{i}",
            "polygon": [[x, y] for x, y in polygon],
            "centroid": [round(value, 8) for value in centroid(polygon)],
        }
        for i, polygon in enumerate(pieces)
    ]
    return {
        "regions": regions
    }, {
        "boundary": boundary,
        "obstacles": obstacles,
        "planning": {
            "robot_radius": robot_radius,
            "safety_margin": safety_margin,
            "required_clearance": required_clearance,
            "start": list(start) if start is not None else None,
            "goal": list(goal) if goal is not None else None,
        },
    }


def build_pipeline(data: dict, tol: float = 1e-9) -> tuple[dict, dict, dict | None]:
    """Accept either a map or precomputed regions, then build the graph."""
    if "map" in data:
        regions_data, map_geometry = regions_from_map(data, tol)
        graph = build_graph(
            regions_data,
            tol,
            required_clearance=map_geometry["planning"]["required_clearance"],
        )
        graph["pipeline"] = "map -> ACD -> convex regions -> graph"
        graph["planning"] = map_geometry["planning"]
        return graph, regions_data, map_geometry
    if "regions" in data:
        graph = build_graph(data, tol)
        graph["pipeline"] = "convex regions -> graph"
        return graph, data, None
    raise ValueError("Input must contain either 'map' or 'regions'")


def build_graph(data: dict, tol: float = 1e-9, required_clearance: float = 0.0) -> dict:
    """Build a directed graph using only shared boundary portals wide enough for the robot."""
    if required_clearance < 0:
        raise ValueError("required_clearance must be non-negative")
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
    for i, left in enumerate(regions):
        for right in regions[i + 1 :]:
            relation, _intersection_area = intersection_relation(left["polygon"], right["polygon"], tol)
            if relation != "shared_edge":
                continue
            portal = shared_portal(left["polygon"], right["polygon"], tol)
            if portal is None:
                continue
            safe_portal = erode_portal(portal, required_clearance, tol)
            if safe_portal is None:
                continue

            forward = {
                "source": left["id"],
                "target": right["id"],
                "relation": "safe_portal",
                "portal": [[round(x, 8), round(y, 8)] for x, y in portal],
                "portal_width": round(distance(*portal), 8),
                "safe_portal": [[round(x, 8), round(y, 8)] for x, y in safe_portal],
                "safe_portal_width": round(distance(*safe_portal), 8),
                "required_clearance": round(required_clearance, 8),
            }
            directed.append(forward)
            directed.append({**forward, "source": right["id"], "target": left["id"]})

    vertices = [
        {
            "id": r["id"],
            "centroid": [round(r["centroid"][0], 8), round(r["centroid"][1], 8)],
            "area": round(polygon_area(r["polygon"]), 8),
            "polygon": [[x, y] for x, y in r["polygon"]],
        }
        for r in regions
    ]
    return {
        "directed": True,
        "vertices": vertices,
        "directed_edges": directed,
        "connected_components": connected_components([r["id"] for r in regions], directed),
    }


COLORS = ["#ef767a", "#56c271", "#5b9cf0", "#ac72d6", "#f4a259", "#49bec7", "#ed6b9f", "#9bcf53"]


def svg_visualization(
    graph: dict,
    width: int = 1200,
    height: int = 650,
    map_geometry: dict | None = None,
) -> str:
    vertices = graph["vertices"]
    points = [p for v in vertices for p in v["polygon"]]
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span_x, span_y = max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)

    panel_count = 3 if map_geometry is not None else 2
    panel_w, margin = width / panel_count, 55
    region_panel = 1 if map_geometry is not None else 0
    graph_panel = 2 if map_geometry is not None else 1

    def transform(p: Point, panel: int) -> Point:
        scale = min((panel_w - 2 * margin) / span_x, (height - 2 * margin) / span_y)
        used_w, used_h = span_x * scale, span_y * scale
        offset_x = panel * panel_w + (panel_w - used_w) / 2
        offset_y = (height - used_h) / 2
        return offset_x + (p[0] - min_x) * scale, height - offset_y - (p[1] - min_y) * scale

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/></marker></defs>',
    ]

    for panel in range(1, panel_count):
        lines.append(f'<line x1="{panel * panel_w}" y1="28" x2="{panel * panel_w}" y2="{height-28}" stroke="#cbd5e1"/>')
    titles = ["Input map", "ACD convex regions", "Graph"] if map_geometry is not None else ["Convex regions", "Graph of Convex Regions"]
    for panel, panel_title in enumerate(titles):
        lines.append(f'<text x="{panel * panel_w + panel_w/2}" y="30" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700">{panel_title}</text>')

    if map_geometry is not None:
        boundary_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (transform(tuple(p), 0) for p in map_geometry["boundary"]))
        lines.append(f'<polygon points="{boundary_points}" fill="#dbeafe" stroke="#0f172a" stroke-width="3"/>')
        for obstacle in map_geometry["obstacles"]:
            obstacle_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (transform(tuple(p), 0) for p in obstacle))
            lines.append(f'<polygon points="{obstacle_points}" fill="#334155" stroke="#0f172a" stroke-width="3"/>')
        planning = map_geometry["planning"]
        for label, color in (("start", "#16a34a"), ("goal", "#dc2626")):
            point = planning[label]
            if point is None:
                continue
            x, y = transform(tuple(point), 0)
            lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="9" fill="{color}" stroke="white" stroke-width="3"/>')
            lines.append(f'<text x="{x+13:.2f}" y="{y+5:.2f}" fill="{color}" font-family="Arial" font-size="15" font-weight="700">{label}</text>')

    for idx, vertex in enumerate(vertices):
        polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (transform(tuple(p), region_panel) for p in vertex["polygon"]))
        color = COLORS[idx % len(COLORS)]
        lines.append(f'<polygon points="{polygon_points}" fill="{color}" fill-opacity="0.48" stroke="#334155" stroke-width="2"/>')
        cx, cy = transform(tuple(vertex["centroid"]), region_panel)
        lines.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="18" fill="#0f172a"/>')
        lines.append(f'<text x="{cx:.2f}" y="{cy+5:.2f}" text-anchor="middle" fill="white" font-family="Arial" font-size="13">{vertex["id"]}</text>')

    positions = {v["id"]: transform(tuple(v["centroid"]), graph_panel) for v in vertices}
    # Every geometric connection is stored as two consecutive directed edges.
    connections = graph["directed_edges"][::2]
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
    lines.append(f'<text x="{width/2}" y="{height-14}" text-anchor="middle" font-family="Arial" font-size="13" fill="#475569">{len(vertices)} regions · {len(connections)} bidirectional connections · {summary}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing a 'map' or 'regions' object")
    parser.add_argument("--output", type=Path, default=Path("graph.json"), help="Output graph JSON")
    parser.add_argument("--svg", type=Path, default=Path("graph.svg"), help="Output visualization SVG")
    parser.add_argument(
        "--regions-output",
        type=Path,
        default=Path("convex_regions.json"),
        help="ACD convex-region output; written only for map input",
    )
    parser.add_argument("--tolerance", type=float, default=1e-9, help="Geometry tolerance")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    graph, regions_data, map_geometry = build_pipeline(data, args.tolerance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.svg.write_text(
        svg_visualization(graph, width=1500 if map_geometry is not None else 1200, map_geometry=map_geometry),
        encoding="utf-8",
    )
    if map_geometry is not None:
        args.regions_output.parent.mkdir(parents=True, exist_ok=True)
        args.regions_output.write_text(
            json.dumps(regions_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"ACD created {len(regions_data['regions'])} convex regions")
    print(f"Built {len(graph['vertices'])} vertices and {len(graph['directed_edges'])} directed edges")
    print(f"Connected components: {graph['connected_components']}")
    if map_geometry is not None:
        print(f"Regions: {args.regions_output}")
    print(f"JSON: {args.output}")
    print(f"SVG:  {args.svg}")


if __name__ == "__main__":
    main()
