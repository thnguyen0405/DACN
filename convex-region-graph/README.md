# Graph of Convex Regions (2D)

Module này xây dựng **directed Graph of Convex Regions (GCR)** từ các convex polygon 2D và cung cấp hai pipeline LLM-guidance cho sampling-based motion planning.

## 1. Yêu cầu

Phần Python chỉ cần **Python 3** và Python standard library, không cần cài package ngoài.

Kiểm tra trước:

```bash
python3 --version
```

> Trên macOS/zsh, hãy dùng `python3`, không dùng `python`. Nếu Terminal báo `zsh: command not found: python` thì đó là bình thường trên nhiều bản macOS mới.

## 2. Chạy nhanh

### Trường hợp A — đang đứng ở thư mục gốc repo `Motion_Planner`

```bash
cd convex-region-graph
python3 build_graph.py example_regions.json --output graph.json --svg graph.svg
```

### Trường hợp B — Terminal của bạn đã ở `convex-region-graph`

Không chạy `cd convex-region-graph` lần nữa. Chỉ chạy:

```bash
python3 build_graph.py example_regions.json --output graph.json --svg graph.svg
```

Nếu chạy thành công, chương trình sẽ tạo/cập nhật:

```text
graph.json
graph.svg
```

Mở `graph.svg` bằng trình duyệt để xem các convex region và graph.

## 3. Định dạng input

`example_regions.json` có dạng:

```json
{
  "regions": [
    {
      "id": "Q1",
      "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]
    },
    {
      "id": "Q2",
      "polygon": [[2, 0], [4, 0], [4, 2], [2, 2]]
    }
  ]
}
```

Yêu cầu:

- mỗi region có ID duy nhất;
- polygon có ít nhất 3 điểm;
- polygon phải convex;
- các điểm có thể theo chiều kim đồng hồ hoặc ngược chiều kim đồng hồ;
- không cần lặp lại điểm đầu ở cuối polygon.

## 4. Quy tắc tạo GCR hiện tại

Mỗi convex region là một vertex.

Hai region chỉ được nối khi boundary của chúng có một trong hai quan hệ:

- `shared_edge`: chung một đoạn biên có chiều dài dương;
- `point_contact`: chạm nhau tại một điểm.

**Positive-area overlap không tạo graph edge.**

Mỗi geometric connection sinh hai directed edges:

```text
A -> B
B -> A
```

`graph.json` chỉ chứa directed graph; không còn trường `undirected_edges`.

Output chính:

```json
{
  "directed": true,
  "vertices": [],
  "directed_edges": [],
  "connected_components": [],
  "connection_count": 0
}
```

Trong đó:

- `vertices`: ID, centroid và polygon của mỗi region;
- `directed_edges`: các cạnh có hướng hợp lệ;
- `connected_components`: weakly connected components của GCR;
- `connection_count`: số cặp region được nối hình học; mỗi connection tương ứng 2 directed edges.

## 5. Chạy test

Khi đang ở thư mục `convex-region-graph`:

```bash
python3 -m unittest discover -v
```

Hoặc chỉ test graph builder:

```bash
python3 -m unittest -v test_build_graph.py
```

## 6. Pipeline chính — LLM region prior

Đây là pipeline phù hợp nhất với hướng **sampling in LLM-inferred critical convex regions**:

```text
graph.json + start/goal
        |
        v
llm_region_prior.py
        |
        v
region_prior.json
        |
        v
export_sampling_prior.py
        |
        v
sampling_prior.json
        |
        v
C++ BiasSampler / RRT-family planners
```

### 6.1 Chạy offline bằng mock response

Không cần API key:

```bash
python3 llm_region_prior.py graph.json \
  --start C0 \
  --goal C6 \
  --response examples/mock_region_prior.json \
  --output outputs/region_prior.json
```

Sau đó export file cho C++:

```bash
python3 export_sampling_prior.py \
  --graph graph.json \
  --prior outputs/region_prior.json \
  --output outputs/sampling_prior.json
```

### 6.2 Chạy bằng OpenRouter

Tạo `.env` từ file mẫu:

```bash
cp .env.example .env
```

Điền:

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TEMPERATURE=0
```

Sau đó:

```bash
python3 llm_region_prior.py graph.json \
  --start C0 \
  --goal C6 \
  --provider openrouter \
  --output outputs/region_prior.json
```

Rồi export:

```bash
python3 export_sampling_prior.py \
  --graph graph.json \
  --prior outputs/region_prior.json \
  --output outputs/sampling_prior.json
```

`sampling_prior.json` có dạng:

```json
{
  "start_region": "C0",
  "goal_region": "C6",
  "regions": [
    {
      "id": "C0",
      "score": 0.7,
      "polygon": [[0, 4], [3, 4], [4, 7], [0, 7]]
    }
  ]
}
```

Score được C++ sampler dùng làm trọng số xác suất chọn region; score không phải path cost.

## 7. Pipeline thay thế — LLM edge weights + Dijkstra

Pipeline này chấm cost cho từng directed edge rồi chạy Dijkstra:

```text
graph.json + start/goal
        |
        v
llm_planner.py
        |
        v
LLM edge costs
        |
        v
Dijkstra
        |
        v
route.json
        |
        v
export_sampling_corridor.py
        |
        v
sampling_corridor.json
```

### 7.1 Chạy bằng OpenRouter

```bash
python3 llm_planner.py graph.json \
  --start C0 \
  --goal C6 \
  --provider openrouter \
  --weights-output outputs/llm_weights.json \
  --route-output outputs/route.json \
  --svg-output outputs/route.svg
```

### 7.2 Chạy offline bằng saved/mock weights

```bash
python3 llm_planner.py graph.json \
  --start C0 \
  --goal C6 \
  --weights examples/mock_llm_weights.json \
  --route-output outputs/route.json \
  --svg-output outputs/route.svg
```

Export corridor:

```bash
python3 export_sampling_corridor.py \
  --graph graph.json \
  --route outputs/route.json \
  --output outputs/sampling_corridor.json
```

## 8. Thứ tự chạy đề xuất để kiểm tra toàn bộ phần Python

Đang ở `convex-region-graph`:

```bash
# 1. Build graph
python3 build_graph.py example_regions.json --output graph.json --svg graph.svg

# 2. Run tests
python3 -m unittest discover -v

# 3. Region-prior pipeline offline
python3 llm_region_prior.py graph.json \
  --start C0 --goal C6 \
  --response examples/mock_region_prior.json \
  --output outputs/region_prior.json

python3 export_sampling_prior.py \
  --graph graph.json \
  --prior outputs/region_prior.json \
  --output outputs/sampling_prior.json

# 4. Edge-weight pipeline offline
python3 llm_planner.py graph.json \
  --start C0 --goal C6 \
  --weights examples/mock_llm_weights.json \
  --route-output outputs/route.json \
  --svg-output outputs/route.svg

python3 export_sampling_corridor.py \
  --graph graph.json \
  --route outputs/route.json \
  --output outputs/sampling_corridor.json
```

## 9. Lỗi thường gặp

### `zsh: command not found: python`

Dùng:

```bash
python3 ...
```

thay cho:

```bash
python ...
```

### `cd: no such file or directory: convex-region-graph`

Kiểm tra thư mục hiện tại:

```bash
pwd
```

Nếu prompt đã kết thúc bằng `convex-region-graph %` thì bạn đã ở đúng thư mục và không cần `cd convex-region-graph` nữa.

### Kiểm tra file có tồn tại

```bash
ls
```

Bạn phải thấy ít nhất:

```text
build_graph.py
example_regions.json
llm_planner.py
llm_region_prior.py
```

### OpenRouter API lỗi

Có thể test toàn bộ logic mà không gọi API bằng `--response` hoặc `--weights` như các ví dụ offline ở trên.

## 10. Tích hợp ACD/VCC

Chỉ cần chuyển output của convex decomposition thành schema:

```json
{
  "regions": [
    {"id": "C0", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}
  ]
}
```

Sau đó `build_graph.py` không phụ thuộc thuật toán decomposition cụ thể.
