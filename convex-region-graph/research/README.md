# Nghiên cứu GCR: điểm vùng, corridor và RRT

Bộ công cụ thí nghiệm cho DACN-main. Đây là **RRT Python độc lập**, chưa tích hợp cập nhật điểm động vào sáu planner ROS/C++. Các kết quả không đại diện cho benchmark ROS.

## Cài đặt và tái lập

Chạy từ thư mục gốc DACN-main, Python 3.10 trở lên:

```sh
python3 -m venv .venv-research
.venv-research/bin/python -m pip install -r convex-region-graph/research/requirements.txt
.venv-research/bin/python convex-region-graph/research/import_dataset.py /duong/dan/GCR-Dataset --output convex-region-graph/research/data --grid-step 0.1
```

`.poly` là nguồn hình học. Importer đọc thứ tự đỉnh theo POLY_FORMAT, chuyển đồng nhất cạnh dài nhất thành 20 m, robot_radius=0.1 m, safety_margin=0.05 m. Đây là đơn vị mô phỏng giả định vì dataset chưa ghi kích thước vật lý. Có thể đổi `--long-side`, `--radius`, `--margin`. Start/goal là hai điểm xa nhau trong thành phần liên thông lớn nhất của lưới an toàn. Mọi đoạn cạnh đều kiểm tra va chạm hình học. Metadata lưu phép đổi đơn vị và SHA256 nguồn.

Đồ thị gốc chứa cạnh shared_length=0 và các cost chưa có công thức nguồn; không dùng trực tiếp như đồ thị portal an toàn. Importer dựng lại bằng code DACN. Nếu ACD cũ thất bại trên polygon hợp lệ, dùng constrained Delaunay của Shapely rồi ghép vùng lồi bằng hàm của DACN, kiểm tra độ phủ và chồng lấn. Cần Shapely >=2.1 và GEOS >=3.10 để dùng nhánh này.

Với mỗi map, ví dụ hole:

```sh
.venv-research/bin/python convex-region-graph/research/run_study.py convex-region-graph/research/data/hole --repeats 10 --iterations 2500
```

Không có `llm_prior.json` thì chạy none, hai baseline vùng và heuristic. Có file thì thêm LLM và decay 5%, 15%, 30%. Chạy lại ghi đè runs.json và analysis.json; sao lưu nếu cần giữ các cohort.

Lấy điểm thật từ OpenRouter (gửi graph/prompt tới dịch vụ, chỉ khi người vận hành cho phép):

```sh
.venv-research/bin/python convex-region-graph/research/llm_study.py convex-region-graph/research/data/hole --env-file convex-region-graph/.env --model nvidia/nemotron-3-super-120b-a12b:free
```

Model có thể không còn khả dụng sau thời điểm thí nghiệm. Script chỉ chấp nhận model `:free` hoặc `openrouter/free`, vẫn lưu cost mà provider báo. Không commit `.env` hoặc response chẩn đoán thô. Khi model lỗi, không tự biến heuristic thành kết quả LLM. Một prior đã lưu được dùng cho toàn bộ các seed; thí nghiệm này chưa đo biến thiên giữa nhiều lần LLM suy luận.

Hai pilot cập nhật động (seed 42, tối đa 2 lần gọi thêm, dùng model từ prior):

```sh
.venv-research/bin/python convex-region-graph/research/run_dynamic.py convex-region-graph/research/data/hole --env-file convex-region-graph/.env --trigger new_region --max-calls 2
.venv-research/bin/python convex-region-graph/research/run_dynamic.py convex-region-graph/research/data/hole --env-file convex-region-graph/.env --trigger interval --max-calls 2
```

`new_region`: có node được chấp nhận trong vùng chưa được khám phá; vùng start đã được đánh dấu. Sự kiện chờ tới khi đủ cooldown 100 bước, nhiều sự kiện gộp thành một lần cập nhật. `interval`: mỗi 250 bước kể cả bước thất bại. Giới hạn tính cả lần gọi lỗi; lỗi giữ nguyên prior. Hiện lời gọi đồng bộ làm planner chờ API. Log phân biệt thời gian planner và thời gian API.

Giảm điểm: sau mỗi 20 node **được thêm thành công** trong vùng i, `s_i <- max(min(0.05, s_i_initial), (1-rate)*s_i)`. Vùng khác giữ nguyên. Khi có prior mới, áp lại mức decay theo tổng số node đã thêm. Điểm 0 giữ 0; floor không bảo đảm mọi vùng luôn được lấy mẫu. Tập dữ liệu thử nghiệm có prior dương.

Kiểm tra ngân sách lớn hơn được lưu riêng:

```sh
.venv-research/bin/python convex-region-graph/research/run_supplement.py convex-region-graph/research/data/narrow --iterations 10000 --repeats 5
PYTHONPATH=convex-region-graph .venv-research/bin/python -m unittest discover -s convex-region-graph/research/tests -v
PYTHONPATH=convex-region-graph .venv-research/bin/python -m unittest discover -s convex-region-graph/tests -v
```

## Đọc kết quả đúng

- `none`: lấy mẫu đều trong bounding box rồi kiểm tra hình học; LLM/heuristic chọn vùng theo `score/sum(scores)` rồi lấy mẫu đều theo diện tích vùng. Vì vậy khác biệt còn gồm hiệu ứng phân rã/lấy mẫu theo vùng; `region_uniform` cho mọi vùng cùng điểm và `region_area` cho điểm tỷ lệ diện tích để kiểm tra ảnh hưởng cách lấy mẫu. Cần nhiều lần gọi LLM độc lập để đánh giá độ ổn định của chính model.
- Cùng seed chỉ là cùng khởi tạo RNG; các chế độ tiêu thụ số ngẫu nhiên khác nhau. Mỗi lần chạy đủ ngân sách, giữ đường kết nối goal tốt nhất trong cây RRT không rewiring. Bán kính nối goal 1.4 m, bước mở rộng 0.7 m, không goal bias.
- Điểm trong [0,1] là mức ưu tiên tương đối, không phải xác suất thành công hay chứng nhận an toàn. Heuristic có trọng số cố định; LLM không bắt buộc dùng công thức đó.
- Sequence kiểm tra ID, start/goal, cạnh có hướng. Corridor là hợp các polygon trong sequence. Lưới hạn chế cả node và toàn đoạn cạnh trong corridor nhưng **không ép thứ tự đi qua vùng**. Kết quả tối ưu chỉ trên lưới 8 hướng; không chứng minh tối ưu liên tục. Lưới không tìm thấy đường không chứng minh không tồn tại đường liên tục.
- So sánh tối ưu phải dùng cùng một lưới cho toàn map và corridor. Một đường tham chiếu nằm ngoài corridor vẫn có thể có đường khác cùng độ dài ở trong corridor.
- Start/goal hoặc đoạn đường có thể nằm trên biên chung nhiều vùng; graph chọn ID đầu tiên chứa endpoint. Mapping đường chọn vùng trước đó nếu còn phù hợp, nếu không chọn ID theo thứ tự chữ. Điểm chỉ chạm biên không được tính như đã đi qua cả vùng.
- Overlap: Jaccard tập vùng đường đi; LCS chuẩn hóa chuỗi có thứ tự; tỷ lệ chiều dài nằm trong dải 0.2 m quanh đường kia (đối xứng, có trọng số chiều dài). Tập vùng có node cây dùng Jaccard riêng. Khi một bên thất bại, overlap đường = null, không gán 0%.
- Replay lịch refresh chỉ đếm sự kiện trên trace tĩnh, không phải kết quả chạy động. Pilot API thật n=1 chỉ kiểm tra tính khả thi và chi phí, không đủ kết luận thống kê.

## Dẫn chứng trong code

| Nội dung | Hàm / file |
|---|---|
| Shape, area covariance, AR, compactness | `region_descriptors.py:polygon_moments` |
| Mean clearance, conductance, traversability | `region_descriptors.py:enrich_graph` |
| Portal thu hẹp và clearance | `build_graph.py:erode_portal`, `point_clearance` |
| Heuristic vùng/cạnh, bottleneck | `scoring.py:deterministic_region_score_records`, `deterministic_edge_cost_records`, `_required_bottlenecks` |
| Xác suất chọn vùng production | `sampling-based-path-finding-main/src/path_finder/include/path_finder/sampler.h:setRegionPrior` (`std::discrete_distribution`) |
| Oracle đoạn và lưới tham chiếu | `research/geometry.py:World`, `GridReference` |
| Đánh giá sequence và đóng góp điểm | `research/scoring_audit.py` |
| Trigger, decay, cooldown, cap | `research/adaptive.py:AdaptivePrior` |
| RRT và trace các node được thêm | `research/rrt_experiment.py:run_rrt` |
| Gọi model thật, token, cost, latency | `research/llm_study.py:StudyProvider` |

Báo cáo kết quả lần chạy và hình minh họa nằm trong gói bàn giao `gcr-study`; dữ liệu map trong `research/data` đã chuyển đổi có thể chạy lại mà không cần import nguồn.
