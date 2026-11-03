# Multi-Map Demo: HCMUT Satellite Image → Convex Region Graph → LLM → RViz

## Overview

This guide explains how to run the complete motion-planning demonstration on your own computer.

The pipeline converts a satellite image or an existing research map into a graph of convex regions, uses a Large Language Model (LLM) to generate region-priority scores, and runs sampling-based motion planners in ROS with RViz visualization.

**Processing pipeline:**

```text
Satellite Image / Existing Map
            |
            v
    Map Geometry
            |
            v
 Convex Decomposition
            |
            v
  Convex Region Graph
            |
            v
     LLM Scoring
            |
            v
   Sampling Prior
            |
            v
    ROS / C++ Planners
            |
            v
      RViz Demo
```

The HCMUT example uses a satellite image with manually annotated building polygons. The start and goal positions represent **Gate 1 and Gate 2**, respectively.

All commands are executed through the Terminal. No web-based map editor is required.

---

## 1. System Requirements

Before starting, make sure your computer has the following software:

| Requirement | Purpose |
|---|---|
| Git | Clone the repository |
| Python 3 | Run image processing, graph generation, and LLM scripts |
| Python virtual environment | Manage Python dependencies |
| Docker Desktop or Docker Engine | Run the ROS environment |
| `motion-planner-vnc` container | Run the motion planners and RViz |
| Internet connection | Download dependencies and call OpenRouter |
| OpenRouter API key | Generate real LLM-based region scores |

The commands in this guide use a Bash-compatible terminal on **macOS or Linux**.

Windows users can use a suitable Linux environment, such as WSL2, with Docker configured to work with it.

### Important notes

- Start Docker before running the RViz demonstration.
- The Docker container must already be created and configured with the project's ROS dependencies.
- Keep commands for one demo in the same Terminal session so that environment variables remain available.
- Do not continue to the next step if the current step fails.
- The LLM scoring stage requires a valid API key unless a previously generated sampling prior is available.

---

## 2. Clone the Repository

Open a Terminal and run:

```bash
git clone https://github.com/thnguyen0405/DACN.git
cd DACN
```

To use a specific development branch, list the available branches:

```bash
git branch -a
```

Then switch to the required branch:

```bash
git switch <branch-name>
```

Replace `<branch-name>` with the actual branch name.

**Note:** Different branches may contain different features. The commands below describe the satellite-to-graph and ROS demonstration workflow documented here.

### Open the graph-processing module

From the repository root:

```bash
cd convex-region-graph
```

All subsequent commands assume that your Terminal is inside this directory, unless otherwise specified.

You can check your current directory using:

```bash
pwd
```

---

## 3. Configure the Python Environment

The project uses a Python virtual environment named `.venv-satellite` for satellite-image processing, geometry operations, graph generation, and LLM scoring.

### Create the virtual environment

From `convex-region-graph`:

```bash
python3 -m venv .venv-satellite
```

Activate it:

```bash
source .venv-satellite/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install the Python dependencies specified by the project.

If the checked-out branch provides a suitable `requirements.txt`, use:

```bash
python -m pip install -r requirements.txt
```

If that file is not present, follow the branch's Python dependency instructions before proceeding. This guide does not assume that an unverified requirements file exists.

### Select the Python interpreter

```bash
PYTHON="$PWD/.venv-satellite/bin/python"
```

Verify that Python is available:

```bash
"$PYTHON" --version
```

**Important:** The `PYTHON` variable is only available in the current Terminal session. Define it again if you open a new Terminal.

---

## 4. Configure the OpenRouter API

The project uses OpenRouter to generate region-priority scores.

Inside `convex-region-graph`, create or edit:

```text
.env
```

Add your API key:

```dotenv
OPENROUTER_API_KEY=your_openrouter_api_key
```

Replace the placeholder with your actual API key.

Keep this file private. Do not commit API keys to GitHub.

To use OpenRouter, the selected model must also be available through your account and have sufficient quota.

On systems where Python encounters SSL certificate errors, you may need to configure the certificate bundle. On macOS, when the following file exists, you can use:

```bash
export SSL_CERT_FILE=/etc/ssl/cert.pem
```

This setting is only necessary when appropriate for your system. It is not required on every machine.

---

## 5. Available Maps

The repository includes the following research maps and HCMUT case.

| Map | Convex Regions | Start Region | Goal Region |
|---|---:|---|---|
| `hole` | 9 | C4 | C5 |
| `narrow` | 16 | C4 | C0 |
| `flappy` | 45 | C14 | C43 |
| `room` | 104 | C40 | C85 |
| `hcmut_cs1` | 164 | C17 | C144 |

These region IDs apply to the current datasets.

**Do not hardcode these IDs into new experiments.** If the input geometry or convex decomposition changes, read the updated start and goal regions from `graph.json`.

---

# Part A — Generate a New HCMUT Demo

## 6. Step 1: Generate the HCMUT Map and Convex Region Graph

The HCMUT dataset contains:

```text
examples/satellite/hcmut_cs1/
├── image.png
└── annotations.json
```

- `image.png`: Satellite image of the HCMUT campus.
- `annotations.json`: Campus boundary, manually annotated buildings, start/goal, and related metadata.

Run:

```bash
CASE="hcmut_demo_$(date +%Y%m%d_%H%M%S)"
CASE_DIR="research/data/$CASE"
SAMPLING_PRIOR="$CASE_DIR/sampling_prior.json"

"$PYTHON" satellite_to_graph.py build \
  --image examples/satellite/hcmut_cs1/image.png \
  --annotations examples/satellite/hcmut_cs1/annotations.json \
  --scale-mode simulation \
  --long-side 20 \
  --output "$CASE_DIR"
```

### What does this command do?

The script:

1. Loads the satellite image and annotations.
2. Constructs the map's free space.
3. Decomposes the free space into convex regions.
4. Calculates geometric region descriptors.
5. Constructs the region connectivity graph.
6. Generates the map data and visualization files.

**This step does not call the LLM.**

### Output files

A new directory is created under:

```text
convex-region-graph/research/data/
```

Example:

```text
research/data/hcmut_demo_20261103_153000/
```

The output includes the following files, according to the documented HCMUT pipeline:

| File | Description |
|---|---|
| `graph.svg` | Visualization of convex regions and graph connections |
| `satellite_overlay.png` | Satellite image with campus boundary, buildings, start and goal |
| `map.json` | Geometry used by the motion planner |
| `regions.json` | Convex region geometry and descriptors |
| `graph.json` | Region connectivity and planning information |
| `reference.json` | Reference-path information |
| `annotations.json` | Input annotation data |
| `import_audit.json` | Import and geometry validation results |
| `pipeline_status.json` | Processing status |

Open `graph.svg` and `satellite_overlay.png` with your preferred image viewer.

### About the map scale

The HCMUT demo uses:

```bash
--scale-mode simulation --long-side 20
```

This normalizes the longest map dimension to **20 simulated meters**.

It does not represent the actual physical dimensions of the university.

The building polygons were approximated from the satellite image and have not been verified by an on-site survey.

The current model treats the remaining space inside the campus boundary as free space. It does not exclusively restrict navigation to designated pedestrian walkways.

---

## 7. Step 2: Generate LLM Region Scores

After the map has been successfully generated, run:

```bash
"$PYTHON" satellite_to_graph.py score \
  --case "$CASE_DIR" \
  --model openrouter/free \
  --reasoning-effort low \
  --timeout 0 \
  --max-tokens 32768
```

### What does this command do?

The script:

1. Loads the generated convex region graph.
2. Reads start and goal information from the graph.
3. Sends the relevant graph information to OpenRouter.
4. Requests region-priority scores.
5. Validates the returned scores.
6. Exports the data required by the C++ sampling-based planners.

### Expected output

Two important files are generated:

**`llm_prior.json`**

Contains the LLM scoring results, including region scores and their explanations.

**`sampling_prior.json`**

Contains the region geometry and priority data required by the C++ planners.

The `sampling_prior.json` file is generated automatically by the HCMUT scoring workflow.

You do not need to run `export_sampling_prior.py` separately for this case.

### API timeout behavior

By default:

```bash
--timeout 0
```

Disables the request timeout and program deadline for the CLI workflow. The process continues waiting until it receives a response, encounters another error, or is interrupted.

To set a 180-second timeout per request:

```bash
--timeout 180
```

The Terminal reports elapsed waiting time periodically and displays progress after completed batches.

### OpenRouter model behavior

The `openrouter/free` identifier may select different underlying models across requests.

Some providers require reasoning to be enabled. If OpenRouter reports that reasoning cannot be disabled, the scoring workflow attempts a retry using low reasoning effort.

Completed batches are preserved within the current process, but the documented workflow does not support resuming a terminated scoring process from saved batches.

If the API fails, do not use incomplete scoring results.

### Confirm successful completion

Check that these files exist:

```bash
ls -lh "$CASE_DIR/llm_prior.json"
ls -lh "$CASE_DIR/sampling_prior.json"
```

The pipeline status should indicate:

```text
llm: complete
sampling_prior: complete
```

If scoring fails, fix the reported problem before starting RViz.

You do not need to regenerate the map simply because the API request failed.

---

## 8. Step 3: Run the Generated Map in RViz

Before running the demo:

- Make sure Docker is running.
- Make sure the `motion-planner-vnc` container already exists and has the necessary ROS environment.
- Verify that `map.json` and `sampling_prior.json` were generated successfully.

Check whether the container exists:

```bash
docker ps -a --filter "name=motion-planner-vnc"
```

If no matching container is listed, complete the project's Docker/ROS setup first. The following commands start an existing container; they do not create a new one.

### Launch the demo

Run the following command from `convex-region-graph`:

```bash
test -s "$CASE_DIR/map.json" && \
test -s "$SAMPLING_PRIOR" && \
docker start motion-planner-vnc && \
docker exec motion-planner-vnc mkdir -p /tmp/demo-case && \
docker cp "$CASE_DIR/map.json" \
  motion-planner-vnc:/tmp/demo-case/map.json && \
docker cp "$SAMPLING_PRIOR" \
  motion-planner-vnc:/tmp/demo-case/sampling_prior.json && \
ROS_DISPLAY=:1 bash ../scripts/run_container_demo.sh \
  map_file:=/tmp/demo-case/map.json \
  sampling_prior_file:=/tmp/demo-case/sampling_prior.json \
  planner:=all \
  rviz:=true
```

The commands are connected using `&&`.

This prevents the demo from starting if an earlier validation or file-copy operation fails.

### Open RViz

Keep the Terminal running.

Open your browser and visit:

http://localhost:6080

This opens the container's VNC desktop, where RViz is displayed.

It is not a satellite-image editor.

### Configure RViz

In RViz, open:

**Displays → Planning**

Enable the desired visualization elements:

- Region boundaries
- Start
- Goal
- Individual planner groups, from `01 RRT` through `06 Informed RRT*`

Disable other planner groups when their paths overlap and make the visualization difficult to read.

The start and goal positions come from `map.json`.

For the HCMUT case:

```text
Start: Gate 1
Goal:  Gate 2
```

### Read the results

The Terminal prints lines beginning with:

```text
[RESULT]
```

These contain planner results.

To stop the demo:

```text
Ctrl + C
```

---

# Part B — Run the Pre-generated HCMUT Case

## 9. Run HCMUT Without Regenerating the Map or Calling the LLM

If the repository already contains the completed `hcmut_cs1` dataset, you can launch it directly.

Navigate to the module directory:

```bash
cd convex-region-graph
```

If you are already inside that directory, skip this command.

Then configure:

```bash
CASE="hcmut_cs1"
CASE_DIR="research/data/$CASE"
SAMPLING_PRIOR="$CASE_DIR/sampling_prior.json"
```

Confirm that the existing files are available:

```bash
ls -lh "$CASE_DIR/map.json"
ls -lh "$SAMPLING_PRIOR"
```

If both files exist, execute the **RViz launch command in Step 3**.

You do not need to run the map-generation or LLM-scoring steps again.

This is the recommended option for users who only want to view the existing HCMUT demonstration.

---

# Part C — Run Other Research Maps

## 10. Switch to `hole`, `narrow`, `flappy`, or `room`

The same ROS demonstration can be used with other research maps.

Available cases:

```text
hole
narrow
flappy
room
```

First stop any running RViz demo with `Ctrl + C`.

### Step 1: Select the map

For example, to run `flappy`:

```bash
CASE="flappy"
CASE_DIR="research/data/$CASE"
SAMPLING_PRIOR="$CASE_DIR/demo_sampling_prior.json"
```

To use another map, change only the `CASE` value.

For example:

```bash
CASE="narrow"
```

Then redefine `CASE_DIR` and `SAMPLING_PRIOR` using the commands above.

### Step 2: Generate the graph visualization

```bash
"$PYTHON" - "$CASE_DIR" <<'PY'
import json
import sys
from pathlib import Path
from build_graph import svg_visualization

folder = Path(sys.argv[1])

graph = json.loads(
    (folder / "graph.json").read_text()
)

geometry = json.loads(
    (folder / "map.json").read_text()
)["map"]

geometry["planning"] = graph["planning"]

(folder / "graph.svg").write_text(
    svg_visualization(
        graph,
        width=1500,
        map_geometry=geometry
    ),
    encoding="utf-8",
)

print("Graph visualization:", folder / "graph.svg")
PY
```

This produces:

```text
research/data/<map-name>/graph.svg
```

The planning data is passed to the visualization function so that the start and goal information is available.

### Step 3: Read start and goal region IDs

```bash
START_REGION=$(
  "$PYTHON" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["planning"]["start_region"])' \
  "$CASE_DIR/graph.json"
)

GOAL_REGION=$(
  "$PYTHON" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["planning"]["goal_region"])' \
  "$CASE_DIR/graph.json"
)

echo "Start region: $START_REGION"
echo "Goal region: $GOAL_REGION"
```

These commands use the actual graph data, rather than relying on fixed region IDs.

### Step 4: Generate the LLM prior

```bash
"$PYTHON" llm_region_prior.py \
  "$CASE_DIR/graph.json" \
  --start "$START_REGION" \
  --goal "$GOAL_REGION" \
  --provider openrouter \
  --output "$CASE_DIR/demo_prior.json"
```

If scoring succeeds, export the C++ sampling prior:

```bash
"$PYTHON" export_sampling_prior.py \
  --graph "$CASE_DIR/graph.json" \
  --prior "$CASE_DIR/demo_prior.json" \
  --output "$SAMPLING_PRIOR"
```

Check the result:

```bash
ls -lh "$SAMPLING_PRIOR"
```

### Step 5: Run the selected map in RViz

Once `map.json` and the sampling prior are available, execute the same **RViz launch command from Step 3**.

The demo will use the currently selected map.

**Important:** Every map requires its own scoring and sampling-prior data. Do not reuse another map's `sampling_prior.json`.

---

## 11. Output Directory Structure

After successfully running a case, the relevant files are organized approximately as follows:

```text
DACN/
├── convex-region-graph/
│   ├── .env
│   ├── .venv-satellite/
│   ├── satellite_to_graph.py
│   ├── llm_region_prior.py
│   ├── export_sampling_prior.py
│   ├── examples/
│   │   └── satellite/
│   │       └── hcmut_cs1/
│   │           ├── image.png
│   │           └── annotations.json
│   └── research/
│       └── data/
│           ├── hole/
│           ├── narrow/
│           ├── flappy/
│           ├── room/
│           ├── hcmut_cs1/
│           └── hcmut_demo_<timestamp>/
│               ├── annotations.json
│               ├── map.json
│               ├── regions.json
│               ├── graph.json
│               ├── graph.svg
│               ├── satellite_overlay.png
│               ├── reference.json
│               ├── import_audit.json
│               ├── llm_prior.json
│               ├── sampling_prior.json
│               └── pipeline_status.json
└── scripts/
    └── run_container_demo.sh
```

The exact files present depend on the selected map and which pipeline stages have completed.

---

## 12. Troubleshooting

### Problem: `python: command not found`

Use Python 3 instead:

```bash
python3 --version
```

Create the virtual environment with `python3`, then use the interpreter inside `.venv-satellite`.

### Problem: `ModuleNotFoundError`

The required Python dependencies may not be installed in the selected environment.

Verify the interpreter:

```bash
"$PYTHON" --version
```

Install the project's required dependencies into that environment.

### Problem: `OPENROUTER_API_KEY` is missing

Check that `.env` exists inside `convex-region-graph` and contains a valid OpenRouter API key.

Do not include extra spaces around the variable name.

### Problem: OpenRouter takes too long

LLM scoring may be slow because of provider availability, model inference time, or network latency.

Use a positive timeout to avoid waiting indefinitely:

```bash
--timeout 180
```

The `openrouter/free` route does not guarantee the same model or latency on every request.

If the API returns an error, resolve it before proceeding.

### Problem: Docker container not found

If:

```bash
docker start motion-planner-vnc
```

reports that the container does not exist, the ROS Docker environment has not been created under the expected name.

Set up the required container before running the demo.

Starting Docker Desktop alone does not create `motion-planner-vnc`.

### Problem: Cannot open `http://localhost:6080`

Check that the Docker container is running:

```bash
docker ps
```

Also verify that the container's VNC service is configured and that port 6080 is available on the host.

### Problem: Missing `sampling_prior.json`

The LLM scoring or export stage may not have completed.

Check the case directory and rerun the appropriate scoring stage.

Do not launch the demo with a missing or partially generated prior.

### Problem: `Obstacle must be strictly inside boundary`

Some older C++ implementations reject obstacles that touch the map boundary at even a single point.

The updated planner described in this workflow allows boundary contact while continuing to reject geometry outside the permitted map and maintaining collision checks.

Stop the current demonstration:

```text
Ctrl + C
```

Then rerun the RViz launch command so the script can copy and build the updated source.

If the error continues, verify that the checked-out branch contains the boundary-contact fix.

You should not need to regenerate the map or call the LLM solely to resolve this issue.

### Problem: Planner displays outdated data

Confirm that the current values of `CASE_DIR` and `SAMPLING_PRIOR` point to the intended case.

Also verify that the Docker copy commands completed successfully.

The launch workflow deliberately stops if file validation or copying fails, reducing the risk of silently using old data.

---

## 13. Important Notes

### Use real LLM scores

Do not use `run_demo.sh` for this workflow if you need actual LLM-generated scoring results.

That script generates demonstration data with mock scores.

Use the scoring commands documented above instead.

### Keep map and prior data consistent

A map and its sampling prior must come from the same case.

Changing map geometry may change convex region IDs and graph connectivity, making older scores invalid.

### Avoid overwriting experiments

The HCMUT build command creates a timestamped case directory to preserve previous results.

Use a new case directory when generating a new HCMUT experiment.

### Geometry validation and safety

The satellite polygons are approximations intended for simulation and research. They are not verified physical navigation maps.

Collision checks in the C++ planner remain necessary regardless of the LLM scores.

---

## 14. Additional Documentation

For details on importing other satellite images and configuring map calibration, see:

[Satellite Image to Convex Region Graph](../../convex-region-graph/SATELLITE_README.md)

For density-decay sampling behavior, see the repository's `DENSITY_DECAY.md`.

---

## 15. Quick Start Summary

For a first-time user:

1. Clone the repository and enter `convex-region-graph`.
2. Set up the Python environment and install dependencies.
3. Configure the OpenRouter API key.
4. Prepare and start the ROS Docker environment.
5. Run the HCMUT map-generation command.
6. Generate and validate LLM region scores.
7. Copy the resulting map and sampling prior into Docker.
8. Launch RViz and open `http://localhost:6080`.

For users who already have the generated HCMUT files, **skip the map-generation and LLM-scoring steps** and launch the pre-generated case directly.

**Expected result:** The selected map, convex-region boundaries, start/goal positions, and sampling-based planner results are displayed in RViz, while detailed planner results are printed in the Terminal.
