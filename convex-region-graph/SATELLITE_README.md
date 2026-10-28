# Ảnh vệ tinh → hai hình tĩnh → bộ dữ liệu map → LLM

Module chạy bằng Terminal, không cần web server. Ảnh HCMUT đã có bộ polygon
vẽ theo các tòa nhà: start ở **cổng 1**, goal ở **cổng 2**.

## 1. Chạy map HCMUT

```bash
cd /Users/nguyen/BK/SEM7/DACN/DACN-main/convex-region-graph

.venv-satellite/bin/python satellite_to_graph.py build \
  --image examples/satellite/hcmut_cs1/image.png \
  --output research/data/hcmut_demo \
  --llm
```

Lệnh tự đọc `annotations.json` cạnh ảnh, kiểm tra hình học, phân rã thành vùng
lồi, tính descriptor, xây graph và đường tham chiếu, lưu hai hình, gọi LLM thật,
rồi xuất điểm cho C++. API key lấy từ `.env`; mặc định dùng `openrouter/free`.
Có thể chọn model miễn phí cụ thể bằng `--model ten-model:free`.
Mặc định dành tối đa 32768 token đầu ra và timeout 180 giây cho một request;
có thể chỉnh `--max-tokens` và `--timeout`. Khả dụng của các model miễn phí có thể thay đổi.
Module đặt `--reasoning-effort none` để ưu tiên ngân sách đầu ra cho JSON. Nếu model
báo bắt buộc suy luận (HTTP 400/422), tự thử lại một lần với `low`, giữ nguyên
model yêu cầu và ngân sách token. Có thể đặt `--reasoning-effort low` từ đầu.
Metadata lưu cả mức yêu cầu ban đầu và mức dùng sau khi thử lại.

**Chỉ cần hình và dữ liệu hình học:** bỏ `--llm`. Không tạo điểm giả.
Thư mục output phải chưa tồn tại để tránh ghi đè hoặc trộn dữ liệu giữa các lần chạy.

Bản đã tạo trong repo nằm ở `research/data/hcmut_cs1/`.

## 2. Xem kết quả

Có đúng **hai file hình**:

| File | Nội dung |
|---|---|
| `graph.svg` | Ba khung: input map → vùng lồi → graph; có thể phóng to |
| `satellite_overlay.png` | Ảnh vệ tinh gốc, polygon tòa nhà màu đỏ, biên vàng, start/goal |

Các file dữ liệu dùng chung cấu trúc với `hole`, `flappy`:

| File | Nội dung |
|---|---|
| `map.json` | Boundary, obstacles, start, goal, bán kính robot, biên an toàn |
| `regions.json` | ID và polygon của từng vùng lồi |
| `graph.json` | Đỉnh, cạnh, portal, descriptor hình học và vùng start/goal |
| `reference.json` | Đường ngắn nhất trên lưới 8 hướng với kiểm tra va chạm; không phải tối ưu liên tục |
| `import_audit.json` | Diện tích, độ phủ, chồng lấn, kết nối và trạng thái đường tham chiếu |
| `llm_prior.json` | Điểm và lý do từng vùng; chỉ có sau khi gọi LLM thành công |
| `sampling_prior.json` | Polygon + điểm vùng để C++ đọc; chỉ có sau khi chấm đủ vùng |
| `annotations.json` | Polygon và start/goal trên tọa độ pixel của ảnh gốc |
| `pipeline_status.json` | Trạng thái hình học, LLM và xuất prior |

`llm_prior.json` chứa `region_scores` để dùng với `export_sampling_prior.py`,
đồng thời có `scores` và `metadata` để dùng với các script nghiên cứu hiện có.
Phản hồi và thông tin lời gọi LLM nằm trong `llm_calls/`.
Nếu không tìm thấy đường trên lưới, `reference.json` là `null` và audit ghi rõ;
điều đó chưa đủ để kết luận không có đường trong không gian liên tục.

## 3. Gọi LLM riêng hoặc thử lại khi API lỗi

Không cần chạy lại phân rã:

```bash
.venv-satellite/bin/python satellite_to_graph.py score \
  --case research/data/hcmut_cs1
```

Lệnh dùng start/goal trong graph, không cần nhập ID bằng tay. Nếu API lỗi hoặc
thiếu điểm vùng, giữ kết quả hình học và không xuất sampling prior bằng điểm thay thế.
Nếu case đã có prior thành công, tạo một case output mới khi muốn chấm lại.

## 4. Nạp một ảnh vệ tinh khác

Ảnh RGB đơn lẻ chưa đủ để xác định chính xác ranh giới tòa nhà, đường đi và tỷ lệ.
Module nhận **ảnh + polygon đã kiểm tra**, hoặc chuyển **mask nhị phân** thành polygon.
Chưa có mô hình tự động nhận diện tòa nhà từ ảnh vệ tinh.

Tạo cấu hình cho ảnh mới:

```bash
.venv-satellite/bin/python satellite_to_graph.py init \
  --image /duong/dan/map_moi.png \
  --output /duong/dan/annotations.json
```

Điền trong JSON:

- `geometry_px.boundary`: các đỉnh ranh giới map.
- `geometry_px.obstacles`: polygon tòa nhà/vật cản.
- `geometry_px.walkable`: tùy chọn, giới hạn vào vùng thực sự cho phép đi.
- `planning_px.start`, `planning_px.goal`: tọa độ `[x, y]` pixel.
- `review.geometry_confirmed`: đặt `true` sau khi kiểm tra hình học.

Tọa độ pixel lấy gốc **trên trái**, x sang phải, y xuống dưới; đúng kích thước ảnh gốc
sau EXIF. Không dùng lại tọa độ từ ảnh đã resize hoặc ảnh khác.

Nếu đã có mask cùng kích thước, trắng = đi được, đen = cấm:

```bash
.venv-satellite/bin/python satellite_to_graph.py init \
  --image /duong/dan/map_moi.png \
  --mask /duong/dan/free_space_mask.png \
  --start 100 200 --goal 800 300 \
  --output /duong/dan/annotations.json
```

Kiểm tra polygon và xác nhận `review.geometry_confirmed`, sau đó chạy cùng pipeline:

```bash
.venv-satellite/bin/python satellite_to_graph.py build \
  --image /duong/dan/map_moi.png \
  --annotations /duong/dan/annotations.json \
  --output research/data/map_moi \
  --llm
```

## 5. Đơn vị và giới hạn của map HCMUT

Mặc định `--scale-mode simulation --long-side 20 --radius 0.1 --margin 0.05`:
chuẩn hóa cạnh dài thành **20 m mô phỏng**, giống cách `research/import_dataset.py`
nhập các map nghiên cứu. Đây **không phải kích thước thực tế của trường**.
Tọa độ được đổi sang gốc dưới trái của bounding box ranh giới và đảo trục y.
Các descriptor được tính từ polygon đã chuẩn hóa; sai số vẽ polygon vẫn tồn tại.

Khi có khoảng cách thực tế đáng tin cậy, điền `calibration.points_px`, `distance_m`,
`source`, `basis` rồi dùng `--scale-mode calibrated`. Với `basis` là
`map_measurement` hoặc `assumed`, cần thêm `--allow-estimated-scale`; metadata vẫn
đánh dấu ước lượng. Có thể điều chỉnh `--grid-step` cho map lớn hơn.

HCMUT hiện có 28 polygon tòa nhà vẽ xấp xỉ, chưa xác minh thực địa. Mô hình xem
phần còn lại trong boundary là vùng trống, kể cả sân/cây xanh; chưa mô hình hóa
hàng rào, bậc thang, xe và quy định đi lại. Giới hạn map ở phần khuôn viên nhìn
thấy trong ảnh. Start/goal được giữ nguyên, không tự chuyển sang vị trí khác.

## 6. Dùng tiếp với C++/RViz khi cần

Sau khi `pipeline_status.json` báo `sampling_prior: complete`, dùng cùng script
với các map cũ:

```bash
CASE_DIR=research/data/hcmut_cs1

docker start motion-planner-vnc && \
docker exec motion-planner-vnc mkdir -p /tmp/demo-case && \
docker cp "$CASE_DIR/map.json" motion-planner-vnc:/tmp/demo-case/map.json && \
docker cp "$CASE_DIR/sampling_prior.json" motion-planner-vnc:/tmp/demo-case/sampling_prior.json && \
ROS_DISPLAY=:1 bash ../scripts/run_container_demo.sh \
  map_file:=/tmp/demo-case/map.json \
  sampling_prior_file:=/tmp/demo-case/sampling_prior.json \
  planner:=all rviz:=true
```

Bước này tùy chọn; xuất hình và JSON không cần Docker hoặc RViz.

## Cài môi trường trên máy khác

Dùng Python 3.11 hoặc 3.12:

```bash
python3.12 -m venv .venv-satellite
.venv-satellite/bin/python -m pip install -r satellite_requirements.txt
```
