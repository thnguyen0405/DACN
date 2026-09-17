# Giải thích từng dòng: llm_region_prior.py

Nhánh score vùng: graph + response/provider → validate scores → region_prior.json. Score càng cao càng ưu tiên lấy mẫu. Không có Dijkstra trong nhánh này. export_sampling_prior.py mới ghép polygon để C++ dùng được.

Nguồn: [llm_region_prior.py](/Users/nguyen/BK/SEM7/DACN/Motion_Planner/convex-region-graph/llm_region_prior.py). Số dòng khớp bản đọc ngày 17/09/2026 (223 dòng). Code nguồn không bị sửa.

Bảng giữ cả dòng trống và dấu đóng/mở để bạn đối chiếu không bị lệch số dòng. Với một câu lệnh xuống nhiều dòng, đọc các dòng liền nhau như một biểu thức.

| Dòng | Code gốc | Giải thích tiếng Việt |
| --- | --- | --- |
| 1 | <code>#!/usr/bin/env python3</code> | Chỉ dẫn chạy bằng python3 khi thực thi trực tiếp. |
| 2 | <code>&quot;&quot;&quot;Ask an LLM for per-region importance scores for sampling-based planning.&quot;&quot;&quot;</code> | Docstring: hỏi LLM mức quan trọng của từng vùng để hướng dẫn lấy mẫu. |
| 3 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 4 | <code>from __future__ import annotations</code> | Hoãn đánh giá type annotation; các chú thích kiểu hỗ trợ đọc code/tooling, không tự validate dữ liệu lúc chạy. |
| 5 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 6 | <code>import argparse</code> | Import bộ phân tích đối số dòng lệnh của thư viện chuẩn. |
| 7 | <code>import json</code> | Import JSON encoder/decoder để chuyển giữa chuỗi JSON và object Python. |
| 8 | <code>import math</code> | Import các phép toán như hypot và isfinite phục vụ hình học/kiểm tra số. |
| 9 | <code>import sys</code> | Import sys để ghi lỗi vào stderr và làm việc với tiến trình. |
| 10 | <code>import warnings</code> | Import hệ thống cảnh báo; warning có thể được ghi nhận mà không dừng chương trình. |
| 11 | <code>from abc import ABC, abstractmethod</code> | ABC và abstractmethod dùng tạo interface trừu tượng mà provider cụ thể phải triển khai. |
| 12 | <code>from pathlib import Path</code> | Import lớp Path biểu diễn đường dẫn và thao tác đọc/ghi file/thư mục. |
| 13 | <code>from typing import Any</code> | Any là chú thích kiểu linh hoạt cho dữ liệu JSON có nhiều kiểu giá trị. |
| 14 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 15 | <code>from graph_utils import load_json_object, prepare_planning_graph, require_region</code> | Import hàm nạp JSON, chuẩn hóa graph và xác nhận start/goal tồn tại. |
| 16 | <code>from llm_weight_provider import (</code> | Bắt đầu import thành phần dùng lại từ llm_weight_provider. |
| 17 | <code>    LLMProviderError,</code> | Exception thống nhất cho lỗi LLM. |
| 18 | <code>    OpenRouterWeightProvider,</code> | Tái sử dụng provider có HTTP transport, cấu hình, retry và parse JSON. |
| 19 | <code>    graph_prompt_data,</code> | Hàm rút gọn graph thành dữ liệu prompt. |
| 20 | <code>    load_dotenv,</code> | Hàm nạp cấu hình .env. |
| 21 | <code>)</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 22 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 23 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 24 | <code>MISSING_REGION_SCORE = 0.1</code> | Score mặc định 0.1 cho từng vùng bị LLM bỏ sót; không phải cận dưới của mọi score LLM. |
| 25 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 26 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 27 | <code>class MissingRegionScoreWarning(UserWarning):</code> | Định nghĩa một loại warning riêng, không phải exception dừng chương trình. |
| 28 | <code>    &quot;&quot;&quot;Emitted when omitted graph regions receive the documented prior floor.&quot;&quot;&quot;</code> | Docstring mô tả cảnh báo vùng thiếu nhận score dự phòng dương. |
| 29 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 30 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 31 | <code>class LLMRegionPriorProvider(ABC):</code> | Interface trừu tượng cho provider chấm điểm từng vùng. |
| 32 | <code>    &quot;&quot;&quot;Replaceable interface for general or future adapted region-prior models.&quot;&quot;&quot;</code> | Docstring: có thể thay provider/model mà giữ nguyên bước validation. |
| 33 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 34 | <code>    @abstractmethod</code> | Đánh dấu phương thức mà lớp con phải triển khai để có thể tạo đối tượng cụ thể. |
| 35 | <code>    def get_region_scores(</code> | Khai báo get_region_scores. |
| 36 | <code>        self, graph: dict[str, Any], start_region: str, goal_region: str</code> | Nhận self, graph và ID start/goal. |
| 37 | <code>    ) -&gt; dict[str, Any]:</code> | Trả dict JSON đã decode. |
| 38 | <code>        &quot;&quot;&quot;Return the provider&#x27;s decoded region-score response.&quot;&quot;&quot;</code> | Docstring của hợp đồng interface; không tự thực hiện request. |
| 39 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 40 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 41 | <code>class OpenRouterRegionPriorProvider(OpenRouterWeightProvider, LLMRegionPriorProvider):</code> | Đa kế thừa: dùng HTTP transport của OpenRouterWeightProvider và interface region-prior. |
| 42 | <code>    &quot;&quot;&quot;Region-prior task using the existing safe OpenRouter transport.&quot;&quot;&quot;</code> | Docstring: chỉ thay tác vụ/prompt, dùng lại phần truyền HTTP. |
| 43 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 44 | <code>    def get_region_scores(</code> | Triển khai phương thức lấy scores theo vùng. |
| 45 | <code>        self, graph: dict[str, Any], start_region: str, goal_region: str</code> | Nhận graph và cặp start/goal của bài toán. |
| 46 | <code>    ) -&gt; dict[str, Any]:</code> | Khai báo kết quả là dict. |
| 47 | <code>        template = self.prompt_path.read_text(encoding=&quot;utf-8&quot;)</code> | Đọc file prompt UTF-8 đã được cấu hình ở constructor kế thừa. |
| 48 | <code>        prompt = template.rstrip() + &quot;\n\nINPUT GRAPH DATA:\n&quot; + json.dumps(</code> | Bỏ khoảng trắng cuối template rồi nối nhãn và graph JSON. |
| 49 | <code>            graph_prompt_data(graph, start_region, goal_region), ensure_ascii=False</code> | Dùng dữ liệu rút gọn gồm ID, centroid, topology, start/goal; không gửi polygon hay occupancy map. |
| 50 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 51 | <code>        result, resolved_model = self._get_model_json(prompt)</code> | Gọi transport chung, nhận nội dung model đã parse và tên model thực tế. |
| 52 | <code>        return {</code> | Bắt đầu tạo response chuẩn của provider region-prior. |
| 53 | <code>            &quot;provider_metadata&quot;: {</code> | Metadata giúp ghi lại nguồn/model/tham số của request. |
| 54 | <code>                &quot;provider&quot;: &quot;openrouter&quot;,</code> | Ghi tên provider openrouter. |
| 55 | <code>                &quot;requested_model&quot;: self.model,</code> | Ghi model đã yêu cầu. |
| 56 | <code>                &quot;resolved_model&quot;: resolved_model,</code> | Ghi model API thực tế báo về, có thể None. |
| 57 | <code>                &quot;temperature&quot;: self.temperature,</code> | Ghi temperature đã sử dụng. |
| 58 | <code>            },</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 59 | <code>            &quot;region_scores&quot;: result.get(&quot;region_scores&quot;),</code> | Lấy region_scores bằng get; nếu model không trả trường này, validator phía sau sẽ bắt lỗi. |
| 60 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 61 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 62 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 63 | <code>def parse_region_score_response(response: str &#124; dict[str, Any]) -&gt; dict[str, Any]:</code> | Chuẩn hóa response từ chuỗi JSON hoặc dict thành dict đúng schema ngoài. |
| 64 | <code>    if isinstance(response, str):</code> | Chỉ json.loads khi response còn là string. |
| 65 | <code>        try:</code> | Bắt lỗi cú pháp JSON của chuỗi response. |
| 66 | <code>            response = json.loads(response)</code> | Giải mã JSON thành object Python. |
| 67 | <code>        except json.JSONDecodeError as exc:</code> | Bắt JSON không hợp lệ. |
| 68 | <code>            raise LLMProviderError(f&quot;LLM returned invalid JSON: {exc}&quot;) from exc</code> | Đổi lỗi parse thành LLMProviderError, giữ exception gốc qua from exc. |
| 69 | <code>    if not isinstance(response, dict):</code> | Kết quả phải là object/dict, không phải list, null hay số. |
| 70 | <code>        raise LLMProviderError(&quot;LLM region-prior response must be a JSON object&quot;)</code> | Báo lỗi response không phải object. |
| 71 | <code>    if not isinstance(response.get(&quot;region_scores&quot;), list):</code> | Trường region_scores bắt buộc là list. |
| 72 | <code>        raise LLMProviderError(&quot;LLM response field &#x27;region_scores&#x27; must be a list&quot;)</code> | Báo lỗi thiếu hoặc sai kiểu region_scores. |
| 73 | <code>    return response</code> | Trả response đã kiểm tra lớp ngoài; chưa kiểm tra từng score. |
| 74 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 75 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 76 | <code>def validate_region_scores(</code> | Hàm kiểm tra từng score và bổ sung các vùng thiếu. |
| 77 | <code>    response: str &#124; dict[str, Any],</code> | Nhận response dạng string hoặc dict. |
| 78 | <code>    graph: dict[str, Any],</code> | Nhận graph đã chuẩn hóa. |
| 79 | <code>    missing_score: float = MISSING_REGION_SCORE,</code> | Cho phép ghi đè fallback, mặc định 0.1. |
| 80 | <code>) -&gt; tuple[dict[str, float], list[str]]:</code> | Trả bảng ID→score và danh sách ID được bù fallback. |
| 81 | <code>    &quot;&quot;&quot;Validate region IDs and scores, then fill individually omitted regions.&quot;&quot;&quot;</code> | Docstring mô tả hai bước validation và bổ sung từng vùng bị thiếu. |
| 82 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 83 | <code>    if not math.isfinite(missing_score) or not 0.0 &lt; missing_score &lt;= 1.0:</code> | Fallback phải hữu hạn và nằm trong (0,1]; đây là kiểm tra cấu hình fallback. |
| 84 | <code>        raise ValueError(&quot;Missing-region fallback score must be in (0, 1]&quot;)</code> | Ném ValueError nếu fallback không hợp lệ. |
| 85 | <code>    parsed = parse_region_score_response(response)</code> | Parse/kiểm tra object ngoài trước khi xử lý từng record. |
| 86 | <code>    region_order = [vertex[&quot;id&quot;] for vertex in graph[&quot;vertices&quot;]]</code> | Lưu thứ tự ID theo graph để output ổn định. |
| 87 | <code>    known = set(region_order)</code> | Tạo set ID phục vụ kiểm tra membership nhanh. |
| 88 | <code>    scores: dict[str, float] = {}</code> | Khởi tạo bảng score đã qua validation. |
| 89 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 90 | <code>    for index, item in enumerate(parsed[&quot;region_scores&quot;]):</code> | Duyệt từng record cùng chỉ số để báo lỗi cụ thể. |
| 91 | <code>        if not isinstance(item, dict):</code> | Record phải là dict. |
| 92 | <code>            raise LLMProviderError(f&quot;region_scores[{index}] must be an object&quot;)</code> | Báo vị trí record sai kiểu. |
| 93 | <code>        region_id, score = item.get(&quot;id&quot;), item.get(&quot;score&quot;)</code> | Lấy id và score, thiếu trường thì get trả None. |
| 94 | <code>        if not isinstance(region_id, str):</code> | ID phải là chuỗi. |
| 95 | <code>            raise LLMProviderError(f&quot;region_scores[{index}] needs a string id&quot;)</code> | Báo lỗi ID sai kiểu. |
| 96 | <code>        if region_id not in known:</code> | ID phải thuộc graph đầu vào. |
| 97 | <code>            raise LLMProviderError(f&quot;Region score references unknown region: {region_id}&quot;)</code> | Từ chối vùng do LLM tự thêm. |
| 98 | <code>        if region_id in scores:</code> | ID không được lặp trong response. |
| 99 | <code>            raise LLMProviderError(f&quot;Duplicate region score for {region_id}&quot;)</code> | Mọi duplicate region score đều bị từ chối, kể cả hai score giống nhau; khác policy cạnh. |
| 100 | <code>        if isinstance(score, bool) or not isinstance(score, (int, float)):</code> | Loại bool trước vì bool là lớp con của int trong Python; chỉ nhận int/float. |
| 101 | <code>            raise LLMProviderError(f&quot;Score for {region_id} must be numeric&quot;)</code> | Báo lỗi score sai kiểu. |
| 102 | <code>        numeric_score = float(score)</code> | Chuẩn hóa score thành float. |
| 103 | <code>        if not math.isfinite(numeric_score) or not 0.0 &lt; numeric_score &lt;= 1.0:</code> | Loại NaN, vô cực, số không dương và số lớn hơn 1. |
| 104 | <code>            raise LLMProviderError(</code> | Bắt đầu tạo lỗi score ngoài miền hợp lệ. |
| 105 | <code>                f&quot;Score for {region_id} must be greater than 0 and less than or equal to 1&quot;</code> | Nội dung yêu cầu 0 < score ≤ 1. |
| 106 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 107 | <code>        scores[region_id] = numeric_score</code> | Lưu score hợp lệ theo ID. |
| 108 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 109 | <code>    if known and not scores:</code> | Nếu graph có vùng nhưng không một score nào dùng được... |
| 110 | <code>        raise LLMProviderError(&quot;LLM response contains no usable region scores&quot;)</code> | ...từ chối toàn bộ, không biến response rỗng thành toàn score mặc định. |
| 111 | <code>    missing = [region_id for region_id in region_order if region_id not in scores]</code> | Tìm vùng graph không xuất hiện trong scores, giữ thứ tự graph. |
| 112 | <code>    if missing:</code> | Chỉ cảnh báo/bù nếu danh sách missing không rỗng. |
| 113 | <code>        warnings.warn(</code> | Phát warning, không dừng chương trình. |
| 114 | <code>            f&quot;Assigned fallback score {missing_score} to {len(missing)} omitted region(s).&quot;,</code> | Thông báo giá trị fallback và số vùng bị thiếu. |
| 115 | <code>            MissingRegionScoreWarning,</code> | Chỉ định category cảnh báo riêng để bên gọi có thể lọc. |
| 116 | <code>            stacklevel=2,</code> | stacklevel=2 chỉ warning về phía code gọi hàm, thay vì dòng nội bộ warnings.warn. |
| 117 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 118 | <code>        for region_id in missing:</code> | Duyệt các vùng bị bỏ sót. |
| 119 | <code>            scores[region_id] = missing_score</code> | Gán score dự phòng để mọi vùng vẫn có xác suất được chọn dương. |
| 120 | <code>    return scores, missing</code> | Trả bảng score đầy đủ và danh sách vùng đã bù. |
| 121 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 122 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 123 | <code>def build_region_prior(</code> | Hàm nghiệp vụ tạo artifact region_prior từ graph và response/provider. |
| 124 | <code>    raw_graph: dict[str, Any],</code> | Graph chưa chuẩn hóa. |
| 125 | <code>    start_region: str,</code> | ID vùng bắt đầu dùng để hỏi LLM và lưu metadata bài toán. |
| 126 | <code>    goal_region: str,</code> | ID vùng đích dùng để hỏi LLM và lưu metadata bài toán. |
| 127 | <code>    response: dict[str, Any] &#124; None = None,</code> | Response có sẵn cho chế độ offline; contract của hàm này là dict hoặc None. |
| 128 | <code>    provider: LLMRegionPriorProvider &#124; None = None,</code> | Provider dùng khi chưa có response. |
| 129 | <code>) -&gt; tuple[dict[str, Any], dict[str, Any], dict[str, float], list[str]]:</code> | Kết quả gồm prior JSON, graph chuẩn hóa, bảng scores và danh sách thiếu. |
| 130 | <code>    graph = prepare_planning_graph(raw_graph)</code> | Kiểm tra/copy graph có hướng. |
| 131 | <code>    require_region(graph, start_region, &quot;start&quot;)</code> | Xác nhận vùng start tồn tại. |
| 132 | <code>    require_region(graph, goal_region, &quot;goal&quot;)</code> | Xác nhận vùng goal tồn tại. |
| 133 | <code>    if response is None:</code> | Chỉ gọi provider nếu chưa có response. |
| 134 | <code>        if provider is None:</code> | Kiểm tra provider có được cung cấp không. |
| 135 | <code>            raise LLMProviderError(&quot;A region-score response or provider is required&quot;)</code> | Thiếu cả response và provider: báo lỗi. |
| 136 | <code>        response = provider.get_region_scores(graph, start_region, goal_region)</code> | Gọi provider region-prior; không gọi Dijkstra. |
| 137 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 138 | <code>    scores, missing = validate_region_scores(response, graph)</code> | Validate và bổ sung score cho mọi vùng. |
| 139 | <code>    parsed = parse_region_score_response(response)</code> | Parse lại để đọc reason từ response gốc. |
| 140 | <code>    reasons = {</code> | Tạo ánh xạ ID→reason phục vụ giải thích, không ảnh hưởng xác suất. |
| 141 | <code>        item[&quot;id&quot;]: item.get(&quot;reason&quot;)</code> | Cặp key/value là ID và lời giải thích. |
| 142 | <code>        for item in parsed[&quot;region_scores&quot;]</code> | Duyệt các record model trả về. |
| 143 | <code>        if isinstance(item, dict)</code> | Chỉ nhận record dạng dict. |
| 144 | <code>        and isinstance(item.get(&quot;id&quot;), str)</code> | Chỉ nhận ID dạng chuỗi. |
| 145 | <code>        and isinstance(item.get(&quot;reason&quot;), str)</code> | Chỉ giữ reason là chuỗi; loại reason sai kiểu một cách nhẹ nhàng. |
| 146 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 147 | <code>    records = []</code> | Tạo danh sách record đầu ra. |
| 148 | <code>    for vertex in graph[&quot;vertices&quot;]:</code> | Duyệt theo thứ tự graph, không theo thứ tự LLM trả. |
| 149 | <code>        region_id = vertex[&quot;id&quot;]</code> | Lấy ID vùng. |
| 150 | <code>        record: dict[str, Any] = {&quot;id&quot;: region_id, &quot;score&quot;: scores[region_id]}</code> | Tạo record gồm ID và score đã validate hoặc bù. |
| 151 | <code>        if region_id in reasons:</code> | Nếu có reason hợp lệ từ model... |
| 152 | <code>            record[&quot;reason&quot;] = reasons[region_id]</code> | ...giữ reason đó để giải thích. |
| 153 | <code>        elif region_id in missing:</code> | Nếu không có reason và vùng thuộc missing... |
| 154 | <code>            record[&quot;reason&quot;] = &quot;Fallback score for a region omitted by the LLM.&quot;</code> | ...ghi rõ score do fallback, không giả thành lời giải thích của model. |
| 155 | <code>        records.append(record)</code> | Thêm record vào output. |
| 156 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 157 | <code>    metadata = response.get(&quot;provider_metadata&quot;)</code> | Lấy metadata nhà cung cấp nếu có. |
| 158 | <code>    prior: dict[str, Any] = {</code> | Tạo object prior đầu ra. |
| 159 | <code>        &quot;start_region&quot;: start_region,</code> | Lưu start_region của bài toán đã chấm. |
| 160 | <code>        &quot;goal_region&quot;: goal_region,</code> | Lưu goal_region của bài toán đã chấm. |
| 161 | <code>        &quot;region_scores&quot;: records,</code> | Lưu danh sách score theo vùng; chưa chứa polygon. |
| 162 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 163 | <code>    if isinstance(metadata, dict):</code> | Chỉ giữ metadata dạng dict. |
| 164 | <code>        prior = {&quot;provider_metadata&quot;: dict(metadata), **prior}</code> | Sao chép metadata rồi ghép các trường prior; **prior giải nén dictionary. |
| 165 | <code>    return prior, graph, scores, missing</code> | Trả đầy đủ bốn kết quả cho bên gọi. |
| 166 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 167 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 168 | <code>def parse_args(argv: list[str] &#124; None = None) -&gt; argparse.Namespace:</code> | Parser command line cho tác vụ region-prior. |
| 169 | <code>    parser = argparse.ArgumentParser(description=__doc__)</code> | Tạo parser dùng docstring làm mô tả. |
| 170 | <code>    parser.add_argument(&quot;graph&quot;, type=Path, help=&quot;GCR JSON file&quot;)</code> | Đối số vị trí graph, kiểu Path. |
| 171 | <code>    parser.add_argument(&quot;--start&quot;, required=True, help=&quot;Start region ID&quot;)</code> | Bắt buộc ID start. |
| 172 | <code>    parser.add_argument(&quot;--goal&quot;, required=True, help=&quot;Goal region ID&quot;)</code> | Bắt buộc ID goal. |
| 173 | <code>    parser.add_argument(&quot;--provider&quot;, choices=[&quot;openrouter&quot;], default=&quot;openrouter&quot;)</code> | Provider duy nhất ở CLI hiện tại là openrouter. |
| 174 | <code>    parser.add_argument(&quot;--response&quot;, type=Path, help=&quot;Reuse saved region-score JSON; skips the API&quot;)</code> | --response dùng response đã lưu hoặc mock, bỏ qua request API. |
| 175 | <code>    parser.add_argument(&quot;--output&quot;, type=Path, default=Path(&quot;outputs/region_prior.json&quot;))</code> | File prior đầu ra mặc định outputs/region_prior.json. |
| 176 | <code>    parser.add_argument(</code> | Bắt đầu khai báo tùy chọn đường dẫn prompt trên nhiều dòng. |
| 177 | <code>        &quot;--prompt&quot;,</code> | Tên tùy chọn --prompt. |
| 178 | <code>        type=Path,</code> | Chuyển giá trị đường dẫn thành Path. |
| 179 | <code>        default=Path(__file__).parent / &quot;prompts&quot; / &quot;region_prior_prompt.txt&quot;,</code> | Prompt mặc định nằm trong thư mục prompts cạnh file Python. |
| 180 | <code>    )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 181 | <code>    parser.add_argument(&quot;--env-file&quot;, type=Path, default=Path(&quot;.env&quot;))</code> | File biến môi trường mặc định .env theo cwd. |
| 182 | <code>    return parser.parse_args(argv)</code> | Parse argv thành Namespace. |
| 183 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 184 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 185 | <code>def main(argv: list[str] &#124; None = None) -&gt; int:</code> | Entry point CLI trả exit code. |
| 186 | <code>    args = parse_args(argv)</code> | Parse đối số. |
| 187 | <code>    try:</code> | Bắt đầu phạm vi bắt lỗi file/dữ liệu/provider. |
| 188 | <code>        raw_graph = load_json_object(args.graph)</code> | Đọc graph JSON. |
| 189 | <code>        graph = prepare_planning_graph(raw_graph)</code> | Chuẩn hóa topology. |
| 190 | <code>        require_region(graph, args.start, &quot;start&quot;)</code> | Kiểm tra start trước API; khác thứ tự trong CLI llm_planner.py. |
| 191 | <code>        require_region(graph, args.goal, &quot;goal&quot;)</code> | Kiểm tra goal trước API. |
| 192 | <code>        if args.response:</code> | Có --response thì dùng offline. |
| 193 | <code>            print(f&quot;Reusing region scores from {args.response}; API call skipped.&quot;)</code> | In file response được tái sử dụng. |
| 194 | <code>            response = load_json_object(args.response)</code> | Đọc response JSON. |
| 195 | <code>            provider = None</code> | Không cần provider vì đã có response. |
| 196 | <code>        else:</code> | Nhánh gọi API. |
| 197 | <code>            load_dotenv(args.env_file)</code> | Nạp .env không ghi đè môi trường có sẵn. |
| 198 | <code>            print(&quot;Calling OpenRouter for region importance scores...&quot;)</code> | In tác vụ đang gửi tới OpenRouter. |
| 199 | <code>            provider = OpenRouterRegionPriorProvider(args.prompt)</code> | Tạo provider region-prior; constructor được kế thừa từ provider weights. |
| 200 | <code>            response = provider.get_region_scores(graph, args.start, args.goal)</code> | Gọi model để lấy scores theo vùng. |
| 201 | <code>            metadata = response.get(&quot;provider_metadata&quot;, {})</code> | Lấy metadata để hiển thị. |
| 202 | <code>            print(f&quot;Requested model: {metadata.get(&#x27;requested_model&#x27;) or provider.model}&quot;)</code> | In requested_model, dự phòng bằng provider.model. |
| 203 | <code>            if metadata.get(&quot;resolved_model&quot;):</code> | Chỉ in resolved_model nếu API báo tên model thực tế. |
| 204 | <code>                print(f&quot;Resolved model: {metadata[&#x27;resolved_model&#x27;]}&quot;)</code> | In tên model thực tế. |
| 205 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 206 | <code>        prior, _, _, missing = build_region_prior(</code> | Tạo prior đã validate; dùng _ cho graph và bảng scores không cần dùng tiếp ở CLI. |
| 207 | <code>            raw_graph, args.start, args.goal, response=response, provider=provider</code> | Truyền response hiện có nên không có request API lần hai. |
| 208 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 209 | <code>        args.output.parent.mkdir(parents=True, exist_ok=True)</code> | Tạo thư mục chứa prior. |
| 210 | <code>        args.output.write_text(</code> | Ghi artifact prior sau validation, khác weights CLI lưu response trước validation. |
| 211 | <code>            json.dumps(prior, indent=2, ensure_ascii=False) + &quot;\n&quot;, encoding=&quot;utf-8&quot;</code> | Serialize đẹp, giữ Unicode, thêm newline và ghi UTF-8. |
| 212 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 213 | <code>        print(f&quot;Saved region prior for {len(prior[&#x27;region_scores&#x27;])} regions to {args.output}&quot;)</code> | In số vùng có score và đường dẫn output. |
| 214 | <code>        if missing:</code> | Nếu đã dùng fallback... |
| 215 | <code>            print(f&quot;Fallback score {MISSING_REGION_SCORE} was used for: {&#x27;, &#x27;.join(missing)}&quot;)</code> | ...in cụ thể các ID nhận score 0.1. |
| 216 | <code>        return 0</code> | Thành công: exit code 0, chưa khẳng định robot tìm được đường. |
| 217 | <code>    except (OSError, ValueError, LLMProviderError) as exc:</code> | Bắt các lỗi file, giá trị/graph và LLM. |
| 218 | <code>        print(f&quot;Error: {exc}&quot;, file=sys.stderr)</code> | In lỗi ra stderr. |
| 219 | <code>        return 1</code> | Thất bại: exit code 1. |
| 220 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 221 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 222 | <code>if __name__ == &quot;__main__&quot;:</code> | Main guard tránh tự chạy khi được import. |
| 223 | <code>    raise SystemExit(main())</code> | Dùng kết quả main làm exit status tiến trình. |
