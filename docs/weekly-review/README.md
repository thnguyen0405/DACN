1. Create graph of convex region with python
```bash
cd /Users/nguyen/BK/SEM7/DACN/DACN-github

bash convex-region-graph/run_demo.sh
```




2. Chạy cả 6 phương pháp với prior LLM

Từ thư mục gốc repo, sau khi tạo map/prior bằng bước 1:

```bash
ROS_DISPLAY=:1 bash scripts/run_container_demo.sh planner:=all rviz:=true
```

Mở desktop RViz tại http://localhost:6080. Trong **Displays → Planning**, bật/tắt nhóm tương ứng:

| Nhóm | Phương pháp | Màu |
| --- | --- | --- |
| 01 RRT | RRT + prior LLM | Cam |
| 02 RRT* | RRT* + prior LLM | Xanh lá |
| 03 RRT# | RRT# + prior LLM | Xanh dương |
| 04 BRRT | BRRT + prior LLM | Tím |
| 05 BRRT* | BRRT* + prior LLM | Đỏ |
| 06 Informed RRT* | Informed RRT* + prior LLM | Hồng |

Checkbox của mỗi nhóm điều khiển cả **Path** và **Waypoints**. Kết quả được giữ trên các topic riêng có latch; mở RViz sau khi tính xong hoặc bỏ chọn rồi chọn lại đều nhận lại đường đi. Chọn goal mới sẽ xóa kết quả cũ và chạy lại cả sáu với cùng start/goal.

`planner:=all` bắt buộc `guidance_mode=region_prior`, dùng chung map và `sampling_prior.json` cho cả sáu. Một lệnh chạy lần lượt sáu thuật toán trong cùng node rồi giữ đồng thời sáu kết quả để so sánh; đây không phải sáu luồng tính toán song song. `search_time:=2.0` đặt ngân sách tìm kiếm cho từng thuật toán; RRT/BRRT có thể trả về sớm khi tìm được đường.

LLM chấm điểm các vùng trước; C++ lấy mẫu theo xác suất tỷ lệ với điểm vùng rồi kiểm tra va chạm bằng map. LLM không được gọi lại ở mỗi bước RRT. Riêng Informed RRT*, sau lời giải đầu tiên, mẫu prior phải nằm thêm trong ellipse được xác định bởi start, goal và độ dài đường tốt nhất. Giới hạn 256 lần thử cho mỗi mẫu giúp tránh kẹt khi miền giao quá nhỏ; nếu không lấy được mẫu hợp lệ thì bỏ lượt đó.

**Prior demo hiện là điểm mock.** Để thử LLM thật, tạo prior bằng luồng LLM của project rồi chạy lại lệnh trên. Chế độ all không tự train hay tự gọi LLM; chất lượng và độ phủ của các vùng trong prior ảnh hưởng trực tiếp khả năng tìm đường của cả sáu.

Chạy riêng phương pháp thứ sáu:

```bash
ROS_DISPLAY=:1 bash scripts/run_container_demo.sh planner:=informed_rrt_star rviz:=true
```

Để xem replay từng bước, chọn một phương pháp cụ thể và thêm `step_mode:=true` (không dùng cùng `planner:=all`).
