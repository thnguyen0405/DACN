# Chạy demo

## 1. Chạy nhanh toàn bộ pipeline Python

Từ thư mục gốc repo:

```bash
cd convex-region-graph
bash run_demo.sh
```

Mở kết quả SVG trên macOS:

```bash
open graph.svg
open outputs/llm_route.svg
```

Trên Linux:

```bash
xdg-open graph.svg
xdg-open outputs/llm_route.svg
```

## 2. Chạy từng bước

### Map -> ACD -> Convex Regions -> GCR

```bash
cd convex-region-graph

python3 build_graph.py example_map.json \
  --regions-output convex_regions.json \
  --output graph.json \
  --svg graph.svg
```

### LLM prior -> Dijkstra route -> SVG

```bash
python3 llm_region_planner.py graph.json \
  --response examples/mock_llm_region_prior.json \
  --svg outputs/llm_route.svg \
  --sampling-prior-output outputs/sampling_prior.json
```

### Mở kết quả

macOS:

```bash
open graph.svg
open outputs/llm_route.svg
```

Linux:

```bash
xdg-open graph.svg
xdg-open outputs/llm_route.svg
```

## 3. Chạy test

```bash
python3 -m unittest -v test_build_graph.py test_llm_region_planner.py
```

## 4. Chạy demo RRT trong noVNC / RViz

### Build ROS workspace

```bash
cd ../sampling-based-path-finding-main
catkin_make
source devel/setup.bash
```

### Terminal 1

```bash
source devel/setup.bash
roslaunch path_finder rviz.launch
```

### Terminal 2

```bash
source devel/setup.bash

roslaunch path_finder test_planners.launch \
  guidance_mode:=region_prior \
  sampling_prior_file:=$(realpath ../convex-region-graph/outputs/sampling_prior.json)
```
