"""Concavity-driven polygon cuts without a triangulation stage.

Uses the ACD strategy of resolving the deepest convex-hull pocket first.
The stopping tolerance is numerical only: graph regions remain strictly convex.
Hole opening and notch cuts use GEOS polygon splitting, not a triangle mesh.
This is a Python implementation of that strategy, not the ACD2D executable.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import split, unary_union


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])


def _notches(poly, epsilon):
    ring = list(orient(poly, sign=1).exterior.coords)[:-1]
    hull_boundary = poly.convex_hull.boundary
    return [(Point(p).distance(hull_boundary), i, p)
            for i, p in enumerate(ring)
            if _cross(ring[i-1], p, ring[(i+1) % len(ring)]) < -epsilon]


def _parts(poly, line, area_epsilon):
    result = list(split(poly, line).geoms)
    if len(result) < 2 or any(not p.is_valid or p.area <= area_epsilon for p in result):
        return None
    return result


def _open_hole(poly, epsilon, area_epsilon):
    hole = max(poly.interiors, key=lambda r: Polygon(r).area)
    center = Polygon(hole).representative_point()
    cx, cy = center.x, center.y
    shell = list(poly.exterior.coords)[:-1]
    vertices = list(hole.coords)[:-1]
    directions = [(1., 0.), (0., 1.)]
    directions += [(x-cx, y-cy) for x, y in vertices]
    directions += [(b[0]-a[0], b[1]-a[1]) for a, b in zip(vertices, vertices[1:]+vertices[:1])]
    directions += [(x-cx, y-cy) for x, y in sorted(shell, key=lambda p: Point(p).distance(center))[:12]]
    extent = math.hypot(poly.bounds[2]-poly.bounds[0], poly.bounds[3]-poly.bounds[1])*2
    best = None
    for dx, dy in directions:
        length = math.hypot(dx, dy)
        if length <= epsilon:
            continue
        dx, dy = dx/length, dy/length
        line = LineString([(cx-extent*dx, cy-extent*dy), (cx+extent*dx, cy+extent*dy)])
        intersections = poly.exterior.intersection(line)
        points = []
        for geom in getattr(intersections, 'geoms', [intersections]):
            if geom.geom_type == 'Point':
                points.append((geom.x-cx)*dx + (geom.y-cy)*dy)
        negative = [v for v in points if v < -epsilon]
        positive = [v for v in points if v > epsilon]
        if not negative or not positive:
            continue
        low, high = max(negative), min(positive)
        # Extend slightly through the shell to avoid endpoint-rounding failures.
        line = LineString([(cx+(low-epsilon*10)*dx, cy+(low-epsilon*10)*dy),
                           (cx+(high+epsilon*10)*dx, cy+(high+epsilon*10)*dy)])
        parts = _parts(poly, line, area_epsilon)
        if not parts or sum(len(p.interiors) for p in parts) >= len(poly.interiors):
            continue
        score = (len(parts), sum(len(_notches(p, epsilon)) for p in parts), high-low)
        if best is None or score < best[0]:
            best = score, parts
    if best is None:
        raise ValueError('ACD could not open an obstacle hole with a valid polygon cut.')
    return best[1]


def _resolve_notch(poly, epsilon, area_epsilon):
    poly = orient(poly, sign=1)
    ring = list(poly.exterior.coords)[:-1]
    notches = _notches(poly, epsilon)
    _, index, source = max(notches, key=lambda item: (item[0], -item[1]))
    targets = list(ring)
    # Edge projections permit cuts ending between original vertices.
    for a, b in zip(ring, ring[1:]+ring[:1]):
        edge = LineString([a, b])
        target = edge.interpolate(edge.project(Point(source)))
        targets.append((target.x, target.y))
    extent = math.hypot(poly.bounds[2]-poly.bounds[0], poly.bounds[3]-poly.bounds[1])*2
    previous, following = ring[index-1], ring[(index+1) % len(ring)]
    left = (previous[0]-source[0], previous[1]-source[1])
    right = (following[0]-source[0], following[1]-source[1])
    ln, rn = math.hypot(*left), math.hypot(*right)
    dx, dy = -left[0]/ln-right[0]/rn, -left[1]/ln-right[1]/rn
    targets.append((source[0]+extent*dx, source[1]+extent*dy))
    before = len(notches)
    best = None
    for target in targets:
        line = LineString([source, target])
        if line.length <= epsilon:
            continue
        # Clip each candidate ray to its first boundary hit. Aiming at a vertex
        # need not imply using that vertex when an intervening edge blocks it.
        dx, dy = (target[0]-source[0])/line.length, (target[1]-source[1])/line.length
        ray = LineString([source, (source[0]+extent*dx, source[1]+extent*dy)])
        intersection = poly.boundary.intersection(ray)
        hits = []
        for geom in getattr(intersection, 'geoms', [intersection]):
            if geom.geom_type == 'Point':
                d = (geom.x-source[0])*dx+(geom.y-source[1])*dy
                if d > epsilon:
                    hits.append(d)
        if not hits:
            continue
        reach = min(hits)
        midpoint = Point(source[0]+reach*dx/2, source[1]+reach*dy/2)
        if not poly.contains(midpoint):
            continue
        line = LineString([source, (source[0]+(reach+epsilon*10)*dx,
                                    source[1]+(reach+epsilon*10)*dy)])
        parts = _parts(poly, line, area_epsilon)
        if not parts or len(parts) != 2:
            continue
        after = sum(len(_notches(p, epsilon)) for p in parts)
        # A cut must resolve the selected notch on BOTH sides, not peel ears.
        if any(any(Point(p).distance(Point(source)) <= epsilon for _, _, p in _notches(part, epsilon))
               for part in parts):
            continue
        if after >= before:
            continue
        score = (after, line.length)
        if best is None or score < best[0]:
            best = score, parts
    if best is None:
        raise ValueError(f'ACD could not resolve the concave vertex at {source}.')
    return best[1]


def decompose_free_space(free, tolerance=1e-9):
    """Partition one valid connected polygon into convex, nonoverlapping pieces."""
    if not isinstance(free, Polygon) or not free.is_valid or free.is_empty:
        raise ValueError('ACD requires a valid connected polygon with positive area.')
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('ACD tolerance must be finite and positive.')
    epsilon = tolerance
    area_epsilon = min(tolerance, free.area*1e-12)
    pending = [free]
    done = []
    while pending:
        poly = pending.pop()
        if poly.interiors:
            pending.extend(_open_hole(poly, epsilon, area_epsilon))
        elif _notches(poly, epsilon):
            pending.extend(_resolve_notch(poly, epsilon, area_epsilon))
        else:
            done.append(poly)
        if len(pending)+len(done) > 1000:
            raise ValueError('ACD exceeded 1000 regions; simplify the input geometry.')
    coverage = unary_union(done)
    limit = max(tolerance, free.area*1e-9)
    if (coverage.symmetric_difference(free).area > limit
            or sum(p.area for p in done)-coverage.area > limit):
        raise ValueError('ACD coverage validation failed: gaps or overlapping regions.')
    done.sort(key=lambda p: (p.centroid.x, p.centroid.y, tuple(p.exterior.coords)))
    return [list(orient(p, sign=1).exterior.coords)[:-1] for p in done]
