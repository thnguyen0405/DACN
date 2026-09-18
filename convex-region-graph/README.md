# Demo

## Main terminal

```bash
docker start motion-planner-vnc
```

Open:

```text
http://localhost:6080
```

## Terminal 1

```bash
cd /workspace/sampling-based-path-finding-main
source /opt/ros/noetic/setup.bash
source devel/setup.bash
roslaunch path_finder rviz.launch
```

## Terminal 2

```bash
cd /workspace/sampling-based-path-finding-main
source /opt/ros/noetic/setup.bash
source devel/setup.bash

roslaunch path_finder test_planners.launch \
  guidance_mode:=region_prior
```

Trong RViz chọn **3D Nav Goal** để đặt goal.
