import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MODEL = "qwen3:4b-instruct"  # Use the exact name from `ollama list`.
PROMPT = (ROOT / "scoring_prompt.txt").read_text(encoding="utf-8")

SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["scored", "insufficient_data", "infeasible"],
        },
        "score": {
            "anyOf": [
                {"type": "integer", "minimum": 0, "maximum": 10},
                {"type": "null"},
            ]
        },
        "reason": {"type": "string"},
    },
    "required": ["status", "score", "reason"],
    "additionalProperties": False,
}


def ask_ollama(task, features):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"task": task, "features": features},
                    allow_nan=False,
                ),
            },
        ],
        "format": SCHEMA,
        "stream": False,
        "options": {"temperature": 0},
    }

    request = Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urlopen(request, timeout=600) as response:
        result = json.load(response)

    answer = json.loads(result["message"]["content"])
    score = answer["score"]

    if answer["status"] == "scored":
        if type(score) is not int or not 0 <= score <= 10:
            raise ValueError(f"Invalid score: {answer}")
    elif score is not None:
        raise ValueError(f"Unscored result must have null score: {answer}")

    return answer


def score_map(map_name):
    path = ROOT / "research" / "data" / map_name / "graph.json"
    graph = json.loads(path.read_text(encoding="utf-8"))

    clearance = graph["planning"]["required_clearance"]
    vertices = {v["id"]: v for v in graph["vertices"]}

    output = {
        "map": map_name,
        "model": MODEL,
        "regions": [],
        "edges": [],
    }

    for vertex in graph["vertices"]:
        features = {
            **vertex["descriptors"],
            "required_clearance": clearance,
        }

        print(f"{map_name}: scoring region {vertex['id']}", flush=True)
        answer = ask_ollama("score_region", features)
        output["regions"].append({"id": vertex["id"], **answer})

    # Geometric scoring is symmetric: reuse the reverse edge's score.
    edge_cache = {}

    for edge in graph["directed_edges"]:
        source, target = edge["source"], edge["target"]
        key = tuple(sorted((source, target)))

        if key not in edge_cache:
            features = {
                "portal_width": edge["portal_width"],
                "safe_portal_width": edge["safe_portal_width"],
                "safe_traversability": edge.get("safe_traversability"),
                "required_clearance": clearance,
                "source_mean_clearance":
                    vertices[source]["descriptors"]["mean_clearance"],
                "target_mean_clearance":
                    vertices[target]["descriptors"]["mean_clearance"],
            }

            print(f"{map_name}: scoring edge {source} -> {target}", flush=True)
            edge_cache[key] = ask_ollama("score_edge", features)

        output["edges"].append({
            "source": source,
            "target": target,
            **edge_cache[key],
        })

    destination = ROOT / "outputs" / map_name / "scores.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(output, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(f"Saved: {destination}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Score regions and edges for one selected map using Ollama."
    )
    parser.add_argument(
        "--map",
        required=True,
        choices=["hole", "narrow", "flappy", "room"],
        help="Map to score; results are saved to outputs/<map>/scores.json.",
    )
    args = parser.parse_args()
    score_map(args.map)


if __name__ == "__main__":
    main()
