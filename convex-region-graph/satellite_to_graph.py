"""Satellite image and reviewed polygons -> static images and planning case files."""
from __future__ import annotations

import base64
from collections import deque
import hashlib
from html import escape
import io
import json
import math
from pathlib import Path
import shutil
import tempfile
import zipfile

import numpy as np
from PIL import Image, ImageOps
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.validation import explain_validity

from build_graph import (build_graph, is_convex, merge_convex_regions,
                         normalize_map_polygon, normalize_polygon, svg_visualization)
from region_descriptors import enrich_graph

SCHEMA = "satellite-annotations/v1"
MAX_VERTICES = 400
MAX_IMAGE_PIXELS = 24_000_000


def read_image(path):
    """Hash original bytes; apply EXIF once for overlay and computation."""
    path = Path(path)
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as source:
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("Ảnh vượt 24 triệu pixel. Hãy giảm kích thước trước khi chú thích.")
        image = ImageOps.exif_transpose(source).convert("RGB")
    identity = dict(name=path.name, width=image.width, height=image.height,
                    sha256=hashlib.sha256(raw).hexdigest())
    return image, identity


def annotation_template(identity):
    w, h = identity["width"], identity["height"]
    return {
        "schema": SCHEMA, "image": identity, "coordinate_units": "m",
        "calibration": {"points_px": [], "distance_m": None, "source": "",
                        "basis": "map_measurement", "relative_uncertainty": None},
        "geometry_px": {"boundary": [[0, 0], [w, 0], [w, h], [0, h]],
                        "walkable": [], "obstacles": []},
        "planning_px": {"start": None, "goal": None},
        "robot": {"radius_m": 0.25, "safety_margin_m": 0.10, "radius_px": 0, "safety_margin_px": 0},
        "review": {"geometry_confirmed": False},
    }


def finite_number(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: cần một số hữu hạn.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label}: phải >= {minimum}.")
    return float(value)


def pixel_point(raw, identity, label):
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError(f"{label}: cần [x, y].")
    x, y = [finite_number(v, label) for v in raw]
    if not (0 <= x <= identity["width"] and 0 <= y <= identity["height"]):
        raise ValueError(f"{label}: tọa độ nằm ngoài ảnh gốc.")
    return x, y


def pixel_polygon(raw, identity, label):
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError(f"{label}: cần ít nhất 3 đỉnh.")
    poly = Polygon([pixel_point(p, identity, label) for p in raw])
    if not poly.is_valid or poly.area <= 1e-8:
        raise ValueError(f"{label}: polygon không hợp lệ ({explain_validity(poly)}).")
    return poly


def check_identity(annotation, identity):
    if annotation.get("schema") != SCHEMA:
        raise ValueError(f"Cần schema {SCHEMA}.")
    for field in ("width", "height", "sha256"):
        if annotation.get("image", {}).get(field) != identity[field]:
            raise ValueError("Chú thích không khớp ảnh (hash/kích thước). Không dùng tọa độ của ảnh khác.")


def calibration_scale(annotation, identity, allow_estimated=False):
    cal = annotation.get("calibration", {})
    points = cal.get("points_px", [])
    if len(points) != 2:
        raise ValueError("Hiệu chuẩn: hãy chọn 2 điểm trên ảnh và nhập khoảng cách thực tế.")
    a, b = [pixel_point(p, identity, "Hiệu chuẩn") for p in points]
    length = math.dist(a, b)
    if length < 10:
        raise ValueError("Hai điểm hiệu chuẩn phải cách nhau ít nhất 10 pixel để hạn chế sai số chọn điểm.")
    metres = finite_number(cal.get("distance_m"), "Khoảng cách hiệu chuẩn", 1e-9)
    if not isinstance(cal.get("source"), str) or not cal["source"].strip():
        raise ValueError("Hiệu chuẩn cần nguồn số đo (URL hoặc mô tả phép đo).")
    basis = cal.get("basis")
    if basis not in ("measured", "map_measurement", "assumed"):
        raise ValueError("calibration.basis phải là measured, map_measurement hoặc assumed.")
    if basis != "measured" and not allow_estimated:
        raise ValueError("Tỷ lệ ước lượng/giả định: cần bật cho phép tỷ lệ ước lượng hoặc --allow-estimated-scale.")
    uncertainty = cal.get("relative_uncertainty")
    if uncertainty is not None:
        uncertainty = finite_number(uncertainty, "Sai số tương đối", 0)
        if uncertainty >= 1:
            raise ValueError("Sai số tương đối phải nhỏ hơn 1 (ví dụ 0.02 = 2%).")
    return metres / length, {
        **cal, "pixel_distance": length, "metres_per_pixel": metres / length,
        "status": "user_declared_measurement" if basis == "measured" else "estimated",
        "relative_uncertainty": uncertainty,
    }


def mask_to_polygons(mask, width, height, simplify_px=2.0):
    """Vectorize occupied pixel cells via row runs; preserve holes/components.

    The raster may be downsampled; restore its coordinates to the ORIGINAL image.
    Simplification is explicit and its area change is reported, never silent.
    """
    simplify_px = finite_number(simplify_px, "simplify_px", 0)
    sy, sx = height / mask.shape[0], width / mask.shape[1]
    runs = []
    for y, row in enumerate(mask):
        ends = np.flatnonzero(np.diff(np.r_[False, row, False].astype(np.int8)))
        runs.extend(box(a * sx, y * sy, b * sx, (y + 1) * sy)
                    for a, b in zip(ends[::2], ends[1::2]))
        if len(runs) > 50000:
            raise ValueError("Mask quá nhiễu; cần làm sạch trước khi vector hóa.")
    if not runs:
        raise ValueError("Không tìm được vùng trắng/được chọn trong mask.")
    raster_geometry = unary_union(runs)
    result = raster_geometry.simplify(simplify_px, preserve_topology=True)
    parts = [result] if isinstance(result, Polygon) else list(result.geoms)
    walkable, obstacles = [], []
    for poly in sorted(parts, key=lambda p: (-p.area, p.bounds)):
        walkable.append([list(p) for p in list(poly.exterior.coords)[:-1]])
        obstacles.extend([[list(p) for p in list(r.coords)[:-1]] for r in poly.interiors])
    reconstructed = unary_union([Polygon(p) for p in walkable]).difference(unary_union([Polygon(p) for p in obstacles]))
    if reconstructed.symmetric_difference(result).area > 1e-8:
        raise ValueError("Mask có đảo đi được nằm trong lỗ vật cản. Hãy chọn một thành phần liên thông; không tự xóa đảo.")
    vertices = sum(map(len, walkable + obstacles))
    if vertices > MAX_VERTICES:
        raise ValueError(f"Mask có {vertices} đỉnh, vượt {MAX_VERTICES}. Tăng simplify_px hoặc vẽ vùng lớn rõ ràng hơn.")
    return {"walkable": walkable, "obstacles": obstacles,
            "audit": {"components": len(parts), "vertices": vertices,
                      "mask_area_px2": raster_geometry.area,
                      "simplification_error_px2": result.symmetric_difference(raster_geometry).area,
                      "simplify_px": simplify_px, "review_required": True}}


def suggest_region(image, seed_px, tolerance=25.0, simplify_px=3.0):
    """Colour-connected proposal, NOT a learned road detector or metric inference."""
    seed = pixel_point(seed_px, dict(width=image.width, height=image.height), "Seed")
    tolerance = finite_number(tolerance, "Ngưỡng màu", 1)
    if tolerance > 160:
        raise ValueError("Ngưỡng màu tối đa là 160.")
    small = image.copy()
    small.thumbnail((512, 512))
    rgb = np.asarray(small, dtype=np.float32)
    x = min(small.width - 1, int(seed[0] * small.width / image.width))
    y = min(small.height - 1, int(seed[1] * small.height / image.height))
    colours = rgb[max(0, y - 1):y + 2, max(0, x - 1):x + 2].reshape(-1, 3)
    reference = np.median(colours, axis=0)
    candidates = np.linalg.norm(rgb - reference, axis=2) <= tolerance
    if not candidates[y, x]:
        raise ValueError("Seed nằm ở biên màu/chữ. Chọn lại giữa vùng đường rõ hơn.")
    mask = np.zeros(candidates.shape, dtype=bool)
    queue = deque([(x, y)])
    mask[y, x] = True
    while queue:
        x, y = queue.popleft()
        for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= xx < small.width and 0 <= yy < small.height and candidates[yy, xx] and not mask[yy, xx]:
                mask[yy, xx] = True
                queue.append((xx, yy))
    result = mask_to_polygons(mask, image.width, image.height, simplify_px)
    result["audit"].update(method="seeded_rgb_flood_fill", tolerance=tolerance,
                           processing_size=list(small.size), seed_px=list(seed))
    return result


def build_documents(annotation, identity, allow_estimated=False, simulation_long_side=None):
    check_identity(annotation, identity)
    if annotation.get("review", {}).get("geometry_confirmed") is not True:
        raise ValueError("Cần kiểm tra và xác nhận vùng đi được/vật cản trước khi xuất graph.")
    units = annotation.get("coordinate_units", "m")
    if units not in ("m", "px"):
        raise ValueError("coordinate_units phải là m hoặc px.")
    origin_x, origin_y = 0, identity["height"]
    if simulation_long_side is not None:
        long_side = finite_number(simulation_long_side, "Cạnh dài mô phỏng", 1e-6)
        outer_px = pixel_polygon(annotation.get("geometry_px", {}).get("boundary"), identity, "Ranh giới")
        x0, y0, x1, y1 = outer_px.bounds
        scale = long_side / max(x1 - x0, y1 - y0)
        origin_x, origin_y = x0, y1
        units = "m"
        calibration = {"status": "simulation_normalized", "long_side_m": long_side,
                       "simulation_metres_per_pixel": scale, "metres_per_pixel": None,
                       "unit_assumption": "simulation metres; physical dimensions unknown"}
    elif units == "px":
        scale, calibration = 1.0, {"status": "uncalibrated_pixel_coordinates", "metres_per_pixel": None}
    else:
        scale, calibration = calibration_scale(annotation, identity, allow_estimated)
    geom = annotation.get("geometry_px", {})
    rings = [geom.get("boundary", [])] + geom.get("walkable", []) + geom.get("obstacles", [])
    if sum(map(len, rings)) > MAX_VERTICES:
        raise ValueError(f"Tối đa {MAX_VERTICES} đỉnh đầu vào. Hãy đơn giản hóa polygon.")
    outer = pixel_polygon(geom.get("boundary"), identity, "Ranh giới")
    walkable = [pixel_polygon(r, identity, f"Vùng đi được {i}")
                for i, r in enumerate(geom.get("walkable", []))]
    obstacles = [pixel_polygon(r, identity, f"Vật cản {i}")
                 for i, r in enumerate(geom.get("obstacles", []))]
    for poly in walkable + obstacles:
        if not outer.covers(poly):
            raise ValueError("Mọi vùng đi được và vật cản phải nằm trong ranh giới đã chọn.")
    free_px = (unary_union(walkable) if walkable else outer).difference(unary_union(obstacles))
    if free_px.is_empty or not free_px.is_valid or not isinstance(free_px, Polygon):
        raise ValueError("Vùng đi được phải là một Polygon liên thông có diện tích. Kiểm tra các đoạn đường bị đứt; không tự bỏ vùng rời.")
    transform = lambda p: ((p[0] - origin_x) * scale, (origin_y - p[1]) * scale)
    boundary = normalize_map_polygon([transform(p) for p in list(free_px.exterior.coords)[:-1]], 1e-9)
    holes = [normalize_map_polygon([transform(p) for p in list(r.coords)[:-1]], 1e-9) for r in free_px.interiors]
    free = Polygon(boundary, holes)
    robot = annotation.get("robot", {})
    radius = finite_number(robot.get("radius_" + units, 0), "Bán kính robot", 0)
    margin = finite_number(robot.get("safety_margin_" + units, 0), "Biên an toàn", 0)
    required = radius + margin
    planning = dict(robot_radius=radius, safety_margin=margin, required_clearance=required)
    for key in ("start", "goal"):
        point = transform(pixel_point(annotation.get("planning_px", {}).get(key), identity, key))
        if not free.contains(Point(point)):
            raise ValueError(f"{key}: phải nằm bên trong vùng đi được, không nằm trên biên hoặc vật cản.")
        clearance = free.boundary.distance(Point(point))
        if clearance + 1e-9 < required:
            raise ValueError(f"{key}: clearance {clearance:.4f} {units} < bán kính + biên an toàn {required:.4f} {units}.")
        planning[key] = list(point)
    triangles = constrained_delaunay_triangles(free)
    pieces = [normalize_polygon(list(t.exterior.coords)[:-1], 1e-9) for t in triangles.geoms]
    if len(pieces) > 600:
        raise ValueError("Quá 600 tam giác. Hãy đơn giản hóa đường biên trước khi tạo graph.")
    # Exact convex merging can be costly for dense raster contours. Retaining
    # triangles is still a valid convex decomposition and preserves every portal.
    merged = len(pieces) <= 120
    if merged:
        pieces = merge_convex_regions(pieces, 1e-9)
    pieces.sort(key=lambda p: (Polygon(p).centroid.x, Polygon(p).centroid.y, p))
    if not pieces or not all(is_convex(p, 1e-9) for p in pieces):
        raise ValueError("Phân rã không tạo được các vùng lồi hợp lệ.")
    regions = {"regions": [{"id": f"C{i}", "polygon": p} for i, p in enumerate(pieces)]}
    graph = build_graph(regions, required_clearance=required)
    graph["pipeline"] = "satellite_reviewed_polygons_constrained_delaunay"
    graph["planning"] = planning
    geometry = dict(boundary=boundary, obstacles=holes, planning=planning)
    enrich_graph(graph, geometry)
    graph["descriptor_metadata"].update(length_unit=units, area_unit=units + "^2")
    graph["descriptor_metadata"]["traversability"] = graph["descriptor_metadata"]["traversability"].replace("m^2", units + "^2")
    for key in ("start", "goal"):
        matching = [v["id"] for v in graph["vertices"] if Polygon(v["polygon"]).covers(Point(planning[key]))]
        if not matching:
            raise ValueError(f"Không tìm được vùng chứa {key}.")
        planning[key + "_region"] = matching[0]
        planning[key + "_regions"] = matching  # Endpoint may be on an internal portal.
    polygons = [Polygon(v["polygon"]) for v in graph["vertices"]]
    coverage = unary_union(polygons)
    mismatch = coverage.symmetric_difference(free).area
    overlap = max(0.0, sum(p.area for p in polygons) - coverage.area)
    area_tolerance = max(1e-8, free.area * 1e-8)
    if mismatch > area_tolerance or overlap > area_tolerance:
        raise ValueError("Kiểm tra diện tích thất bại: các vùng lồi bị thiếu, trùng hoặc nằm ngoài vùng đi được.")
    common = next((c for c in graph["connected_components"]
                   if set(planning["start_regions"]) & set(c) and set(planning["goal_regions"]) & set(c)), None)
    reachable = common is not None
    if reachable:
        for key in ("start", "goal"):
            planning[key + "_region"] = next(r for r in planning[key + "_regions"] if r in common)
    warnings = [
        "Geometry is reviewed image tracing, not a surveyed map or verified traversability.",
        "Uniform scale assumes a top-down image with no perspective or nonuniform resize.",
        "Mean clearance uses the repository's numerical quadrature; it is not an exact integral.",
        "Safe portals use the repository's endpoint trimming rule; collision checking remains necessary.",
    ]
    if calibration["status"] == "estimated":
        warnings.append("Metric scale is estimated/assumed; exported measurements inherit that uncertainty.")
    if simulation_long_side is not None:
        warnings.append("SIMULATION METRES: normalized like research maps, not measured campus dimensions.")
    if units == "px":
        warnings.append("PIXEL UNITS ONLY: no metric calibration. Do not interpret coordinates, areas or robot parameters as metres.")
    if not reachable:
        warnings.append("Start and goal are disconnected in the safe-portal graph. Review geometry and robot clearance.")
    provenance = {
        "schema": "satellite-to-graph/v1", "image": identity,
        "calibration": calibration, "units": units,
        "coordinate_transform": {"origin": "boundary bottom-left" if simulation_long_side is not None else "image bottom-left",
                                 "origin_px": [origin_x, origin_y], "scale": scale,
                                 "x": "(u - origin_px[0]) * scale", "y": "(origin_px[1] - v) * scale"},
        "geometry_reviewed": True, "physical_accuracy": "not_independently_verified",
        "review": annotation.get("review"), "scene_model": annotation.get("scene_model"),
        "decomposition": "constrained_delaunay_plus_convex_merge" if merged else "constrained_delaunay_triangles",
        "warnings": warnings,
    }
    graph["provenance"] = provenance
    map_doc = {"map": {"boundary": boundary, "obstacles": holes, "coordinate_units": units,
                       **{k: planning[k] for k in ("start", "goal", "robot_radius", "safety_margin")}},
               "provenance": provenance}
    audit = {"schema": "satellite-geometry-audit/v1", "length_unit": units, "area_unit": units + "^2",
             "free_area": free.area, "regions_area": sum(p.area for p in polygons),
             "coverage_error": mismatch, "overlap_area": overlap,
             "region_count": len(polygons), "directed_edge_count": len(graph["directed_edges"]),
             "start_goal_graph_connected": bool(reachable), "warnings": warnings}
    # Preserve explicit metric audit fields for existing callers only in metric mode.
    if units == "m":
        audit.update({key + "_m2": audit[key] for key in ("free_area", "regions_area", "coverage_error", "overlap_area")})
    svg = svg_visualization(graph, width=1800, map_geometry=geometry)
    svg = svg.replace("Input map", "Input map (" + ("simulation m" if simulation_long_side is not None else units) + ")")
    return {"annotations.json": annotation, "map.json": map_doc, "regions.json": regions,
            "graph.json": graph, "audit.json": audit,
            "graph.svg": svg}


def encode_document(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def scene_svg(annotation, image):
    """Portable inspection overlay; original image is embedded without recolouring."""
    raw = io.BytesIO()
    image.save(raw, format="PNG")
    w, h = image.size
    header = 110
    units = annotation.get("coordinate_units", "m")
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {w} {h + header}">',
             '<rect width="100%" height="100%" fill="#101923"/>',
             '<text x="30" y="43" fill="white" font-family="Arial" font-size="32">Ảnh → polygon vật cản → start / goal</text>',
             f'<text x="30" y="84" fill="#b4cedd" font-family="Arial" font-size="24">Đơn vị: {units}. Biên nhà và khuôn viên vẽ xấp xỉ từ ảnh; cần kiểm tra thực địa.</text>',
             f'<g transform="translate(0 {header})">',
             f'<image width="{w}" height="{h}" href="data:image/png;base64,{base64.b64encode(raw.getvalue()).decode()}"/>']
    geometry = annotation["geometry_px"]
    for kind, rings, color, opacity in (
        ("boundary", [geometry["boundary"]], "#ffdf5b", 0),
        ("walkable", geometry["walkable"], "#56e9ae", .20),
        ("obstacle", geometry["obstacles"], "#ff414b", .36),
    ):
        for i, ring in enumerate(rings):
            points = " ".join(f"{x:.4f},{y:.4f}" for x, y in ring)
            lines.append(f'<polygon points="{points}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="4"/>')
            if kind == "obstacle":
                center = Polygon(ring).representative_point()
                lines.append(f'<text x="{center.x}" y="{center.y}" text-anchor="middle" font-family="Arial" font-size="22" font-weight="bold" fill="white" stroke="#53121a" stroke-width="4" paint-order="stroke">B{i + 1:02}</text>')
    for key, color in (("start", "#39f29a"), ("goal", "#56b8ff")):
        p = annotation["planning_px"].get(key)
        if p:
            x, y = p
            label = escape(annotation.get("endpoint_labels", {}).get(key, key))
            lines.append(f'<circle cx="{x}" cy="{y}" r="17" fill="{color}" stroke="white" stroke-width="5"/>')
            lines.append(f'<text x="{x + 25}" y="{y - 22}" font-family="Arial" font-size="28" font-weight="bold" fill="{color}" stroke="#101923" stroke-width="6" paint-order="stroke">{escape(key)}: {label}</text>')
    lines.append('</g></svg>')
    return "\n".join(lines)


def save_documents(documents, output):
    """Stage a complete bundle; refuse replacing an existing run."""
    output = Path(output)
    if output.exists():
        raise ValueError(f"Thư mục đã tồn tại: {output}. Chọn tên mới để giữ kết quả cũ.")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".satellite-", dir=output.parent))
    try:
        for name, value in documents.items():
            if isinstance(value, bytes):
                (staging / name).write_bytes(value)
            else:
                (staging / name).write_text(encode_document(value), encoding="utf-8")
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def zip_documents(documents):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in documents.items():
            archive.writestr(name, value if isinstance(value, bytes) else encode_document(value))
    return data.getvalue()



if __name__ == "__main__":
    from satellite_case import main
    raise SystemExit(main())
