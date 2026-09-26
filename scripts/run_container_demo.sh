#!/usr/bin/env bash
# Run current checkout in the existing ROS container, without overwriting its
# /workspace mount (which may point at an older, different checkout).
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
container_name="${ROS_CONTAINER:-motion-planner-vnc}"
demo_root=/tmp/llm-path-planning-demo

docker start "$container_name" >/dev/null
# Copy only source and generated demo inputs; never copy .env or .git.
docker exec "$container_name" mkdir -p "$demo_root/sampling-based-path-finding-main/src" "$demo_root/convex-region-graph/outputs"
docker cp "$repo_dir/sampling-based-path-finding-main/src/." "$container_name:$demo_root/sampling-based-path-finding-main/src/"
docker cp "$repo_dir/convex-region-graph/example_map.json" "$container_name:$demo_root/convex-region-graph/example_map.json"
docker cp "$repo_dir/convex-region-graph/outputs/sampling_prior.json" "$container_name:$demo_root/convex-region-graph/outputs/sampling_prior.json"
docker exec "$container_name" bash -lc 'set -e; source /opt/ros/noetic/setup.bash; cd /tmp/llm-path-planning-demo/sampling-based-path-finding-main; catkin_make -j2'
# Default headless works even if the container has no active VNC desktop.
# To show RViz on an existing X display: ROS_DISPLAY=:1 ... rviz:=true
exec docker exec -it -e "DISPLAY=${ROS_DISPLAY:-:1}" \
  -e "XAUTHORITY=${ROS_XAUTHORITY:-/home/ubuntu/.Xauthority}" -e LIBGL_ALWAYS_SOFTWARE=1 "$container_name" bash -lc \
  'source /opt/ros/noetic/setup.bash; source /tmp/llm-path-planning-demo/sampling-based-path-finding-main/devel/setup.bash; exec roslaunch path_finder demo.launch rviz:=false "$@"' bash "$@"
