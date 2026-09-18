# Demo

README này chứa toàn bộ các bước cần dùng để chạy demo:

```text
example_map.json
      |
      v
Map -> ACD -> Convex Regions -> GCR
      |
      v
LLM Region Prior -> sampling_prior.json
      |
      v
ROS / RViz / RRT
```

---

## 1. Trên Mac: cập nhật code

Mở Terminal trên Mac:

```bash
cd "/Users/nguyen/BK/SEM7/DACN/DACN-github"

git checkout main
git pull --ff-only origin main
```

Nếu `git pull` báo local changes:

```bash
git stash push -u -m "backup-before-demo"
git pull --ff-only origin main
```

Không cần `git stash pop` trước khi demo.

---

## 2. Trên Mac: chạy pipeline Map -> ACD -> GCR -> LLM

```bash
cd "/Users/nguyen/BK/SEM7/DACN/DACN-github/convex-region-graph"

bash run_demo.sh
```

Kết quả cần có:

```text
graph.svg
outputs/llm_route.svg
outputs/sampling_prior.json
```

Mở SVG trên macOS:

```bash
open graph.svg
open outputs/llm_route.svg
```

---

## 3. Copy code từ Mac sang container noVNC

Kiểm tra container đang chạy:

```bash
docker ps
```

Lấy `CONTAINER ID` của container ROS/noVNC.

Ví dụ:

```text
5aa8bd966643
```

Có thể lưu vào biến:

```bash
CONTAINER_ID=5aa8bd966643
```

Từ thư mục gốc repo:

```bash
cd "/Users/nguyen/BK/SEM7/DACN/DACN-github"
```

Copy phần GCR/LLM:

```bash
docker cp convex-region-graph/. \
  $CONTAINER_ID:/workspace/convex-region-graph/
```

Copy toàn bộ ROS source mới:

```bash
docker cp sampling-based-path-finding-main/src/. \
  $CONTAINER_ID:/workspace/sampling-based-path-finding-main/src/
```

> `/workspace` trong noVNC không phải Git repository, vì vậy không chạy `git pull` trong noVNC.

---

## 4. Trong noVNC: chạy lại pipeline Python

Mở Terminal trong noVNC:

```bash
cd /workspace/convex-region-graph

python3 --version
bash run_demo.sh
```

Nếu thành công sẽ thấy cuối log:

```text
OK
Done.
```

Kiểm tra file RRT cần dùng:

```bash
ls /workspace/convex-region-graph/outputs/sampling_prior.json
```

---

## 5. Trong noVNC: build ROS

Chạy bước này khi:

- container mới;
- vừa copy code C++ mới;
- vừa sửa file `.cpp`, `.h` hoặc `CMakeLists.txt`.

```bash
cd /workspace/sampling-based-path-finding-main

source /opt/ros/noetic/setup.bash

catkin_make

source devel/setup.bash
```

Build thành công khi cuối log đạt `100%`.

---

## 6. Terminal 1: chạy map + RViz

Mở Terminal 1 trong noVNC:

```bash
cd /workspace/sampling-based-path-finding-main

source /opt/ros/noetic/setup.bash
source devel/setup.bash

roslaunch path_finder rviz.launch
```

Giữ terminal này chạy.

RViz phải hiển thị map từ:

```text
convex-region-graph/example_map.json
```

Map demo hiện tại:

```text
x: 0 -> 16
y: 0 -> 10
start: (1, 1, 0)
goal mẫu: gần (15, 9, 0)
```

---

## 7. Terminal 2: chạy RRT với LLM Region Prior

Mở Terminal 2 trong noVNC:

```bash
cd /workspace/sampling-based-path-finding-main

source /opt/ros/noetic/setup.bash
source devel/setup.bash
```

Chạy riêng RRT để demo dễ quan sát:

```bash
roslaunch path_finder test_planners.launch \
  guidance_mode:=region_prior \
  run_rrt:=true \
  run_rrt_star:=false \
  run_rrt_sharp:=false \
  run_brrt:=false \
  run_brrt_star:=false
```

Sau đó trong RViz:

1. Chọn **3D Nav Goal**.
2. Click một điểm trong free space.
3. Có thể chọn goal gần `(15, 9, 0)`.
4. Không chọn goal bên trong obstacle.

Nếu thành công, Terminal 2 sẽ hiện log RRT và RViz sẽ hiển thị tree/path.

---

## 8. Demo đối chứng: RRT không dùng LLM

Dừng Terminal 2 bằng:

```text
Ctrl+C
```

Sau đó chạy:

```bash
roslaunch path_finder test_planners.launch \
  guidance_mode:=none \
  run_rrt:=true \
  run_rrt_star:=false \
  run_rrt_sharp:=false \
  run_brrt:=false \
  run_brrt_star:=false
```

Để quay lại LLM-guided RRT:

```bash
roslaunch path_finder test_planners.launch \
  guidance_mode:=region_prior \
  run_rrt:=true \
  run_rrt_star:=false \
  run_rrt_sharp:=false \
  run_brrt:=false \
  run_brrt_star:=false
```

---

## 9. Checklist ngắn trước khi demo

### Mac

```bash
cd "/Users/nguyen/BK/SEM7/DACN/DACN-github"
git pull --ff-only origin main

cd convex-region-graph
bash run_demo.sh
```

Sau đó:

```bash
docker ps
```

và copy code vào container:

```bash
cd "/Users/nguyen/BK/SEM7/DACN/DACN-github"

CONTAINER_ID=<container_id>

docker cp convex-region-graph/. \
  $CONTAINER_ID:/workspace/convex-region-graph/

docker cp sampling-based-path-finding-main/src/. \
  $CONTAINER_ID:/workspace/sampling-based-path-finding-main/src/
```

### noVNC

```bash
cd /workspace/convex-region-graph
bash run_demo.sh
```

Nếu cần build:

```bash
cd /workspace/sampling-based-path-finding-main
source /opt/ros/noetic/setup.bash
catkin_make
source devel/setup.bash
```

Terminal 1:

```bash
roslaunch path_finder rviz.launch
```

Terminal 2:

```bash
roslaunch path_finder test_planners.launch \
  guidance_mode:=region_prior \
  run_rrt:=true \
  run_rrt_star:=false \
  run_rrt_sharp:=false \
  run_brrt:=false \
  run_brrt_star:=false
```

Cuối cùng chọn **3D Nav Goal** trong RViz.
