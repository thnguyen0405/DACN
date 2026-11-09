# Query-specific structural preparation and Ollama scoring

This stage prepares class-1 structural information and asks a small local LLM
for exploratory **start-goal query priority** scores. It does not change
polygon decomposition, ROS/C++, collision decisions, or the retained graph.
It is not a complete implementation of Section 6 of the review: there are no
running trees, class-2 labels, online rewards, Bayesian selection, Thompson
sampling, or learned trust in the LLM.

## Run

From `convex-region-graph/`, using its existing Python environment:

```bash
source .venv/bin/activate
# Preparation only; no Ollama request:
python score_maps.py --map flappy --prepare-only
# Preparation and local model inference; checkpoints are saved after every item:
python score_maps.py --map flappy --resume
# Explicitly score a graph you rebuilt, rather than the bundled prepared graph:
python score_maps.py --map flappy --graph outputs/flappy/graph.json --k 3 --resume
```

The model defaults to `qwen3:4b-instruct`. Override with `--model` using the exact
installed name from `ollama list`. `--base-url`, `--config`, `--prompt`,
`--prepared-output`, and `--output` are also configurable. Changing the input,
model name, server URL, prompt, or response settings invalidates a checkpoint;
use a different output path, or deliberately start a fresh run without `--resume`.
Do not run two writers against the same output file.

Preparation can also run independently:

```bash
python prepare_scoring_data.py --map flappy --k 3
```

New artifacts (legacy `scores.json` remains unchanged):

| File in `outputs/<map>/` | Contents |
|---|---|
| `query_labeled_data.json` | Source graph/config hashes, original IDs/polygons/descriptors, robot and endpoints, sequences, class-1 features/memberships/labels, missing-data explanations, effective configuration |
| `query_priority_scores.json` | One result per region and undirected connection; status, integer score or null, concise reason, prompt/input hashes, model name, checkpoint/completion status |

Output directories can be changed. Default input is still
`research/data/<map>/graph.json`; use `--graph` explicitly for rebuilt graphs.
Preparation never automatically rebuilds the graph. Lengths retain the input's
simulation-meter convention; no physical calibration is introduced.

## Sequences

Only `directed_edges` already retained by clearance filtering are used. For a
retained directed connection i -> j, let m be the midpoint of its **safe** portal:

```
weight(i,j) = distance(centroid_i, m) + distance(m, centroid_j)
```

Yen's algorithm with Dijkstra spur searches finds loopless (simple) paths.
All start-region/goal-region pairs are considered, followed by a global top-k
selection. k defaults to 3; fewer paths are returned when fewer exist. Start/goal
coordinates are checked against every polygon, including shared boundaries;
if coordinates are absent, explicit endpoint-region metadata is used. A shared
endpoint region gives a zero-cost one-region sequence. Missing endpoint regions
and disconnected queries are reported explicitly, with no fabricated routes.

Each sequence stores its ordered region IDs, ordered directed connections,
original edge indices/IDs when present, individual weights and total weight.
Tie-breaking uses region-ID lexicographic order. These are **graph sequences,
not certified collision-free robot trajectories**.

## Class-1 vocabulary and configuration

Edit `structural_scoring_config.json`. It records numerical thresholds,
softness, activation/"very" cutoffs, discrete degree/endpoint rules, definitions,
and unresolved choices. Defaults are provisional values from Section 6, Tables
8 and 11, not experimentally validated scoring cutoffs.

For scalar f, increasing membership is sigmoid((f-threshold)/softness);
decreasing membership is one minus that value. Crisp conditions use 0 or 1.
A label is active at membership >= 0.5 and marked "very" at >= 0.9 by default.
All numeric memberships are saved, including inactive ones. An unavailable
membership is **null**, with an explanatory reason, not zero.

| Label | Implemented definition |
|---|---|
| open | Increasing membership of region maximum-inscribed-ball radius / robot radius, threshold 5, softness 1 |
| corridor | Degree == 2 multiplied by increasing membership of maximum-inscribed-ellipsoid axis ratio, threshold 3, softness 0.5 |
| junction | Degree >= 3 multiplied by increasing membership of returned-sequence region fraction, threshold 0.3, softness 0.1 |
| dead_end | Degree == 1 and not a start/goal-containing region |
| pocket | Endpoint-free side of a bridge in a component containing a query endpoint |
| narrow | Decreasing membership of full-dimensional portal-intersection inradius / robot radius, threshold 2, softness 0.3 |
| critical | Increasing membership of returned-sequence connection fraction, threshold 0.8, softness 0.05 |
| alternative_route | Membership in any simple start-goal path edge-disjoint from the best sequence |

Degree counts unique neighbors of the retained undirected connection graph.
Pocket and alternative-route labels require reciprocal graph edges; otherwise
those labels are explicitly unavailable. Sequences and all-path connection
checks still respect directed reachability.

Alternative-route membership is computed exactly for reciprocal graphs using a
block-cut forest after removing the best sequence's undirected edges. It does
not label a side branch merely because that branch is reachable from start.
This also detects alternatives outside the returned k sequences.

### Top-k coverage is not an all-path guarantee

`sequence_fraction` uses the **actual returned count**, not the requested k.
`in_all_returned_sequences` only refers to those sequences.
`mandatory_on_all_start_goal_paths` is a separate connectivity test: remove both
directions of the connection and check whether *any* endpoint pair remains
connected. No path means these query-dependent fractions/mandatory flags are
undefined, not evidence of importance. `on_any_simple_start_goal_path` is also
reported exactly on reciprocal graphs. Region best costs from start/to goal
are calculated in Python with the same edge weights.

### Explicit missing geometry

Current graphs do not contain:

- `vertices[].descriptors.maximum_inscribed_ball_radius`;
- `vertices[].descriptors.maximum_inscribed_ellipsoid_axis_ratio`;
- `directed_edges[].intersection_inscribed_ball_radius` for a full-dimensional
  intersection.

Thus open/corridor memberships that require those values are unavailable.
A false degree condition can still determine corridor membership as zero.
Covariance aspect ratio, mean clearance and bounding-box elongation are **not**
substituted. Explicit positive values in the above fields can be consumed later,
but this stage does not compute an inscribed ellipsoid or change decomposition.

The repository's portals are 1D shared-boundary segments. Their lengths (raw or
safe) are not the inradius of a 2D intersection. `narrow` remains unavailable
until a geometry-compatible definition is agreed or the required intersection
geometry is supplied. Original portal lengths remain available as numeric
features for scoring. Point robots have undefined radius-normalized width
memberships; no division by zero is performed.

## LLM contract

`query_scoring_prompt.txt` replaces the old local-suitability objective for this
CLI. Each request includes query metadata, sequences, retained adjacency,
configuration and target features/labels; connection requests also include both
endpoint regions. Python computes labels; LLM output cannot modify them.

The model returns `scored` with an integer 0..10, or `insufficient_data` with a
null score, and a brief reason. Higher means greater **query-specific priority**.
No additive weights or numerical scoring thresholds are introduced. The prompt
lists unresolved rubric decisions requiring supervisor agreement. Available
structural evidence may support a score despite partial missing class-1 labels.
Disconnected queries are marked insufficient without model calls.

Connections are assessed as undirected connection importance, once per pair;
original directed records are retained in the prepared data. No low score
removes a region or connection. The model does not certify feasibility and
cannot override the graph. Model explanations remain fallible; inspect them
for unsupported route claims and missing-data confusion. Completion adds conservative
`review_flags` for possible unsupported positive label/necessity claims and a
review count. These text heuristics can flag legitimate contextual mentions and
can miss errors; they neither certify explanations nor modify scores or labels.

Old `scoring_prompt.txt` and `outputs/<map>/scores.json` are kept as local-geometry
baselines. Comparing their numbers with new query-priority numbers is descriptive
only: a difference is not an error metric because the objectives differ.

## Checks

```bash
python -B -m unittest discover -v
```

Tests cover weights, loopless top-k enumeration against exhaustive small-graph
oracles, multiple/shared endpoints, disconnection, retained-edge direction,
bridge pockets, edge-disjoint alternatives, top-k versus all-path necessity,
missing-data behavior, configurable memberships, output protection, and mocked
LLM schema/checkpoint behavior. Live Ollama scoring is an integration run, not
proof of priority-score quality or planner improvement.
