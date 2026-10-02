# Kiến trúc đã triển khai

## Toàn pipeline

```mermaid
flowchart LR
  M[Map JSON] --> A[ACD convex regions]
  A --> G[Safe-portal directed GCR + descriptors]
  G --> S{Scoring mode}
  S -->|offline mock| V[Strict validation]
  S -->|real OpenAI/OpenRouter| V
  S -->|deterministic heuristic| V
  V --> D[Dijkstra minimum edge cost]
  D --> Q[Ordered region sequence]
  Q --> X[Sequence strategy JSON]
  G --> P[Region-prior JSON]
  X --> R[Six RRT-family planners]
  P --> R
  M --> C[Exact state/segment collision]
  C --> R
  R --> O[Metrics + paths]
  O --> Z[RViz]
```

## LLM scoring

```mermaid
flowchart TD
  G[Validated real graph data] --> I[gcr-llm-input/v2]
  I --> L[Configured provider; no automatic paid fallback]
  L --> J[JSON region_scores + edge_costs + reasons]
  J --> V{Validate IDs, topology, finite ranges, duplicates}
  V -->|invalid| E[Fail with explicit error]
  V -->|missing field| H[Neutral region / deterministic geometric edge fallback]
  V --> D[Dijkstra]
  H --> D
```

## Sequence thành sampling

```mermaid
flowchart TD
  Q[C0,C6,C7,... in preserved order] --> B{Random mixture}
  B -->|default 80% guided| G{Guided draw}
  B -->|default 20%| U[Uniform global workspace sample]
  G -->|default 20% of guided| P[Sample consecutive safe portal]
  G -->|otherwise| R[Choose sequence region by score; uniform point in polygon]
  P --> K[Normal RRT state/segment collision checks]
  R --> K
  U --> K
  K --> T[Tree expansion/rewiring/connection]
```

Sequence chỉ thay đổi proposal distribution. Dijkstra success không được dùng làm RRT success; final path vẫn phải có đúng start/goal và mọi segment phải qua `OccMap::checkSegment`.

## Input/output module

| Module | Input | Output |
|---|---|---|
| `build_graph.py` | map hoặc convex regions JSON | directed safe graph, descriptors, SVG |
| `llm_region_planner.py` | graph + mock/real/heuristic mode | validated plan, route, sampling prior, SVG |
| `scoring.py` | validated graph/start/goal | deterministic scores/costs with contributions |
| `export_sampling_corridor.py` | graph + validated plan/prior | ordered sequence-guided strategy |
| `convex_corridor.h` | prior/strategy JSON | strict C++ structs |
| `BiasSampler` | selected guidance mode | candidate sample only |
| `OccMap/MapGeometry2D` | map + candidate state/segment | exact valid/invalid decision |
| RRT/RRT*/RRT#/BRRT/BRRT*/Informed RRT* | samples + collision oracle | tree, path, real metrics |
| `benchmark.py` | same inputs/budget/seeds | per-run JSON/CSV + aggregate statistics |

## Point robot và obstacle inflation

Planner dùng configuration space: robot được coi là một reference point; forbidden set là obstacle giãn ra và workspace co vào một khoảng `robot_radius + safety_margin`. Code không dựng polygon offset mới mà kiểm tra chính xác tương đương bằng khoảng cách point/segment tới obstacle và boundary. Vì vậy không inflation hai lần. Python dùng cùng tổng clearance để kiểm tra start/goal và trim portal; C++ dùng tổng đó cho mọi state/segment. Sample có thể rơi gần obstacle nhưng sẽ bị collision checker loại, không được thêm vào tree.

