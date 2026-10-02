# Nội dung đề xuất slide 17–18

## Slide 17 — Explainable region/edge scoring

- Input chỉ gồm start/goal, 15 convex regions, 34 directed safe portals, descriptors đo từ demo và clearance 0.30 m.
- Region score `[0,1]`: sampling priority; kết hợp progress, connectivity, clearance, size, shape, detour và required bottleneck.
- Edge cost `(0,1]`: graph-search cost; thêm centroid distance, portal width, safe width và safe traversability.
- Region score và edge cost liên quan nhưng không đồng nhất.
- LLM mode trả reason dựa trên feature thật; heuristic mode là baseline không AI với contribution số học.
- Demo: C9 nhận bottleneck bonus; C13→C14 cost thấp nhờ final goal progress.

## Slide 18 — Region sequence guides RRT, không thay thế RRT

- Dijkstra demo: `C0→C6→C7→C9→C12→C13→C14`.
- Default thí nghiệm: 80% guided, 20% uniform global exploration; trong guided draw có thể ưu tiên safe portal liên tiếp.
- Region trong sequence được chọn theo score, sau đó sample đều theo diện tích polygon.
- Sequence không phải waypoint path. RRT vẫn nearest/steer/add/rewire và collision-check tất cả point/segment.
- Dijkstra success ≠ planner success. RRT success chỉ khi có path start→goal đã xác minh collision-free.
- So sánh công bằng: cùng map/start/goal/clearance/budget/seeds cho baseline, region prior và sequence-guided.

