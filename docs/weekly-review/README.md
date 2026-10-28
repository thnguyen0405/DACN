# Demo nhiều map: Ảnh vệ tinh HCMUT → Graph of Convex Regions → LLM → RViz

## Chuẩn bị

- Mở Docker Desktop, có sẵn container `motion-planner-vnc` khi chạy RViz.
- Cấu hình OpenRouter API key trong `convex-region-graph/.env`.
- Dùng Python trong `.venv-satellite` đã cài các thư viện xử lý ảnh và hình học.
- Chạy các bước trong cùng một Terminal để giữ các biến đã khai báo.
- Nếu một bước báo lỗi, xử lý trước khi tiếp tục.

Ảnh HCMUT đã có file polygon tòa nhà đi kèm. Start là **cổng 1**, goal là
**cổng 2**. Module chạy trực tiếp bằng Terminal, không cần web editor.

## Các map có sẵn

| Map | Số vùng lồi | START_REGION | GOAL_REGION |
|---|---:|---|---|
| hole | 9 | C4 | C5 |
| narrow | 16 | C4 | C0 |
| flappy | 45 | C14 | C43 |
| room | 104 | C40 | C85 |
| hcmut_cs1 | 164 | C17 | C144 |

Các ID trong bảng áp dụng cho dữ liệu hiện tại. Khi sửa polygon hoặc phân rã lại,
lấy ID từ `graph.json`, không gán cố định theo bảng.

## 1. Từ ảnh vệ tinh HCMUT, tạo map và hai hình

```bash
cd /Users/nguyen/BK/SEM7/DACN/DACN-main/convex-region-graph

PYTHON=.venv-satellite/bin/python
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

Mỗi lần chạy tạo một thư mục case mới, tránh ghi đè kết quả trước đó.
Lệnh nạp ảnh và polygon, phân rã vùng trống thành các vùng lồi, tính descriptor,
xây graph và đường tham chiếu. Bước này chưa gọi LLM.

Mở hai hình trong thư mục được in ở Terminal:

- `graph.svg`: input map → các vùng lồi → graph kết nối.
- `satellite_overlay.png`: ảnh vệ tinh với biên khuôn viên, polygon tòa nhà và start/goal.

Các file hình học đi kèm: `map.json`, `regions.json`, `graph.json`,
`reference.json`, `import_audit.json`, `annotations.json`, `pipeline_status.json`.

**Tỷ lệ:** cạnh dài được chuẩn hóa thành **20 m mô phỏng**, tương tự các map
nghiên cứu; không phải kích thước thực tế của trường. Polygon tòa nhà được vẽ
xấp xỉ từ ảnh, chưa xác minh thực địa. Mô hình hiện xem phần còn lại trong
ranh giới là vùng trống; chưa giới hạn riêng vào đường đi bộ.

## 2. Gọi LLM và xuất điểm cho C++

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem "$PYTHON" satellite_to_graph.py score \
  --case "$CASE_DIR" \
  --model openrouter/free \
  --reasoning-effort none \
  --max-tokens 32768
```

Lệnh tự lấy start/goal từ graph, gọi LLM thật, kiểm tra đủ điểm cho từng vùng và
xuất hai file:

- `llm_prior.json`: xem `region_scores` để đọc `score` và `reason` của từng vùng.
- `sampling_prior.json`: polygon + điểm vùng để C++ sử dụng.

`openrouter/free` có thể chọn model khác nhau giữa các lần gọi. Nếu endpoint
báo `Reasoning is mandatory ... cannot be disabled`, chương trình tự thử lại
một lần với `reasoning-effort low`, giữ nguyên model yêu cầu và giới hạn token.
Không cần tạo lại map. Có thể đặt `--reasoning-effort low` ngay trong lệnh trên
nếu muốn bật suy luận từ đầu. Nếu tiếp tục lỗi do hết token hoặc hạn mức API,
xử lý thông báo mới trước khi chạy RViz; không dùng điểm trả về dở dang.

Không cần gọi `export_sampling_prior.py` riêng trong nhánh HCMUT: lệnh `score`
đã thực hiện bước xuất này. Khi hoàn tất, `pipeline_status.json` ghi
`llm: complete` và `sampling_prior: complete`.

Nếu API lỗi hoặc thiếu điểm vùng, không dùng phản hồi dở dang. Có thể chạy lại
lệnh `score` khi case chưa có prior thành công. Nếu muốn chấm lại một case đã có
prior, bắt đầu từ bước 1 để tạo case mới.

## 3. Chạy đúng map đó trên RViz

Chỉ chạy sau khi bước 2 hoàn tất. Các lệnh nối bằng `&&` để dừng nếu thao tác
copy thất bại, tránh khởi chạy với dữ liệu cũ trong container.

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

Giữ Terminal mở và truy cập [http://localhost:6080](http://localhost:6080)
để xem màn hình RViz trong container. Đây là màn hình VNC, không phải web editor
xử lý ảnh vệ tinh.

Trong RViz, vào **Displays → Planning**:

- Bật **Region boundaries**, **start**, **goal**.
- Bật lần lượt các nhóm `01 RRT` đến `06 Informed RRT*`.
- Tắt bớt nhóm nếu các đường đi chồng lên nhau.

Start và goal lấy từ `map.json`: cổng 1 → cổng 2. Terminal hiển thị các dòng
`[RESULT]` chứa kết quả tìm đường. Nhấn **Control + C** để dừng demo.

Nếu gặp `Obstacle must be strictly inside boundary` với bản HCMUT, đó là
kiểm tra hình học trong bản C++ cũ: một tòa nhà chạm biên khuôn viên tại một
điểm. Bản sửa cho phép vật cản tiếp xúc biên nhưng vẫn kiểm tra không vượt
ra ngoài và giữ kiểm tra va chạm. Nhấn **Control + C**, rồi chạy lại **bước 3**;
script sẽ copy source mới và build lại. Không sửa polygon, tạo lại map hoặc
gọi lại LLM chỉ để xử lý lỗi này.

## Dùng ngay bản HCMUT đã tạo sẵn

Bản `hcmut_cs1` đã có đủ hai hình, bộ JSON và điểm LLM cho 164 vùng.
Nếu chỉ muốn mở RViz với bản này, chạy:

```bash
cd /Users/nguyen/BK/SEM7/DACN/DACN-main/convex-region-graph

PYTHON=.venv-satellite/bin/python
CASE=hcmut_cs1
CASE_DIR="research/data/$CASE"
SAMPLING_PRIOR="$CASE_DIR/sampling_prior.json"
```

Sau đó chạy **bước 3**. Không chạy lại `score` trên prior đã hoàn tất.

## Đổi sang hole, narrow, flappy hoặc room

Sau khi dừng RViz, chọn map; ví dụ `flappy`:

```bash
CASE=flappy
CASE_DIR="research/data/$CASE"
SAMPLING_PRIOR="$CASE_DIR/demo_sampling_prior.json"

"$PYTHON" - "$CASE_DIR" <<'PY'
import json
import sys
from pathlib import Path
from build_graph import svg_visualization

folder = Path(sys.argv[1])
graph = json.loads((folder / "graph.json").read_text())
geometry = json.loads((folder / "map.json").read_text())["map"]
geometry["planning"] = graph["planning"]
(folder / "graph.svg").write_text(
    svg_visualization(graph, width=1500, map_geometry=geometry),
    encoding="utf-8",
)
print("Mở:", folder / "graph.svg")
PY

START_REGION=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["planning"]["start_region"])' "$CASE_DIR/graph.json")
GOAL_REGION=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["planning"]["goal_region"])' "$CASE_DIR/graph.json")

SSL_CERT_FILE=/etc/ssl/cert.pem "$PYTHON" llm_region_prior.py \
  "$CASE_DIR/graph.json" \
  --start "$START_REGION" \
  --goal "$GOAL_REGION" \
  --provider openrouter \
  --output "$CASE_DIR/demo_prior.json" && \
"$PYTHON" export_sampling_prior.py \
  --graph "$CASE_DIR/graph.json" \
  --prior "$CASE_DIR/demo_prior.json" \
  --output "$SAMPLING_PRIOR"
```

Dòng `geometry["planning"] = graph["planning"]` cung cấp thông tin start/goal
cho hàm vẽ, tránh `KeyError: 'planning'`. Start/goal của LLM cũng được đọc tự động
từ graph, tránh nhầm ID giữa các map.

Khi xuất prior thành công, chạy lại **bước 3** với các biến vừa chọn.
Mỗi map có điểm LLM riêng; không dùng prior của map này cho map khác.

**Lưu ý:** Không chạy `run_demo.sh` trong quy trình này vì script đó tạo dữ liệu
với điểm mock. Hướng dẫn nhập ảnh vệ tinh khác và hiệu chuẩn tỷ lệ xem tại
[Module ảnh vệ tinh → graph](../../convex-region-graph/SATELLITE_README.md).
