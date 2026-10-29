# Dynamic density-based region score decay

## Vấn đề và luồng dữ liệu

`convex-region-graph/llm_region_prior.py` tạo điểm LLM theo vùng. `export_sampling_prior.py` ghép điểm với polygon thành `sampling_prior.json`; luồng `llm_region_planner.py` cũng có thể xuất file cùng schema, nhưng trường `score` ở luồng này là xác suất đã qua softmax/exploration. C++ chỉ đọc trường `score` trong file xuất và dùng trực tiếp làm trọng số cho `std::discrete_distribution`; C++ không tự dùng softmax. Giá trị nào ở file JSON chính là `base_score` bất biến trong một phiên chạy. Không thay đổi Python hoặc schema JSON.

Trước đây phân phối chọn vùng không đổi khi cây mở rộng. Khi bật decay, sampler theo dõi số node đã chèn và cập nhật trọng số sau mỗi epoch. Cây hiện có tiếp tục chạy, không gọi lại LLM.

## Công thức

Với vùng `i`, diện tích polygon `A_i > 0`, số node được gán `N_i`, mật độ `rho_i = N_i/A_i`:

```
adjusted_i = max(min_score, base_i - lambda_i * rho_i/(rho_i + rho_ref))
lambda_i   = protected_lambda nếu được bảo vệ, ngược lại lambda
P_i        = adjusted_i / sum(adjusted_j)
```

Mặc định: `rho_ref=2`, `lambda=0.4`, `protected_lambda=0.1`, `min_score=0.05`, `K=100`. Mật độ bằng 0 cho `adjusted=max(min_score, base)`. Điểm sàn chỉ áp dụng khi **bật** và đến epoch cập nhật đầu tiên; trước đó phân phối vẫn y như file JSON. Điểm gốc luôn được giữ riêng, nên không có trừ phạt tích lũy. Điểm sàn bảo đảm mỗi vùng tiếp tục có xác suất chọn dương sau khi cập nhật.

## Đếm node và bảo vệ vùng

Mỗi `addTreeNode` của RRT, RRT*, RRT#, BRRT, BRRT* thông báo sau khi node được chèn. Informed RRT* dùng class RRTStar và đi cùng nhánh đó. BRRT thông báo cả node ở cây A và mọi node connect ở cây B. Node bị từ chối trước khi chèn, goal được nối bằng đổi parent, rewiring và root ban đầu không được đếm. Node ngoài các polygon vẫn tăng bộ đếm node thêm thành công để xác định mốc K, nhưng không tăng bộ đếm vùng nào.

Nếu một node nằm trong nhiều polygon đóng, nó được gán đúng một lần cho region ID nhỏ nhất theo thứ tự từ điển, không phụ thuộc thứ tự trong JSON. Mọi vùng chứa goal thực tế đều được bảo vệ. Vùng `goal_region` từ JSON cũng được bảo vệ, cùng các ID truyền qua `density_decay_protected_region_ids`; danh sách này dành cho bottleneck đã được xác định từ dữ liệu khác. Không suy đoán bottleneck từ diện tích. Polygon không lồi, diện tích bằng 0, tọa độ không hữu hạn bị từ chối khi nạp prior. Mỗi lệnh `plan()` reset bộ đếm và phân phối về điểm gốc trước khi tìm đường.

Decay chỉ có tác dụng với `guidance_mode=region_prior` và `density_decay_enabled=true`. `none`, `corridor`, `sequence_guided` giữ ngữ nghĩa cũ. Mặc định OFF.

## Cấu hình và demo

ROS parameters trong `test_planners.launch` và `demo.launch`:

| Parameter | Mặc định | Ý nghĩa |
| --- | ---: | --- |
| `density_decay_enabled` | `false` | Bật decay |
| `density_decay_update_interval` | `100` | Số node chèn giữa các epoch |
| `density_decay_lambda` | `0.4` | Phạt thường |
| `density_decay_protected_lambda` | `0.1` | Phạt vùng bảo vệ |
| `density_decay_rho_ref` | `2.0` | Mật độ tham chiếu |
| `density_decay_min_score` | `0.05` | Điểm sàn |
| `density_decay_protected_region_ids` | `[]` | YAML list ID bảo vệ thêm |
| `density_decay_log_file` | rỗng | Đường dẫn CSV tùy chọn; bỏ trống vẫn log CSV qua ROS |

Ví dụ trên máy có ROS1/catkin và các dependencies của project:

```bash
cd sampling-based-path-finding-main
catkin_make -DCATKIN_ENABLE_TESTING=ON
catkin_make run_tests_path_finder_gtest_convex_corridor_sampler_test
source devel/setup.bash
roslaunch path_finder demo.launch planner:=rrt guidance_mode:=region_prior \
  density_decay_enabled:=true density_decay_update_interval:=100 \
  density_decay_log_file:=/tmp/density_decay_rrt.csv rviz:=false
```

Để bảo vệ thêm một vùng bottleneck đã biết, truyền `density_decay_protected_region_ids:="[region_3]"` cho `roslaunch`. ID phải có trong sampling prior. File CSV dùng chế độ append, có header một lần; nên dùng đường dẫn riêng cho từng thí nghiệm.

## So sánh Static LLM và LLM + Density Decay

Dùng cùng `map_file`, `sampling_prior_file`, `planner`, `random_seed`, `search_time`, `max_tree_node_nums` và các tham số thuật toán. Chạy hai lệnh ở hai phiên riêng:

```bash
roslaunch path_finder demo.launch planner:=rrt guidance_mode:=region_prior random_seed:=42 \
  search_time:=5.0 density_decay_enabled:=false rviz:=false
roslaunch path_finder demo.launch planner:=rrt guidance_mode:=region_prior random_seed:=42 \
  search_time:=5.0 density_decay_enabled:=true \
  density_decay_log_file:=/tmp/density_decay_rrt.csv rviz:=false
```

So sánh các dòng `[RESULT]` (thành công, thời gian, độ dài đường, số vòng lặp, số node), rồi vẽ `density`, `adjusted_score`, `probability_after` theo `nodes_added` từ CSV. Ví dụ với base `0.8`, diện tích `1`, `N=2`, `rho=2`, vùng thường được `0.8-0.4*2/(2+2)=0.6`; vùng được bảo vệ là `0.75`. Nếu cả hai ban đầu `0.8`, xác suất vùng thường sau epoch là `0.6/(0.6+0.75)≈0.4444`, trước epoch là `0.5`.

Seed cố định tái lập chuỗi mẫu trong test sampler khi chuỗi node được thêm giống nhau. Vì planner có giới hạn theo thời gian và môi trường ROS bất đồng bộ, hai lần chạy không nhất thiết đi cùng số vòng lặp tuyệt đối; so sánh thống kê nhiều lần hoặc dùng giới hạn node tương đương để báo cáo công bằng.

## File thay đổi

- `sampling-based-path-finding-main/src/path_finder/include/path_finder/sampler.h`: config, base/adjusted score, đếm node, công thức và phân phối, callback log.
- Năm header `rrt.h`, `rrt_star.h`, `rrt_sharp.h`, `brrt.h`, `brrt_star.h`: reset đầu `plan()` và thông báo trong `addTreeNode`.
- `sampling-based-path-finding-main/src/path_finder/src/test_planner.cpp`: đọc ROS params, xác thực vùng bảo vệ, CSV/ROS logging.
- `sampling-based-path-finding-main/src/path_finder/launch/test_planners.launch` và `demo.launch`: truyền tham số.
- `sampling-based-path-finding-main/src/path_finder/test/convex_corridor_sampler_test.cpp`: unit tests.

## Hạn chế và tình trạng kiểm chứng

Decay dựa trên mật độ node trong polygon 2D; không tính độ phủ hình học của cạnh, các đoạn trong vùng hay thể tích 3D. Polygon chồng lấn được phân xử bằng ID nhỏ nhất, có thể làm mật độ vùng khác thấp hơn trực giác. CSV được ghi từng dòng tại epoch nên bật file log làm tăng I/O; bỏ trống đường dẫn nếu chỉ cần ROS log. Việc nhận diện bottleneck tự động chưa có nguồn dữ liệu đáng tin cậy, nên cần cấu hình ID rõ ràng. Kết quả build/test thực chạy của môi trường hiện tại được báo cáo trong phần bàn giao, không suy ra chỉ từ mã.
