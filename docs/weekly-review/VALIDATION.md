# Kết quả xác minh

## Benchmark ROS đã chạy

ROS Noetic trong container Linux ARM64; map demo 16 × 10 m, robot radius + margin = 0,30 m. Start (1,1,0), goal (15,9,0).

5 planner × 2 chế độ × 3 seed (42–44), cùng ngân sách 0,5 giây / 5.000 node; planar, informed off, step replay off. Prior từ mock, không phải model đã train.

| Planner | Chế độ | Thành công | Wall time trung bình (s) | Chiều dài trung bình (m) |
|---|---|---:|---:|---:|
| rrt | none | 3/3 | 0.0472 | 19.0922 |
| rrt | region_prior | 3/3 | 0.0416 | 19.2784 |
| rrt_star | none | 3/3 | 0.5048 | 16.4904 |
| rrt_star | region_prior | 3/3 | 0.5056 | 16.4949 |
| rrt_sharp | none | 3/3 | 0.5052 | 16.4812 |
| rrt_sharp | region_prior | 3/3 | 0.5051 | 16.4844 |
| brrt | none | 3/3 | 0.0539 | 18.3134 |
| brrt | region_prior | 3/3 | 0.0541 | 18.7238 |
| brrt_star | none | 3/3 | 0.5049 | 16.4881 |
| brrt_star | region_prior | 3/3 | 0.5038 | 16.4949 |

Dữ liệu từng lượt: [benchmark.json](benchmark.json). Wall time gồm lời gọi plan và visualization, không phải thời gian đến nghiệm đầu. Giới hạn node có thể kết thúc lượt trước 0,5 giây. Các đường báo success đều được kiểm tra lại đầu/cuối và từng đoạn.

**Không có kết luận prior tốt hơn baseline từ bảng này.** Đây là kiểm tra chạy được trên một map; một số lượt prior cho đường dài hơn. Cần nhiều map, nhiều seed và LLM/nhãn thật để đánh giá hiệu quả nghiên cứu.

## Kiểm thử tự động

- Python: 73 tests pass, gồm moment polygon, clearance, connectivity, dữ liệu chấm nhãn và parser API.
- C++: `catkin_test_results` báo 0 lỗi, 0 failures; build thành công; sampler và hình học map có test cho clearance robot đĩa, biên lõm, đoạn cắt vật cản, hình học không hợp lệ và baseline 2D.
- API thật/fine-tuning: chưa thực hiện. Không gửi key hoặc dữ liệu lên dịch vụ trong lượt kiểm thử này.

## Kiểm tra demo trực quan

- Demo full đã chạy trong ROS: map publisher, RRT* và RViz.
- Service `next_step` trả thành công với các sự kiện `sample` và `nearest`.
- RViz dùng camera TopDownOrtho, toàn bộ map cùng frame `map`; vật cản cam, biên vùng vàng, đường kết quả mảnh.
- [Ảnh RViz](rviz-demo.png).

## Chế độ sáu phương pháp dùng chung prior

Kiểm tra `planner:=all`, seed 42, ngân sách 0,5 giây mỗi phương pháp trên cùng map/prior mock:

- Cả RRT, RRT*, RRT#, BRRT, BRRT* và Informed RRT* báo `guidance=region_prior success=1`.
- Sáu topic `*_final_path` riêng đều có đầu (1,1,0), cuối (15,9,0); kiểm tra đầu/cuối và va chạm từng đoạn được thực hiện trước khi xuất kết quả.
- Client đăng ký sau khi chạy xong và đăng ký lại đều nhận được sáu đường có latch.
- Cấu hình RViz có sáu Group riêng, mỗi nhóm chứa Path và Waypoints đúng topic.
- Build ROS thành công; `catkin_test_results`: 40 tests, 0 errors, 0 failures (tổng do catkin báo). Bổ sung kiểm tra prior nằm trong ellipse xoay, miền giao rỗng, reset và prior thường không bị clip.

Đây là kiểm thử tích hợp với prior mock, chưa phải đánh giá chất lượng LLM thật.
