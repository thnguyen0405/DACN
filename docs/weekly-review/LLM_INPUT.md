# Input thực tế gửi cho LLM

`llm_weight_provider.graph_prompt_data()` và `llm_region_planner.compact_llm_input()` dùng chung schema `gcr-llm-input/v2`. Không gửi raster map hay polygon obstacle thô; model chỉ nhận dữ liệu đã đo được từ map/GCR.

## Schema

| Field | Kiểu | Ý nghĩa |
|---|---|---|
| `start.coordinates`, `goal.coordinates` | `[x,y]` hoặc `null` | Tọa độ thật trong frame `map`, đơn vị m |
| `start.region_id`, `goal.region_id` | string | Region chứa start/goal, được code xác định |
| `robot.radius`, `safety_margin`, `required_clearance` | number hoặc `null` | `required_clearance = radius + margin` |
| `regions[]` | array | Chỉ các vertex có thật trong graph |
| `regions[].centroid/area/diameter` | number(s) | Hình học vùng |
| `aspect_ratio`, `compactness` | number hoặc `null` | Shape descriptors; định nghĩa trong `descriptor_metadata` |
| `mean_clearance`, `centroid_clearance` | number hoặc `null` | Khoảng cách tới obstacle hoặc exterior workspace |
| `degree`, `safe_degree` | number hoặc `null` | Số neighbor hình học / số neighbor còn traversable |
| `conductance`, `safe_conductance` | number hoặc `null` | Tổng portal width / perimeter |
| `directed_edges[]` | array | Toàn bộ và chỉ các directed edge hợp lệ |
| `portal`, `safe_portal` | hai endpoint hoặc `null` | Biên chung và phần còn lại sau trimming clearance |
| `portal_width`, `safe_portal_width` | number hoặc `null` | Độ rộng portal trước/sau trimming |
| `traversability`, `safe_traversability` | number hoặc `null` | Heuristic width × min(mean clearance), không phải safety proof |

## Ví dụ trích trực tiếp từ demo

Đây là excerpt từ `convex-region-graph/graph.json` sau khi chạy `build_graph.py`; các số không được tạo để minh họa:

```json
{
  "schema": "gcr-llm-input/v2",
  "start": {"coordinates": [1.0, 1.0], "region_id": "C0"},
  "goal": {"coordinates": [15.0, 9.0], "region_id": "C14"},
  "robot": {
    "radius": 0.22,
    "safety_margin": 0.08,
    "required_clearance": 0.3,
    "model": "point in configuration space; obstacles/workspace exterior expanded by required_clearance"
  },
  "regions": [{
    "id": "C0",
    "centroid": [1.33333333, 4.66666667],
    "area": 20.0,
    "diameter": 10.0,
    "aspect_ratio": 4.8470210457313,
    "compactness": 2.080725868566783,
    "mean_clearance": 0.8790136330424272,
    "centroid_clearance": 1.33333333,
    "degree": 2,
    "safe_degree": 2
  }],
  "directed_edges": [{
    "source": "C0",
    "target": "C6",
    "relation": "safe_portal",
    "portal": [[4.0, 4.0], [0.0, 10.0]],
    "safe_portal": [[3.83358994, 4.24961509], [0.16641006, 9.75038491]],
    "portal_width": 7.21110255,
    "safe_portal_width": 6.61110255,
    "traversability": 6.338657450717011,
    "safe_traversability": 5.811249270891555
  }]
}
```

Payload thật chứa đủ 15 regions và 34 directed edges; excerpt chỉ rút gọn để đọc được.

## Điều model không được tự suy diễn

- Không tạo region, edge, portal, obstacle, corner angle hay clearance chưa có.
- `null` nghĩa là unknown, không phải 0.
- Mean clearance không phải minimum clearance và traversability không chứng minh collision-free.
- Region score không phải success probability. Edge cost không phải path length hình học.
- Sequence không phải trajectory; RRT vẫn tự tạo cây và kiểm tra mọi state/segment.
- Mock JSON là dữ liệu offline cố định, không phải AI reasoning. Repo chưa có fine-tuned model.

