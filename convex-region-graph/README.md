# Map -> ACD -> Graph of Convex Regions -> LLM-guided sampling

Thư mục này chứa pipeline 2D hoàn chỉnh dùng cho demo:

```text
map + obstacles + robot clearance
        |
        v
ACD-style decomposition
        |
        v
convex regions
        |
        v
safe-portal Graph of Convex Regions
        |
        +-----------------------------+
        |                             |
        v                             v
LLM region prior                 LLM edge preference
        |                             |
        |                         Dijkstra
        |                             |
        +-------------+---------------+
                      |
                      v
             sampling guidance
                      |
                      v
              RRT-family planner
```

## 1. Điểm mới

Bản hiện tại không còn bắt đầu từ `example_regions.json` bắt buộc nữa.

`build_graph.py` nhận trực tiếp một map gồm:

- `boundary`: biên ngoài của không gian làm việc;
- `obstacles`: các polygon vật cản;
- `robot_radius` và `safety_margin`;
- `start`, `goal`.

Từ đó chương trình:

1. nối các hole/obstacle với boundary bằng visibility bridges;
2. triangulate free space bằng ear clipping;
3. greedy-merge các tam giác kề nhau khi hợp vẫn convex;
4. tạo các convex regions;
5. tìm shared boundary portal giữa các region;
6. co portal theo `robot_radius + safety_margin`;
7. chỉ giữ portal còn đủ rộng;
8. sinh 2 directed edges cho mỗi safe portal;
9. tìm connected components;
10. xuất SVG trực quan hóa toàn bộ `Input map -> ACD convex regions -> Graph`.

`point_contact` không tạo edge. Positive-area overlap cũng không tạo edge.

## 2. Chạy nhanh toàn bộ demo

Đang ở thư mục `convex-region-graph`:

```bash
bash run_demo.sh
```

Hoặc chạy từng bước.

### Bước 1 - map -> convex regions -> GCR

```bash
python3 build_graph.py example_map.json \
  --regions-output convex_regions.json \
  --output graph.json \
  --svg graph.svg
```

Kết quả:

- `convex_regions.json`: dữ liệu convex regions trung gian;
- `graph.json`: GCR + safe portals + start/goal metadata;
- `graph.svg`: hình 3 panel giống demo: **Input map | ACD convex regions | Graph**.

Mở:

```bash
open graph.svg
```

Trên Linux:

```bash
xdg-open graph.svg
```

### Bước 2 - LLM/mock prior -> route -> SVG

Demo offline, không cần API key:

```bash
python3 llm_region_planner.py graph.json \
  --response examples/mock_llm_region_prior.json \
  --svg outputs/llm_route.svg \
  --sampling-prior-output outputs/sampling_prior.json
```

Kết quả nhìn thấy:

- `outputs/llm_route.svg`: vùng được tô theo prior, xác suất P của từng region và route Dijkstra được tô đỏ.

Không còn sinh các file raw LLM JSON như:

- `llm_weights.json`
- `region_prior.json`
- `route.json`
- `llm_plan.json`
- `llm_response.json`

File JSON duy nhất còn cần cho C++ là:

- `outputs/sampling_prior.json`

Đây là **interface nội bộ cho BiasSampler/RRT**, không phải raw output của LLM.

## 3. LLM nhận input gì?

Planner chỉ gửi dữ liệu đã được kiểm tra từ graph:

```text
start_region
goal_region
regions:
  - id
  - centroid
  - area
safe_portals:
  - source
  - target
  - safe_portal_width
  - required_clearance
```

LLM không được tạo region hoặc edge mới.

Model có thể trả:

- `region_scores`: score cao -> region đáng lấy mẫu hơn;
- `edge_costs`: cost thấp -> transition được ưu tiên hơn.

Nếu edge cost bị thiếu, code suy ra từ region scores.

Prior cuối được tính bằng softmax và trộn thêm một phần uniform exploration, nên mọi region vẫn có xác suất khác 0.

Route được chọn bằng Dijkstra trên các safe portals có thật.

## 4. Chạy model thật

Tạo `.env`:

```dotenv
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

Sau đó:

```bash
python3 llm_region_planner.py graph.json \
  --provider openai \
  --svg outputs/llm_route.svg \
  --sampling-prior-output outputs/sampling_prior.json
```

Raw response không được lưu ra JSON mặc định.

## 5. Map input

Ví dụ:

```json
{
  "map": {
    "boundary": [[0,0],[16,0],[16,10],[0,10]],
    "robot_radius": 0.22,
    "safety_margin": 0.08,
    "start": [1,1],
    "goal": [15,9],
    "obstacles": [
      [[2,2],[5,1.5],[4,4]],
      [[7,1],[9,1.5],[10,3.5],[8.5,4.5],[6.5,3]],
      [[12,5],[15,5],[15,8],[13.5,8],[13.5,6.5],[12,6.5]]
    ]
  }
}
```

`required_clearance = robot_radius + safety_margin`.

Start và goal phải nằm trong free space và có clearance đủ lớn.

## 6. Tương thích input convex regions cũ

Vẫn chạy được:

```bash
python3 build_graph.py example_regions.json --output graph.json --svg graph.svg
```

Khi input chứa `regions`, chương trình bỏ qua bước map decomposition.

## 7. Chạy test

```bash
python3 -m unittest -v test_build_graph.py test_llm_region_planner.py
```

Test bao phủ:

- ACD/decomposition giữ diện tích;
- convex output;
- obstacle polygons;
- safe portal;
- robot clearance;
- loại point contact;
- loại overlap;
- start/goal mapping;
- LLM topology validation;
- prior khác 0;
- Dijkstra route.

## 8. Chạy lại demo RRT trong noVNC/RViz

Sau bước LLM, C++ dùng:

```text
convex-region-graph/outputs/sampling_prior.json
```

Build ROS workspace:

```bash
cd ../sampling-based-path-finding-main
catkin_make
source devel/setup.bash
```

Terminal 1:

```bash
roslaunch path_finder rviz.launch
```

Terminal 2:

```bash
source devel/setup.bash
roslaunch path_finder test_planners.launch \
  guidance_mode:=region_prior \
  sampling_prior_file:=$(realpath ../convex-region-graph/outputs/sampling_prior.json)
```

### Quan trọng về map ROS

`example_map.json` là map 2D dùng để chứng minh pipeline **map -> ACD -> GCR -> LLM**.

Nếu noVNC/RViz vẫn publish map cũ từ `/random_forest/all_map`, thì geometry của occupancy map ROS không giống `example_map.json`. Khi đó RRT vẫn chạy nhưng đây chưa phải một demo end-to-end trên cùng một map.

Để đánh giá đúng full pipeline, occupancy map ROS và `example_map.json` phải mô tả cùng một môi trường.

Collision checking của RRT vẫn luôn dùng occupancy map thật; GCR/LLM chỉ thay đổi phân phối lấy mẫu.

## 9. Output nên dùng khi thuyết trình

Ưu tiên hai file SVG:

```text
graph.svg
outputs/llm_route.svg
```

- `graph.svg`: chứng minh map ban đầu đã được phân rã thành convex regions và dựng graph.
- `llm_route.svg`: chứng minh LLM prior + Dijkstra route.

Không cần mở raw LLM JSON khi thuyết trình.
