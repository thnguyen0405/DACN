# Audit 30/09/2026

## Đã có trước thay đổi

- Map→ACD→safe-portal graph, region descriptors và portal descriptors.
- Strict LLM response validation, directed Dijkstra, OpenAI/OpenRouter adapters và offline JSON.
- Region-prior sampling, hard corridor sampling, collision checks, RViz và sáu phương pháp.
- Point-robot clearance tương đương configuration-space inflation.

## Hoàn thiện trong lần cập nhật này

- Một schema input chung `gcr-llm-input/v2`; giữ nested descriptors để tương thích dataset cũ.
- Baseline deterministic riêng biệt trong `scoring.py`; reason chứa từng contribution.
- Missing edge cost dùng geometry-aware heuristic trong pipeline hợp nhất.
- Sequence-guided mode: giữ thứ tự, weighted regions, consecutive portals và global exploration cấu hình được.
- C++ loader/sampler và launch parameter cho `sequence_guided` trên cả sáu planner.
- Metrics: pure plan time, first-solution time, path length/ratio, iterations và nodes added.
- Benchmark 3 mode × nhiều seed; JSON/CSV từng run và thống kê aggregate; failure/timeout không có path length.
- Unit tests mới cho scoring, edge cost, sequence distribution/exploration, benchmark math và configuration-space boundaries.

## Còn hạn chế

- Chưa fine-tune model; mock không phải AI và không phải ground truth.
- Corner proximity chỉ có thể được model/heuristic dùng khi descriptor hiện có chứng minh; graph chưa có field khoảng cách tới từng corner riêng.
- Chưa có benchmark mới trong commit này vì môi trường Windows hiện tại không có ROS/catkin. File benchmark cũ không bị sửa hoặc giả lập.
- Sequence adaptation theo tiến độ tree chưa bật; chiến lược hiện là static mixture, dùng giống nhau cho hai hướng của BRRT. Đây là lựa chọn an toàn, rõ ràng và reproducible cho vòng đánh giá hiện tại.

