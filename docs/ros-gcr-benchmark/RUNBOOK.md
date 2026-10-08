# Chạy lại benchmark ROS GCR

Benchmark dùng C++ production trong DACN-main và các prior LLM đã lưu. Không cần gửi request API mới. Các file code nguồn đã dùng có SHA256 trong source_hashes.json; inputs/ chứa map, graph, prior cho C++ và sequence_strategy của cả bốn map.

## Chuẩn bị container

Container cần ROS Noetic và các dependency đã có trong motion-planner-vnc. Chép thư mục sampling-based-path-finding-main/src của DACN-main vào một workspace riêng trong container. Ví dụ gốc /tmp/dacn-gcr-benchmark-20261008 có cấu trúc:

```
sampling-based-path-finding-main/src/
inputs/hole/ ... flappy/ ... narrow/ ... room/
run_ros_benchmark.py
benchmark.py
```

Hai file Python điều phối có trong scripts/ của gói bàn giao. Build rồi chạy test:

```sh
source /opt/ros/noetic/setup.bash
cd /tmp/dacn-gcr-benchmark-20261008/sampling-based-path-finding-main
catkin_make -j2
catkin_make run_tests_path_finder -j2
source devel/setup.bash
```

## Chạy master riêng và benchmark

Terminal thứ nhất trong container:

```sh
source /opt/ros/noetic/setup.bash
roscore -p 11339
```

Terminal thứ hai trong container:

```sh
source /opt/ros/noetic/setup.bash
source /tmp/dacn-gcr-benchmark-20261008/sampling-based-path-finding-main/devel/setup.bash
export ROS_MASTER_URI=http://localhost:11339
export ROS_HOSTNAME=localhost
python3 /tmp/dacn-gcr-benchmark-20261008/run_ros_benchmark.py \
  --root /tmp/dacn-gcr-benchmark-20261008 \
  --output /tmp/dacn-gcr-benchmark-20261008/results-new \
  --repeats 10 --search-time 1
```

Dùng thư mục output mới cho mỗi lần chạy. Runner chạy tuần tự; nếu thiếu RESULT hoặc không thu được đường của lượt báo thành công, runner dừng để kiểm tra lỗi. Failure trong thuật toán (không tìm ra đường trong ngân sách) vẫn là một kết quả hợp lệ.

Có thể chọn thử nhanh `--maps hole --planners rrt --modes none region_prior --repeats 1`. Sáu planner mặc định gồm rrt, rrt_star, rrt_sharp, brrt, brrt_star và informed_rrt_star; ba chế độ none, region_prior và sequence_guided. Không dùng planner:=all vì code demo hiện tại ép cả suite sang region_prior.

## Phân tích lại dữ liệu đã ghi

Dùng Python 3.10+ cùng requirements của convex-region-graph/research và gói markdown trên máy chủ. Đặt results/ nhận từ container cạnh inputs/ trong thư mục gói kết quả. Script analyze_ros.py dùng module research từ DACN-main:

```sh
PYTHONPATH=/duong/dan/DACN-main/convex-region-graph \
  /duong/dan/venv/bin/python scripts/analyze_ros.py /duong/dan/ros-gcr-benchmark
```

Script xác minh đủ 720 bản ghi duy nhất, không lỗi hạ tầng, đúng endpoint và collision toàn đoạn; sau đó tạo báo cáo và biểu đồ. Phần kiểm tra này được cấu hình cho cohort 10 seed × 4 map × 6 planner × 3 chế độ đã bàn giao.

Thời gian planner là số đo nội bộ C++; wall_seconds còn có khởi tạo node, gửi goal, thu topic và tắt node. Thời gian gọi LLM ban đầu không nằm trong cả hai vì benchmark dùng cache prior. Không trộn với kết quả RRT Python trước đó.

Bản GitHub giữ đường đi, tổng hợp, hình và thông tin kiểm chứng. Toàn bộ 720 log cùng marker cây đã thu được nằm trong gói ZIP bàn giao của phiên làm việc.
