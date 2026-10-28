# Convex-region graph và LLM sampling prior

```bash
bash run_demo.sh
```

Demo offline: map → phân rã lồi → graph và descriptor hình học → mock scoring
→ sampling prior cho C++ → kiểm thử. Không gọi LLM thật hay train model.

Hướng dẫn ROS, chạy từng planner, phát lại từng bước và giải thích luồng map:
[Demo tuần này](../docs/weekly-review/README.md).

Công thức, rubric và dữ liệu huấn luyện:
[Tiêu chí chấm điểm](../docs/weekly-review/SCORING.md).

Nạp ảnh vệ tinh và polygon/mask, xuất **hai hình tĩnh** và bộ JSON giống các map
`hole`, `flappy`, rồi chấm LLM và xuất sampling prior bằng CLI:
[Module ảnh vệ tinh → graph](SATELLITE_README.md). Không cần web server.
