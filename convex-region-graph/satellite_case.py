"""Headless import of a satellite image into the existing research/demo pipeline."""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time
import uuid

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from satellite_to_graph import (annotation_template, build_documents, check_identity,
                                encode_document, finite_number, mask_to_polygons,
                                read_image, save_documents)
from research.geometry import GridReference, World

ROOT = Path(__file__).resolve().parent


def satellite_overlay(image, annotation):
    """Draw source-image geometry at full resolution, without a browser or padding."""
    canvas = image.convert("RGBA")
    layer = Image.new("RGBA", canvas.size)
    draw = ImageDraw.Draw(layer)
    width = max(2, round(image.width / 550))
    geom = annotation["geometry_px"]
    for ring in geom.get("obstacles", []):
        xy = [tuple(p) for p in ring]
        draw.polygon(xy, fill=(255, 80, 90, 65))
        draw.line(xy + xy[:1], fill="#ff7078", width=width, joint="curve")
    for ring in geom.get("walkable", []):
        xy = [tuple(p) for p in ring]
        draw.line(xy + xy[:1], fill="#59edb1", width=width, joint="curve")
    boundary = [tuple(p) for p in geom["boundary"]]
    draw.line(boundary + boundary[:1], fill="#ffe467", width=width + 1, joint="curve")
    canvas = Image.alpha_composite(canvas, layer)
    draw = ImageDraw.Draw(canvas)
    font_size = max(18, round(image.width / 48))
    font = None
    for name in ("/System/Library/Fonts/Supplemental/Arial.ttf", "DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(name, font_size)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default(size=font_size)
    radius = max(8, round(image.width / 80))
    for key, color in (("start", "#39edaa"), ("goal", "#ff709e")):
        x, y = annotation["planning_px"][key]
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color,
                     outline="white", width=max(2, width))
        label = key + ": " + annotation.get("endpoint_labels", {}).get(key, key)
        bounds = draw.textbbox((0, 0), label, font=font)
        tx = max(5, min(x + radius, image.width - (bounds[2]-bounds[0]) - 8))
        ty = max(5, min(y-font_size*1.6, image.height-font_size*1.5))
        draw.text((tx, ty), label, font=font, fill=color, stroke_width=2, stroke_fill="#12222b")
    data = io.BytesIO()
    canvas.convert("RGB").save(data, format="PNG")
    return data.getvalue()


def build_case(image, identity, annotation, *, scale_mode="simulation", long_side=20,
               radius=None, margin=None, grid_step=.1, allow_estimated=False):
    begin = time.perf_counter()
    annotation = copy.deepcopy(annotation)
    if scale_mode not in ("simulation", "calibrated"):
        raise ValueError("scale_mode phải là simulation hoặc calibrated.")
    annotation["coordinate_units"] = "m"
    robot = annotation.setdefault("robot", {})
    if radius is not None or scale_mode == "simulation":
        robot["radius_m"] = .1 if radius is None else radius
    if margin is not None or scale_mode == "simulation":
        robot["safety_margin_m"] = .05 if margin is None else margin
    annotation["export_settings"] = {"scale_mode": scale_mode,
                                     "long_side_m": long_side if scale_mode == "simulation" else None}
    docs = build_documents(annotation, identity, allow_estimated,
                           simulation_long_side=long_side if scale_mode == "simulation" else None)
    world = World(docs["map.json"])
    step = finite_number(grid_step, "Bước lưới tham chiếu", 1e-6)
    x0, y0, x1, y1 = world.bounds
    nx, ny = math.ceil((x1-x0)/step), math.ceil((y1-y0)/step)
    if nx * ny > 250_000 or min(x1-x0, y1-y0) <= step/2:
        raise ValueError("Bước lưới không phù hợp: cần 1–250000 điểm. Điều chỉnh --grid-step.")
    planning = docs["graph.json"]["planning"]
    reference = GridReference(world, step).shortest(planning["start"], planning["goal"])
    if reference:
        reference["coordinate_mode"] = scale_mode
    audit = docs.pop("audit.json")
    audit.update(rebuilt_vertices=len(docs["graph.json"]["vertices"]),
                 rebuilt_directed_edges=len(docs["graph.json"]["directed_edges"]),
                 endpoint_policy="preserve annotated start and goal; never relocate",
                 reference_found=reference is not None, reference_grid_step=step,
                 coordinate_mode=scale_mode, preparation_seconds=time.perf_counter()-begin)
    if reference is None:
        audit["warnings"].append("No path on the reference grid; this alone does not prove continuous infeasibility.")
    docs["import_audit.json"] = audit
    docs["reference.json"] = reference
    docs["satellite_overlay.png"] = satellite_overlay(image, annotation)
    docs["pipeline_status.json"] = {
        "geometry": "complete", "llm": "not_requested", "sampling_prior": "not_created",
        "start_region": planning["start_region"], "goal_region": planning["goal_region"],
        "coordinate_mode": scale_mode,
    }
    return docs


def score_case(directory, env_file, model="openrouter/free", provider=None,
               max_tokens=32768, timeout=180, reasoning_effort="none"):
    """Use the same real provider and validators as the research/demo maps.

    Publish the prior only after every region is scored. A failed call cannot
    silently substitute mock scores or overwrite a previous successful result.
    """
    from llm_region_prior import build_region_prior
    from export_sampling_prior import build_sampling_prior
    directory = Path(directory)
    max_tokens = int(finite_number(max_tokens, "Token đầu ra", 1))
    timeout = finite_number(timeout, "Timeout", 1)
    names = ("llm_prior.json", "sampling_prior.json")
    if any((directory / name).exists() for name in names):
        raise ValueError("Case đã có prior. Tạo case mới để chấm lại, tránh dùng nhầm kết quả cũ.")
    raw = (directory / "graph.json").read_bytes()
    graph = json.loads(raw)
    audit = json.loads((directory / "import_audit.json").read_text())
    if not audit["start_goal_graph_connected"]:
        raise ValueError("Start/goal chưa nối được trong graph; kiểm tra hình học trước khi gọi LLM.")
    status_path = directory / "pipeline_status.json"
    status = json.loads(status_path.read_text())
    status.update(llm="running", sampling_prior="not_created")
    status_path.write_text(encode_document(status))
    published = []
    temporary_files = []
    try:
        if provider is None:
            from research.llm_study import StudyProvider
            log_dir = directory / "llm_calls" / uuid.uuid4().hex[:12]
            provider = StudyProvider(graph, log_dir, env_file, model=model, timeout=timeout,
                                     reasoning_effort=reasoning_effort)
            provider.max_tokens = max_tokens
            _, metadata = provider.score()
            response = json.loads((log_dir / "call-00.json").read_text())["response"]
        else:
            # Dependency injection for deterministic integration/failure tests.
            response, metadata = provider(graph)
        planning = graph["planning"]
        prior, _, scores, missing = build_region_prior(
            graph, planning["start_region"], planning["goal_region"], response=response)
        if missing:
            raise ValueError(f"LLM thiếu {len(missing)} vùng; không xuất sampling prior với điểm thay thế.")
        prior.update(scores=scores, metadata=metadata, graph_sha256=hashlib.sha256(raw).hexdigest())
        sampling, missing = build_sampling_prior(graph, prior)
        if missing:
            raise ValueError("Sampling prior không đủ điểm.")
        # The status is the completion marker; both JSON files must exist.
        for name, doc in zip(names, (prior, sampling)):
            temporary = directory / ("." + name + ".tmp")
            temporary_files.append(temporary)
            temporary.write_text(encode_document(doc), encoding="utf-8")
        for name, temporary in zip(names, temporary_files):
            temporary.replace(directory / name)
            published.append(directory / name)
        status.update(llm="complete", sampling_prior="complete")
    except Exception:
        for path in published + temporary_files:
            path.unlink(missing_ok=True)
        status.update(llm="failed", sampling_prior="not_created")
        status_path.write_text(encode_document(status))
        raise
    status_path.write_text(encode_document(status))
    return prior


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Tạo cấu hình polygon hoặc nhập mask; không mở web.")
    init.add_argument("--image", required=True, type=Path)
    init.add_argument("--mask", type=Path)
    init.add_argument("--simplify-px", type=float, default=2)
    init.add_argument("--start", nargs=2, type=float, metavar=("X", "Y"))
    init.add_argument("--goal", nargs=2, type=float, metavar=("X", "Y"))
    init.add_argument("--output", required=True, type=Path)
    build = commands.add_parser("build", help="Ảnh + polygon → hai hình + bộ JSON nghiên cứu.")
    build.add_argument("--image", required=True, type=Path)
    build.add_argument("--annotations", type=Path, help="Mặc định annotations.json cạnh ảnh.")
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--scale-mode", choices=("simulation", "calibrated"), default="simulation")
    build.add_argument("--long-side", type=float, default=20)
    build.add_argument("--radius", type=float)
    build.add_argument("--margin", type=float)
    build.add_argument("--grid-step", type=float, default=.1)
    build.add_argument("--allow-estimated-scale", action="store_true")
    build.add_argument("--llm", action="store_true", help="Gọi LLM thật và xuất sampling_prior.json sau khi tạo map.")
    score = commands.add_parser("score", help="Chấm LLM cho case đã tạo; không phân rã lại.")
    score.add_argument("--case", required=True, type=Path)
    for sub in (build, score):
        sub.add_argument("--env-file", type=Path, default=ROOT / ".env")
        sub.add_argument("--model", default="openrouter/free")
        sub.add_argument("--max-tokens", type=int, default=32768)
        sub.add_argument("--timeout", type=float, default=180)
        sub.add_argument("--reasoning-effort", choices=("none", "minimal", "low"), default="none")
    args = parser.parse_args(argv)
    try:
        if args.command == "score":
            score_case(args.case, args.env_file, args.model, max_tokens=args.max_tokens, timeout=args.timeout,
                       reasoning_effort=args.reasoning_effort)
            print(f"Đã xuất {args.case / 'llm_prior.json'} và sampling_prior.json")
            return 0
        image, identity = read_image(args.image)
        if args.command == "init":
            annotation = annotation_template(identity)
            if args.mask:
                with Image.open(args.mask) as mask:
                    if mask.size != image.size:
                        raise ValueError("Mask phải cùng kích thước ảnh sau EXIF.")
                    proposal = mask_to_polygons(np.asarray(mask.convert("L")) >= 128,
                                                *image.size, args.simplify_px)
                annotation["geometry_px"].update({k: proposal[k] for k in ("walkable", "obstacles")})
                annotation["proposal_audit"] = proposal["audit"]
            for key in ("start", "goal"):
                if getattr(args, key) is not None:
                    annotation["planning_px"][key] = getattr(args, key)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encode_document(annotation))
            print(f"Đã tạo {args.output}. Điền/kiểm tra polygon, start/goal và review.geometry_confirmed.")
            return 0
        if args.output.exists():
            raise ValueError(f"Case đã tồn tại: {args.output}. Dùng lệnh score hoặc chọn thư mục mới.")
        path = args.annotations or args.image.with_name("annotations.json")
        if not path.exists():
            raise ValueError(f"Thiếu {path}. Dùng init để nhập polygon/mask; ảnh RGB đơn lẻ chưa đủ xác định vật cản.")
        annotation = json.loads(path.read_text(encoding="utf-8"))
        check_identity(annotation, identity)
        print("Đang phân rã, tính descriptor và đường tham chiếu...", flush=True)
        docs = build_case(image, identity, annotation, scale_mode=args.scale_mode,
                          long_side=args.long_side, radius=args.radius, margin=args.margin,
                          grid_step=args.grid_step, allow_estimated=args.allow_estimated_scale)
        save_documents(docs, args.output)
        audit = docs["import_audit.json"]
        print(f"Đã lưu {args.output}: {audit['region_count']} vùng; {audit['directed_edge_count']} cạnh có hướng.")
        print("Hai hình: graph.svg và satellite_overlay.png")
        print(f"Tỷ lệ: {args.scale_mode}; tham chiếu tìm được: {audit['reference_found']}")
        if args.llm:
            print("Đang gọi LLM thật; nếu lỗi, giữ bộ hình học để thử lại bằng lệnh score.", flush=True)
            score_case(args.output, args.env_file, args.model, max_tokens=args.max_tokens, timeout=args.timeout,
                       reasoning_effort=args.reasoning_effort)
            print("Đã xuất llm_prior.json và sampling_prior.json.")
    except Exception as exc:
        from llm_weight_provider import LLMProviderError
        if not isinstance(exc, (OSError, ValueError, KeyError, TypeError, AttributeError, LLMProviderError)):
            raise
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
