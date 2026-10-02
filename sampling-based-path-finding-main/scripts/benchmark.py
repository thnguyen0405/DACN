#!/usr/bin/env python3
"""Run seeded ROS planners and save per-run plus aggregate JSON/CSV metrics."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import time
from typing import Any

RESULT_LINE = re.compile(r"\[RESULT\]\s+(.*)")
FIELDS = (
    "planning_time_ms", "time_to_first_solution_ms", "path_length",
    "straight_line_distance", "path_length_ratio", "iterations", "nodes_added",
)


def parse_result(text: str) -> dict[str, Any] | None:
    matches = RESULT_LINE.findall(text)
    if not matches:
        return None
    tokens = dict(re.findall(r"([A-Za-z_]+)=([^\s]+)", matches[-1]))
    required = {"planner", "guidance", "success", *FIELDS}
    if not required.issubset(tokens):
        return None
    result: dict[str, Any] = {
        "planner": tokens["planner"], "mode": tokens["guidance"],
        "success": tokens["success"] == "1",
    }
    for field in FIELDS:
        value = float(tokens[field])
        if not math.isfinite(value):
            return None
        if field in ("iterations", "nodes_added"):
            result[field] = int(value)
        elif not result["success"] and field in ("path_length", "path_length_ratio", "time_to_first_solution_ms"):
            result[field] = None
        else:
            result[field] = value
    return result


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["planner"], row["mode"]), []).append(row)
    output = []
    for (planner, mode), group in sorted(groups.items()):
        success = [row for row in group if row.get("success")]
        record: dict[str, Any] = {
            "planner": planner, "mode": mode, "runs": len(group),
            "successes": len(success), "success_rate": len(success) / len(group),
        }
        for field in FIELDS:
            values = [row[field] for row in group if row.get(field) is not None]
            record[f"{field}_mean"] = statistics.fmean(values) if values else None
            record[f"{field}_stdev"] = statistics.stdev(values) if len(values) > 1 else 0.0 if values else None
        output.append(record)
    return output


def write_outputs(output: Path, metadata: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({**metadata, "results": rows, "summary": summarize(rows)}, indent=2) + "\n", encoding="utf-8")
    columns = ["planner", "mode", "seed", "success", *FIELDS, "timeout", "error", "log"]
    with output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--sequence-strategy", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("benchmark.json"))
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=42)
    parser.add_argument("--search-time", type=float, default=1.0)
    parser.add_argument("--port", type=int, default=11329)
    parser.add_argument("--planners", nargs="+", default=["rrt", "rrt_star", "rrt_sharp", "brrt", "brrt_star", "informed_rrt_star"])
    args = parser.parse_args(argv)
    if args.repeats < 1 or args.search_time <= 0:
        parser.error("Positive repeats and search-time required")
    for path in (args.map, args.prior, args.sequence_strategy):
        if not path.is_file(): parser.error(f"Input file not found: {path}")

    env = dict(os.environ, ROS_MASTER_URI=f"http://localhost:{args.port}", ROS_HOSTNAME="localhost")
    rows: list[dict[str, Any]] = []
    logs = args.output.parent / (args.output.stem + "_logs"); logs.mkdir(parents=True, exist_ok=True)
    metadata = {
        "map": str(args.map.resolve()), "prior": str(args.prior.resolve()),
        "sequence_strategy": str(args.sequence_strategy.resolve()),
        "search_time_seconds": args.search_time, "repeats": args.repeats,
        "seeds": list(range(args.seed_start, args.seed_start + args.repeats)),
        "llm_api_time_included": False,
    }
    for planner_name in args.planners:
        for mode in ("none", "region_prior", "sequence_guided"):
            for seed in metadata["seeds"]:
                command = ["roslaunch", "--port", str(args.port), "path_finder", "test_planners.launch",
                    f"map_file:={args.map.resolve()}", f"sampling_prior_file:={args.prior.resolve()}",
                    f"sequence_strategy_file:={args.sequence_strategy.resolve()}",
                    f"planner:={planner_name}", f"guidance_mode:={mode}", f"random_seed:={seed}",
                    f"search_time:={args.search_time}", "step_mode:=false", "planar:=true",
                    "use_informed_sampling:=false", "launch_prefix:=stdbuf -oL -eL"]
                log_path = logs / f"{planner_name}-{mode}-{seed}.log"; timed_out = False
                with log_path.open("w", encoding="utf-8") as log:
                    process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    try:
                        deadline = time.monotonic() + args.search_time + 30.0
                        while time.monotonic() < deadline:
                            if parse_result(log_path.read_text(errors="replace")) or process.poll() is not None: break
                            time.sleep(0.1)
                        else: timed_out = True
                    finally:
                        if process.poll() is None:
                            os.killpg(process.pid, signal.SIGINT)
                            try: process.wait(timeout=8)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL); process.wait()
                parsed = parse_result(log_path.read_text(errors="replace"))
                row: dict[str, Any] = {"planner": planner_name, "mode": mode, "seed": seed, "timeout": timed_out, "log": str(log_path)}
                if parsed: row.update(parsed)
                else: row.update(success=False, error="timeout" if timed_out else "No valid [RESULT] record")
                rows.append(row); print(json.dumps(row), flush=True); write_outputs(args.output, metadata, rows)
    return 1 if any(row.get("error") for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
