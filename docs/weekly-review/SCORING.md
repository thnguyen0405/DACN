# Descriptor và quy trình chấm nhãn

Các công thức dựa trên ảnh tiêu chí giảng viên cung cấp. Mỗi vertex của
`graph.json` có `descriptors`; mỗi portal có `traversability`.

| Nhóm | Field | Công thức / ý nghĩa |
|---|---|---|
| Size | area | Diện tích A của polygon, m² |
| Size | diameter | Khoảng cách lớn nhất giữa hai đỉnh, bằng đường kính vùng lồi, m |
| Shape | aspect_ratio | λ_max/λ_min của covariance phân bố đều theo diện tích; không phải căn tỷ lệ |
| Shape | compactness | P²/(4πA); 1 cho đường tròn lý tưởng, lớn hơn với vùng dài/hẹp |
| Clearance | centroid_clearance | Khoảng cách từ centroid đến vật cản gần nhất hoặc biên workspace, m |
| Clearance | mean_clearance | (1/A)∫clr(x)dx, xấp xỉ theo diện tích, m |
| Connectivity | degree | Số vùng có chung portal hình học |
| Connectivity | safe_degree | Số vùng kề còn lại sau loại portal quá hẹp |
| Conductance | conductance | Tổng độ rộng portal hình học / chu vi P |
| Conductance | safe_conductance | Tổng độ rộng portal sau thu hẹp, chỉ tính cạnh còn lại / P |
| Portal | portal_width | Chiều dài biên chung W_ij, m |
| Portal | safe_portal_width | Độ rộng sau bỏ clearance ở hai đầu, m |
| Portal | traversability | W_ij × min(CL_i,CL_j), m² |
| Portal | safe_traversability | Cùng công thức nhưng dùng safe_portal_width |

Covariance dùng moment chính xác của polygon với phân bố **đều theo diện tích**,
không dùng covariance của danh sách đỉnh. Mean clearance chia mỗi tam giác
fan thành 12² tam giác con, lấy khoảng cách ở trọng tâm rồi tính tổng có trọng
số diện tích. Đây là quadrature xác định, không phải giá trị tích phân chính xác.

Clr(x) tính tới obstacle và phần ngoài workspace. Biên phân rã giữa hai vùng
trống không phải vật cản. Mean clearance và traversability không chứng minh
mọi điểm hoặc đoạn trong vùng đều đủ an toàn. Thiếu map gốc thì clearance và
traversability là `null`, không tự đặt bằng 0.

## Cách dùng đặc trưng để chấm điểm

Prompt yêu cầu cân nhắc nhiều yếu tố, không áp đặt một công thức score cứng:

- Vùng lớn không nhất thiết quan trọng; vùng hẹp có thể là đường nối bắt buộc.
- Vùng nhiều kết nối tạo lựa chọn, nhưng một ngõ cụt chứa goal vẫn có thể quan trọng.
- Compactness và aspect ratio mô tả hình dạng; không suy diễn góc vật cản chưa có trong dữ liệu.
- Kết hợp clearance, portal và tiến triển về goal; giải thích bằng dữ liệu được cung cấp.
- Score trong [0,1] là ưu tiên lấy mẫu, không phải xác suất thành công đã hiệu chuẩn.

Pipeline demo chuyển score thành softmax (T=0,25), trộn 12% phân bố đều theo
**vùng**, rồi xuất xác suất vào field `score` của giao diện C++. C++ chọn vùng
proportional theo field này, chọn tam giác theo diện tích và lấy điểm đều trong
tam giác. Sau đó kiểm tra điểm/đoạn bằng mô hình robot đĩa.

## Chuẩn bị dataset

```bash
# Xuất task để người chấm nhãn; chưa có assistant target.
python3 export_scoring_dataset.py graph.json --output outputs/scoring_tasks.jsonl

# Sau khi có file nhãn cho đúng graph, xuất một ví dụ có target.
python3 export_scoring_dataset.py graph.json \
  --labels reviewed_labels.json --label-source human-reviewed \
  --output outputs/scoring_labeled.jsonl
```

Nhãn dùng schema `region_scores` và `edge_costs` như prompt. Mọi vùng phải có
score rõ ràng; ID/cạnh không tồn tại bị từ chối. Đáp án không tự được tạo bằng
fallback khi xuất supervised target. File `.metadata.json` ghi nguồn nhãn:
`human-reviewed`, `model-generated` hoặc `synthetic`.

**Chưa train/fine-tune model trong repo này.** Công việc đã hoàn thành ở mức
trích xuất đặc trưng, đưa vào prompt và xuất dữ liệu chấm nhãn/JSONL có kiểm tra.
Muốn train cần thêm nhiều map/start-goal, nhãn được duyệt, chọn base model và
quy trình huấn luyện. Không coi mock hiện tại là ground truth.

Đánh giá nên tách train/validation/test theo map (không chỉ theo dòng vùng),
so với uniform và các heuristic không LLM. Đo tỷ lệ thành công, thời gian đến
nghiệm đầu, chiều dài, clearance nhỏ nhất, số kiểm tra va chạm và chi phí gọi
LLM; lặp nhiều seed. Ghi cả ca thất bại và vùng bottleneck, không chỉ map thuận lợi.
