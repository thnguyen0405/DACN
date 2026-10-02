# Ví dụ region score và edge cost

Có hai chế độ tách biệt:

1. `scoring_mode=llm`: model đọc `gcr-llm-input/v2`, trả score/cost kèm `reason` dựa trên đúng feature được cung cấp.
2. `scoring_mode=deterministic_heuristic`: `scoring.py` tính cục bộ, không gọi model và luôn ghi “not LLM” trong reason. Đây là baseline/fallback kiểm thử.

## Rubric region

`region_score ∈ [0,1]`; cao hơn nghĩa là ưu tiên sampling. Rubric xem xét clearance, shape, size, safe connectivity, goal progress, detour và required bottleneck. Vùng hẹp không tự động bị loại: vertex mà khi bỏ đi làm mất kết nối start–goal nhận bottleneck bonus.

Heuristic hiện tại chuẩn hóa min–max trên chính graph (missing → neutral 0.5):

```text
score = clamp[0,1](
  0.20
  + 0.24 goal_progress
  + 0.14 safe_connectivity
  + 0.14 clearance
  + 0.08 size
  + 0.08 shape_quality
  - 0.12 detour
  + 0.20 required_bottleneck
  + 0.12 endpoint)
```

Các trọng số là lựa chọn kỹ thuật thử nghiệm, chưa được giảng viên xác nhận là tối ưu. Ví dụ số học minh họa rubric: `0.50 + 0.15 progress + 0.10 connectivity - 0.20 low-clearance - 0.10 detour = 0.45`.

Kết quả heuristic trên graph demo thật (làm tròn):

| Region | Score | Ảnh hưởng nổi bật |
|---|---:|---|
| C0 | 0.533 | start endpoint, size, clearance |
| C6 | 0.521 | progress, degree, clearance |
| C7 | 0.551 | progress và clearance cao |
| C9 | 0.959 | required bottleneck, degree 4, size và clearance |
| C12 | 0.616 | goal progress, clearance |
| C13 | 0.619 | goal progress |
| C14 | 0.733 | goal endpoint và progress |

## Rubric edge

`edge_cost ∈ (0,1]`; Dijkstra tối thiểu hóa tổng cost. Heuristic không lấy đơn thuần trung bình hai region scores:

```text
cost = clamp[0.01,1](
  0.18
  + 0.22 relative_centroid_length
  + 0.15 portal_width_penalty
  + 0.15 safe_portal_width_penalty
  + 0.12 safe_traversability_penalty
  - 0.10 goal_progress
  + 0.08 detour_penalty
  + 0.10 (1 - destination_region_score))
```

| Directed edge | Cost | Lý do chính |
|---|---:|---|
| C0→C6 | 0.530 | portal khá rộng, progress tốt |
| C6→C7 | 0.384 | edge ngắn, progress và clearance tốt |
| C7→C9 | 0.408 | destination C9 rất quan trọng |
| C9→C12 | 0.266 | portal rất rộng, goal progress |
| C12→C13 | 0.244 | edge ngắn, progress tốt |
| C13→C14 | 0.214 | final goal progress |
| C0→C1 | 0.773 | portal/safe width tương đối kém và detour |
| C1→C5 | 0.706 | portal hẹp hơn |

Với deterministic heuristic trên demo hiện tại:

- `C0→C6→C7→C9→C12→C13→C14`: tổng cost `2.04577881`.
- `C0→C1→C5→C6→C7→C9→C12→C13→C14`: tổng cost `3.64117192`.

Dijkstra chọn sequence thứ nhất vì tổng cost thấp hơn. Mỗi cặp liên tiếp được kiểm tra có trong `directed_edges`; code không thể thêm shortcut không tồn tại.

Thiếu region score được điền neutral `0.5`. Thiếu edge cost trong pipeline hợp nhất được tính bằng heuristic hình học ở trên và ghi trong `model_completion.derived_edge_costs`; không gán bằng trung bình hai region. ID lạ, duplicate, non-finite, score ngoài `[0,1]`, cost ngoài `(0,1]` đều bị từ chối.
