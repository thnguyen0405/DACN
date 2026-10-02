# Cách chạy demo với LLM miễn phí qua OpenRouter

## 1. Chuẩn bị

- Python 3.10 trở lên.
- Mở Docker Desktop; cần có sẵn container ROS `motion-planner-vnc`.
- Tạo API key tại https://openrouter.ai/keys.
- Lưu cấu hình sau vào `/Users/nguyen/BK/SEM7/DACN/DACN-main/convex-region-graph/.env`, thay phần giữ chỗ bằng key của bạn:

```dotenv
OPENROUTER_API_KEY=DAN_KEY_OPENROUTER_VAO_DAY
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TEMPERATURE=0
```

Không đưa file `.env` lên GitHub.

## 2. Tạo graph từ map mẫu

```bash
cd /Users/nguyen/BK/SEM7/DACN/DACN-main/convex-region-graph

python3 build_graph.py example_map.json \
  --regions-output convex_regions.json \
  --output graph.json \
  --svg graph.svg
```

## 3. Gọi LLM chấm điểm vùng

Chạy trong cùng thư mục. Với map mẫu hiện tại, start là `C0`, goal là `C14`.

```bash
export SSL_CERT_FILE=/etc/ssl/cert.pem
unset OPENROUTER_API_KEY OPENROUTER_MODEL OPENROUTER_BASE_URL OPENROUTER_TEMPERATURE

python3 llm_region_prior.py graph.json \
  --provider openrouter \
  --start C0 \
  --goal C14 \
  --output outputs/openrouter_region_prior.json
```

Chỉ tiếp tục khi hiện `Saved region prior ...`. Nếu có `Error: ...`, dừng tại bước này. Cảnh báo `MissingRegionScoreWarning` nghĩa là vùng bị LLM bỏ sót được gán điểm mặc định `0.5`; demo vẫn chạy được.

## 4. Xuất prior cho C++

```bash
python3 export_sampling_prior.py \
  --graph graph.json \
  --prior outputs/openrouter_region_prior.json \
  --output outputs/sampling_prior.json
```

Chỉ tiếp tục khi hiện `Exported 15 scored regions ...`.

## 5. Chạy sáu planner và mở RViz

```bash
cd /Users/nguyen/BK/SEM7/DACN/DACN-main

ROS_DISPLAY=:1 bash scripts/run_container_demo.sh \
  planner:=all rviz:=true
```

Giữ Terminal này mở. Truy cập http://localhost:6080, vào **Displays → Planning** và bật các nhóm từ **01 RRT** đến **06 Informed RRT***.

Nhấn **Control + C** trong Terminal để dừng demo.

**Không chạy lại `run_demo.sh` sau bước 3: script đó ghi đè prior bằng điểm mock.**
