"""Import a recorded ACD2D partition without recomputing its cuts.

The supplied exports round coordinates to four decimals. Restore their shared
straight edges against the exact map boundary before building safe portals.
Region IDs, region count, and the reference mesh topology are preserved.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent


def geometry_sha256(map_data):
    geometry = {"boundary": map_data["boundary"], "obstacles": map_data.get("obstacles", [])}
    raw = json.dumps(geometry, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _restore_shared_boundaries(regions, free, decimals):
    bounds = unary_union([Polygon(r["polygon"]) for r in regions]).bounds
    sx0, sy0, sx1, sy1 = bounds
    x0, y0, x1, y1 = free.bounds
    scale_x, scale_y = (x1-x0)/(sx1-sx0), (y1-y0)/(sy1-sy0)
    precision_limit = max(scale_x, scale_y) * 2.5 * 10**(-decimals)
    nodes, lookup, rings = [], {}, []
    for region in regions:
        ring = []
        for x, y in region["polygon"]:
            key = (x, y)
            if key not in lookup:
                lookup[key] = len(nodes)
                nodes.append([x0+(x-sx0)*scale_x, y0+(y-sy0)*scale_y])
            ring.append(lookup[key])
        rings.append(ring)
    nodes = np.array(nodes, dtype=float)
    initial = nodes.copy()
    boundary_rings = [list(free.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in free.interiors]
    corners = [p for ring in boundary_rings for p in ring]
    boundary_edges = [(a, b) for ring in boundary_rings for a, b in zip(ring, ring[1:]+ring[:1])]
    constraints = []
    for index, point in enumerate(nodes):
        distance, corner = min((np.linalg.norm(point-np.array(q)), q) for q in corners)
        if distance < precision_limit:
            nodes[index] = corner
            constraints.append(("fixed", index, np.array(corner)))
            continue
        candidates = []
        for a, b in boundary_edges:
            vector = np.array(b)-a
            parameter = (point-a) @ vector / (vector @ vector)
            if -1e-9 <= parameter <= 1+1e-9:
                normal = np.array([-vector[1], vector[0]]) / np.linalg.norm(vector)
                distance = abs((point-a) @ normal)
                if distance < precision_limit:
                    candidates.append((distance, normal, np.array(a)))
        if candidates:
            _, normal, anchor = min(candidates, key=lambda item: item[0])
            constraints.append(("line", index, normal, anchor))

    # Restore straight chains and T-junctions that were bent by decimal rounding.
    triples = set()
    for ring in rings:
        for j, b in enumerate(ring):
            a, c = ring[j-1], ring[(j+1) % len(ring)]
            v, w = initial[b]-initial[a], initial[c]-initial[b]
            length = np.linalg.norm(initial[c]-initial[a])
            determinant = v[0]*w[1]-v[1]*w[0]
            if length > precision_limit and v @ w > 0 and abs(determinant)/length < precision_limit:
                triples.add((a, c, b, length))
    edges = sorted({tuple(sorted((a, b))) for ring in rings for a, b in zip(ring, ring[1:]+ring[:1])})
    for a, b in edges:
        vector = nodes[b]-nodes[a]
        length = np.linalg.norm(vector)
        if length <= 1e-12:
            raise ValueError("The ACD2D reference contains a collapsed edge.")
        for k, point in enumerate(nodes):
            if k in (a, b):
                continue
            offset = point-nodes[a]
            parameter = offset @ vector / (vector @ vector)
            distance = abs(vector[0]*offset[1]-vector[1]*offset[0]) / length
            if 1e-5 < parameter < 1-1e-5 and distance < precision_limit:
                triples.add((a, b, k, length))

    residual = math.inf
    for _ in range(12):
        rows, values = [], []
        for kind, index, *args in constraints:
            if kind == "fixed":
                for dimension in (0, 1):
                    row = np.zeros(nodes.size)
                    row[index*2+dimension] = 1
                    rows.append(row)
                    values.append(nodes[index, dimension]-args[0][dimension])
            else:
                normal, anchor = args
                row = np.zeros(nodes.size)
                row[index*2:index*2+2] = normal
                rows.append(row)
                values.append((nodes[index]-anchor) @ normal)
        for a, b, k, length in sorted(triples):
            v, w = nodes[b]-nodes[a], nodes[k]-nodes[a]
            row = np.zeros(nodes.size)
            row[a*2:a*2+2] = [-w[1]+v[1], w[0]-v[0]]
            row[b*2:b*2+2] = [w[1], -w[0]]
            row[k*2:k*2+2] = [-v[1], v[0]]
            rows.append(row/length)
            values.append((v[0]*w[1]-v[1]*w[0])/length)
        residual = max(map(abs, values), default=0.)
        if residual < 1e-12:
            break
        correction = np.linalg.lstsq(np.array(rows), -np.array(values), rcond=1e-12)[0]
        nodes += correction.reshape(-1, 2)
    displacement = float(np.max(np.linalg.norm(nodes-initial, axis=1)))
    if residual > 1e-10 or displacement > precision_limit:
        raise ValueError("The ACD2D reference cannot be restored within its recorded export precision.")
    polygons = [Polygon(nodes[ring]) for ring in rings]
    if any(not p.is_valid or p.area <= 0 for p in polygons):
        raise ValueError("The restored ACD2D reference contains an invalid region.")
    union = unary_union(polygons)
    coverage_error = union.symmetric_difference(free).area
    overlap = max(0., sum(p.area for p in polygons)-union.area)
    limit = max(1e-8, free.area*1e-10)
    if coverage_error > limit or overlap > limit:
        raise ValueError("The restored ACD2D reference leaves gaps or overlapping regions.")
    from build_graph import normalize_polygon
    restored = [{"id": r["id"], "polygon": normalize_polygon(list(p.exterior.coords)[:-1], 1e-9)}
                for r, p in zip(regions, polygons)]
    return restored, {
        "coordinate_transform": {"type": "bounding_box_affine", "source_bounds": list(bounds),
                                 "target_bounds": list(free.bounds), "scale_x": scale_x, "scale_y": scale_y},
        "rounding_repair": {"coordinate_decimal_places": decimals,
                            "maximum_vertex_displacement": displacement,
                            "allowed_vertex_displacement": precision_limit,
                            "coverage_error_area": coverage_error, "overlap_area": overlap},
    }


def import_partition(document):
    config = document["acd2d_reference"]
    path = (ROOT / config["path"]).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("The ACD2D reference path must be inside convex-region-graph.")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != config["sha256"]:
        raise ValueError("The ACD2D reference checksum does not match the map configuration.")
    reference = json.loads(raw)
    if reference.get("schema") != "acd2d-reference/v1":
        raise ValueError("Unsupported ACD2D reference schema.")
    m = document["map"]
    if geometry_sha256(m) != reference["geometry_sha256"]:
        raise ValueError("Map geometry changed. Supply a matching ACD2D reference or remove acd2d_reference to recompute with the Python backend.")
    regions = reference["regions"]
    if not regions or len({r["id"] for r in regions}) != len(regions):
        raise ValueError("The ACD2D reference must contain distinct region IDs.")
    for region in regions:
        if not all(math.isfinite(float(v)) for p in region["polygon"] for v in p):
            raise ValueError("ACD2D reference coordinates must be finite.")
    free = Polygon(m["boundary"]).difference(unary_union([Polygon(p) for p in m.get("obstacles", [])]))
    if not isinstance(free, Polygon) or free.is_empty or not free.is_valid:
        raise ValueError("An ACD2D reference requires valid connected map geometry.")
    restored, repair = _restore_shared_boundaries(regions, free, reference["coordinate_decimal_places"])
    return {"regions": restored, "decomposition": {
        "backend": "acd2d_reference_import", "execution": "recorded_partition_import",
        "source_filename": reference["source_filename"], "source_sha256": reference["source_sha256"],
        "reference_path": config["path"], "reference_sha256": config["sha256"],
        "source_parameters": reference["source_parameters"], "region_count": len(restored),
        "region_ids_preserved": True, "convexity": "strict", "triangulation": False,
        **repair,
    }}
