# Tóm tắt thuyết trình

## Introduction

Mục tiêu là dùng hiểu biết vùng lồi để thay đổi phân bố lấy mẫu, nhưng giữ tính đúng của sampling-based motion planning: graph/LLM chỉ tạo prior, collision checker và RRT quyết định đường hợp lệ.

## Work completed

Đã nối map→descriptors→LLM/mock/heuristic→Dijkstra→ordered sequence→mixed sampling cho cả sáu planner. Đã chuẩn hóa schema và validation, giữ baseline không phụ thuộc LLM, bổ sung metrics và benchmark nhiều seed.

## Remaining work

Chạy build/test ROS và benchmark mới trên môi trường Linux/ROS; mở rộng bộ map; thu nhãn chuyên gia hoặc output model thật; đo chi phí API riêng; cân nhắc descriptor corner/minimum clearance.

## Current limitations

Chưa fine-tune; mock chỉ phục vụ offline integration; heuristic weights chưa được giảng viên xác nhận; sequence mixture hiện static; một demo không đủ kết luận phương pháp tốt hơn.

## Next experiments

Chạy 6 planners × 3 modes × ít nhất 10–30 seeds/map, cùng budget. Báo success rate, time-to-first, planning time, path ratio, iterations/nodes và confidence/dispersion; giữ failure/timeout. Ablation: bỏ portal bias, thay 80/20 bằng nhiều tỷ lệ, LLM so với deterministic heuristic.

