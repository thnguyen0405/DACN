# Giải thích từng dòng: llm_weight_provider.py

Module dùng chung có bốn vai trò: interface provider, cấu hình/prompt, HTTP transport, validation cost cạnh. Hai lớp JSON khác nhau: envelope HTTP và JSON nằm trong message.content. Retry chỉ bao quanh transport envelope, không bao quanh validation nội dung model.

Nguồn: [llm_weight_provider.py](/Users/nguyen/BK/SEM7/DACN/Motion_Planner/convex-region-graph/llm_weight_provider.py). Số dòng khớp bản đọc ngày 17/09/2026 (422 dòng). Code nguồn không bị sửa.

Bảng giữ cả dòng trống và dấu đóng/mở để bạn đối chiếu không bị lệch số dòng. Với một câu lệnh xuống nhiều dòng, đọc các dòng liền nhau như một biểu thức.

| Dòng | Code gốc | Giải thích tiếng Việt |
| --- | --- | --- |
| 1 | <code>&quot;&quot;&quot;LLM API abstraction and strict edge-weight response validation.&quot;&quot;&quot;</code> | Docstring: module tách giao tiếp API khỏi bước kiểm tra trọng số cạnh. |
| 2 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 3 | <code>from __future__ import annotations</code> | Hoãn đánh giá type annotation; các chú thích kiểu hỗ trợ đọc code/tooling, không tự validate dữ liệu lúc chạy. |
| 4 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 5 | <code>import json</code> | Import JSON encoder/decoder để chuyển giữa chuỗi JSON và object Python. |
| 6 | <code>import http.client</code> | Import loại lỗi HTTP mức thấp, dùng phát hiện response đọc chưa đầy đủ. |
| 7 | <code>import os</code> | Import os để đọc/đặt các biến môi trường cấu hình API. |
| 8 | <code>import urllib.error</code> | Import các exception HTTPError/URLError cho xử lý lỗi request. |
| 9 | <code>import urllib.request</code> | Import công cụ tạo/gửi HTTP request không cần SDK bên ngoài. |
| 10 | <code>import warnings</code> | Import hệ thống cảnh báo; warning có thể được ghi nhận mà không dừng chương trình. |
| 11 | <code>from abc import ABC, abstractmethod</code> | ABC và abstractmethod dùng tạo interface trừu tượng mà provider cụ thể phải triển khai. |
| 12 | <code>from pathlib import Path</code> | Import lớp Path biểu diễn đường dẫn và thao tác đọc/ghi file/thư mục. |
| 13 | <code>from typing import Any</code> | Any là chú thích kiểu linh hoạt cho dữ liệu JSON có nhiều kiểu giá trị. |
| 14 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 15 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 16 | <code>NEUTRAL_MISSING_WEIGHT = 0.5</code> | Cost dự phòng 0.5 cho từng cạnh thiếu; đây là lựa chọn policy của code, không phải dự đoán LLM. |
| 17 | <code>DEFAULT_OPENROUTER_MODEL = &quot;openrouter/free&quot;</code> | Tên model/router mặc định trong code là openrouter/free; không chứng minh dịch vụ hiện tại khả dụng. |
| 18 | <code>DEFAULT_OPENROUTER_BASE_URL = &quot;https://openrouter.ai/api/v1&quot;</code> | Base URL mặc định để ghép endpoint Chat Completions. |
| 19 | <code>DEFAULT_OPENROUTER_TEMPERATURE = 0.0</code> | Temperature mặc định 0.0; không bảo đảm kết quả model/router lặp lại tuyệt đối. |
| 20 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 21 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 22 | <code>class LLMProviderError(RuntimeError):</code> | Exception nghiệp vụ kế thừa RuntimeError để bên gọi bắt các lỗi LLM thống nhất. |
| 23 | <code>    &quot;&quot;&quot;Raised when an LLM request or response cannot be used.&quot;&quot;&quot;</code> | Docstring nêu request hoặc response không dùng được. |
| 24 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 25 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 26 | <code>class DuplicateEdgeWeightWarning(UserWarning):</code> | Loại UserWarning riêng cho duplicate cạnh có cùng weight. |
| 27 | <code>    &quot;&quot;&quot;Emitted when an identical repeated LLM edge-weight record is ignored.&quot;&quot;&quot;</code> | Docstring mô tả bản ghi trùng giống nhau sẽ bị bỏ qua có cảnh báo. |
| 28 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 29 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 30 | <code>class _RetryableOpenRouterError(Exception):</code> | Exception nội bộ báo lỗi transport đủ điều kiện retry. |
| 31 | <code>    &quot;&quot;&quot;Internal signal carrying the final user-facing transport error.&quot;&quot;&quot;</code> | Docstring: gói lỗi cuối cùng dành cho người dùng và tín hiệu retry. |
| 32 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 33 | <code>    def __init__(self, error: LLMProviderError, retry_message: str) -&gt; None:</code> | Constructor nhận lỗi LLM và thông báo sẽ retry. |
| 34 | <code>        super().__init__(str(error))</code> | Khởi tạo phần Exception cha bằng chuỗi mô tả lỗi. |
| 35 | <code>        self.error = error</code> | Giữ object lỗi gốc để ném ra nếu retry tiếp tục thất bại. |
| 36 | <code>        self.retry_message = retry_message</code> | Giữ thông báo dùng khi thông báo retry lần đầu. |
| 37 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 38 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 39 | <code>class LLMWeightProvider(ABC):</code> | Interface trừu tượng cho mọi provider chấm trọng số cạnh. |
| 40 | <code>    &quot;&quot;&quot;Replaceable interface for general or future adapted LLMs.&quot;&quot;&quot;</code> | Docstring: cho phép thay API/model mà không thay thuật toán graph search. |
| 41 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 42 | <code>    @abstractmethod</code> | Yêu cầu lớp con triển khai get_edge_weights. |
| 43 | <code>    def get_edge_weights(</code> | Khai báo phương thức lấy weights theo graph và cặp start/goal. |
| 44 | <code>        self, graph: dict[str, Any], start_region: str, goal_region: str</code> | self là đối tượng provider; ba đối số còn lại mô tả bài toán. |
| 45 | <code>    ) -&gt; dict[str, Any]:</code> | Contract trả dict JSON đã decode, không tự bảo đảm weights hợp lệ. |
| 46 | <code>        &quot;&quot;&quot;Return the provider&#x27;s decoded JSON response.&quot;&quot;&quot;</code> | Docstring mô tả kết quả interface. |
| 47 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 48 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 49 | <code>def load_dotenv(path: Path = Path(&quot;.env&quot;)) -&gt; None:</code> | Hàm đọc .env đơn giản, mặc định là .env trong cwd. |
| 50 | <code>    &quot;&quot;&quot;Load a small .env file without overriding existing environment values.&quot;&quot;&quot;</code> | Docstring: không ghi đè giá trị đã có trong os.environ. |
| 51 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 52 | <code>    if not path.exists():</code> | Nếu file cấu hình không tồn tại... |
| 53 | <code>        return</code> | ...thoát im lặng; có thể người dùng đã đặt biến môi trường bên ngoài. |
| 54 | <code>    for raw_line in path.read_text(encoding=&quot;utf-8&quot;).splitlines():</code> | Đọc UTF-8, tách thành các dòng và duyệt từng dòng. |
| 55 | <code>        line = raw_line.strip()</code> | Bỏ khoảng trắng ở đầu/cuối. |
| 56 | <code>        if not line or line.startswith(&quot;#&quot;) or &quot;=&quot; not in line:</code> | Bỏ dòng trống, comment bắt đầu # hoặc dòng không có dấu =. |
| 57 | <code>            continue</code> | Chuyển sang dòng kế tiếp khi không phải phép gán cấu hình. |
| 58 | <code>        name, value = line.split(&quot;=&quot;, 1)</code> | Tách ở dấu = đầu tiên, cho phép phần giá trị chứa dấu =. |
| 59 | <code>        name, value = name.strip(), value.strip().strip(&quot;\&quot;&quot;).strip(&quot;&#x27;&quot;)</code> | Làm sạch tên/giá trị và bỏ dấu nháy ở hai đầu theo cách đơn giản; không phải parser dotenv đầy đủ. |
| 60 | <code>        if name:</code> | Chỉ chấp nhận tên biến không rỗng. |
| 61 | <code>            os.environ.setdefault(name, value)</code> | setdefault chỉ đặt giá trị nếu tên chưa tồn tại trong môi trường. |
| 62 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 63 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 64 | <code>def graph_prompt_data(</code> | Hàm tạo phần dữ liệu graph nhỏ gọn cho prompt. |
| 65 | <code>    graph: dict[str, Any], start_region: str, goal_region: str</code> | Nhận graph đã chuẩn hóa và ID start/goal. |
| 66 | <code>) -&gt; dict[str, Any]:</code> | Trả một dictionary có thể json.dumps. |
| 67 | <code>    &quot;&quot;&quot;Build the compact, topology-constrained data sent to the model.&quot;&quot;&quot;</code> | Docstring: mô hình chỉ được chấm trên topology cung cấp. |
| 68 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 69 | <code>    return {</code> | Bắt đầu object dữ liệu prompt. |
| 70 | <code>        &quot;start_region&quot;: start_region,</code> | Gửi ID vùng bắt đầu. |
| 71 | <code>        &quot;goal_region&quot;: goal_region,</code> | Gửi ID vùng đích. |
| 72 | <code>        &quot;regions&quot;: [</code> | Bắt đầu danh sách thông tin các vùng. |
| 73 | <code>            {&quot;id&quot;: vertex[&quot;id&quot;], &quot;centroid&quot;: vertex[&quot;centroid&quot;]}</code> | Chỉ gửi id và centroid; polygon, occupancy map và kích thước robot không nằm trong record này. |
| 74 | <code>            for vertex in graph[&quot;vertices&quot;]</code> | Duyệt mọi vertex trong graph. |
| 75 | <code>        ],</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 76 | <code>        &quot;edges&quot;: [</code> | Bắt đầu danh sách cạnh gửi model. |
| 77 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 78 | <code>                &quot;source&quot;: edge[&quot;source&quot;],</code> | Gửi ID nguồn của cạnh có hướng. |
| 79 | <code>                &quot;target&quot;: edge[&quot;target&quot;],</code> | Gửi ID đích của cạnh có hướng. |
| 80 | <code>                &quot;relation&quot;: edge[&quot;relation&quot;],</code> | Gửi loại quan hệ hình học, ví dụ shared_edge. |
| 81 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 82 | <code>            for edge in graph[&quot;directed_edges&quot;]</code> | Duyệt directed_edges; không suy ra cạnh từ undirected_edges. |
| 83 | <code>        ],</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 84 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 85 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 86 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 87 | <code>class OpenRouterWeightProvider(LLMWeightProvider):</code> | Provider OpenRouter triển khai interface LLMWeightProvider. |
| 88 | <code>    &quot;&quot;&quot;OpenRouter Chat Completions provider using only configured models.</code> | Docstring: provider dùng model cấu hình, không tự chuyển model khi lỗi; có thể thay lớp provider mà giữ graph search. |
| 89 | <code>&nbsp;</code> | Docstring: provider dùng model cấu hình, không tự chuyển model khi lỗi; có thể thay lớp provider mà giữ graph search. |
| 90 | <code>    The rest of the planner depends only on ``LLMWeightProvider``, so a future</code> | Docstring: provider dùng model cấu hình, không tự chuyển model khi lỗi; có thể thay lớp provider mà giữ graph search. |
| 91 | <code>    API or fine-tuned-model adapter does not affect graph search.  This class</code> | Docstring: provider dùng model cấu hình, không tự chuyển model khi lỗi; có thể thay lớp provider mà giữ graph search. |
| 92 | <code>    never changes models automatically, which prevents an accidental paid</code> | Docstring: provider dùng model cấu hình, không tự chuyển model khi lỗi; có thể thay lớp provider mà giữ graph search. |
| 93 | <code>    fallback.</code> | Docstring: provider dùng model cấu hình, không tự chuyển model khi lỗi; có thể thay lớp provider mà giữ graph search. |
| 94 | <code>    &quot;&quot;&quot;</code> | Docstring: provider dùng model cấu hình, không tự chuyển model khi lỗi; có thể thay lớp provider mà giữ graph search. |
| 95 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 96 | <code>    def __init__(</code> | Bắt đầu constructor cấu hình provider. |
| 97 | <code>        self,</code> | self là đối tượng đang được tạo. |
| 98 | <code>        prompt_path: Path,</code> | Đường dẫn file prompt bắt buộc. |
| 99 | <code>        api_key: str &#124; None = None,</code> | API key truyền trực tiếp là tùy chọn; thiếu sẽ đọc môi trường. |
| 100 | <code>        model: str &#124; None = None,</code> | Model truyền trực tiếp là tùy chọn. |
| 101 | <code>        base_url: str &#124; None = None,</code> | Base URL truyền trực tiếp là tùy chọn. |
| 102 | <code>        temperature: float &#124; None = None,</code> | Temperature tùy chọn; None nghĩa là lấy môi trường/mặc định. |
| 103 | <code>        timeout: float = 60.0,</code> | Timeout mỗi lần mở request mặc định 60 giây; không phải deadline toàn bộ planner. |
| 104 | <code>        debug_response_path: Path = Path(&quot;outputs/openrouter_invalid_response.txt&quot;),</code> | Đường dẫn lưu raw HTTP response sai định dạng phục vụ debug. |
| 105 | <code>    ) -&gt; None:</code> | Constructor không trả kết quả nghiệp vụ. |
| 106 | <code>        self.prompt_path = prompt_path</code> | Lưu đường dẫn prompt. |
| 107 | <code>        self.api_key = api_key or os.environ.get(&quot;OPENROUTER_API_KEY&quot;)</code> | Ưu tiên api_key có giá trị, nếu thiếu/rỗng thì lấy OPENROUTER_API_KEY. |
| 108 | <code>        self.model = (</code> | Bắt đầu lựa chọn model theo chuỗi ưu tiên. |
| 109 | <code>            model</code> | Ưu tiên model được truyền trực tiếp. |
| 110 | <code>            or os.environ.get(&quot;OPENROUTER_MODEL&quot;)</code> | Nếu không có thì thử biến OPENROUTER_MODEL. |
| 111 | <code>            or DEFAULT_OPENROUTER_MODEL</code> | Cuối cùng dùng DEFAULT_OPENROUTER_MODEL. |
| 112 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 113 | <code>        self.base_url = (</code> | Bắt đầu lựa chọn base URL. |
| 114 | <code>            base_url</code> | Ưu tiên base_url truyền trực tiếp. |
| 115 | <code>            or os.environ.get(&quot;OPENROUTER_BASE_URL&quot;)</code> | Nếu không có thì dùng biến OPENROUTER_BASE_URL. |
| 116 | <code>            or DEFAULT_OPENROUTER_BASE_URL</code> | Nếu vẫn thiếu thì dùng URL mặc định. |
| 117 | <code>        ).rstrip(&quot;/&quot;)</code> | Bỏ dấu / cuối URL để ghép endpoint không có dấu // dư. |
| 118 | <code>        configured_temperature: float &#124; str = (</code> | Tạo biến nhiệt độ cấu hình, có thể đang là float hoặc chuỗi từ môi trường. |
| 119 | <code>            temperature</code> | Chọn giá trị temperature truyền vào... |
| 120 | <code>            if temperature is not None</code> | ...nếu nó khác None. Kiểm tra này giữ được giá trị 0.0 hợp lệ, không dùng toán tử or. |
| 121 | <code>            else os.environ.get(</code> | Nếu không truyền thì đọc môi trường... |
| 122 | <code>                &quot;OPENROUTER_TEMPERATURE&quot;, str(DEFAULT_OPENROUTER_TEMPERATURE)</code> | ...dùng chuỗi của temperature mặc định khi biến không tồn tại. |
| 123 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 124 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 125 | <code>        try:</code> | Bắt lỗi chuyển đổi nhiệt độ sang số. |
| 126 | <code>            self.temperature = float(configured_temperature)</code> | float(...) chuyển chuỗi hoặc số thành float để đưa vào request JSON. |
| 127 | <code>        except (TypeError, ValueError) as exc:</code> | Bắt lỗi kiểu hoặc nội dung không thể đổi sang float. |
| 128 | <code>            raise LLMProviderError(</code> | Ném exception cấu hình LLM. |
| 129 | <code>                &quot;OPENROUTER_TEMPERATURE must be a numeric value between 0 and 2.&quot;</code> | Thông báo temperature phải là số trong [0,2]. |
| 130 | <code>            ) from exc</code> | Kết thúc exception và giữ nguyên nhân gốc bằng from exc. |
| 131 | <code>        if not 0.0 &lt;= self.temperature &lt;= 2.0:</code> | Kiểm tra miền [0,2]; NaN và vô cực cũng không vượt qua điều kiện này. |
| 132 | <code>            raise LLMProviderError(</code> | Ném lỗi temperature ngoài miền. |
| 133 | <code>                &quot;OPENROUTER_TEMPERATURE must be between 0 and 2.&quot;</code> | Nội dung lỗi khoảng giá trị temperature. |
| 134 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 135 | <code>        self.timeout = timeout</code> | Lưu timeout request. |
| 136 | <code>        self.debug_response_path = debug_response_path</code> | Lưu đường dẫn debug response. |
| 137 | <code>        if not self.api_key:</code> | Nếu API key thiếu/rỗng... |
| 138 | <code>            raise LLMProviderError(</code> | ...tạo lỗi cấu hình ngay, chưa gửi request. |
| 139 | <code>                &quot;OPENROUTER_API_KEY is not set. Create a key at &quot;</code> | Thông báo thiếu OPENROUTER_API_KEY. |
| 140 | <code>                &quot;https://openrouter.ai/keys and add it to the environment or .env file.&quot;</code> | Nối hướng dẫn vị trí cấu hình key vào lỗi; đây là chuỗi thông báo trong code. |
| 141 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 142 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 143 | <code>    def get_edge_weights(</code> | Phương thức public thực hiện tác vụ chấm cost cạnh. |
| 144 | <code>        self, graph: dict[str, Any], start_region: str, goal_region: str</code> | Nhận graph và ID start/goal. |
| 145 | <code>    ) -&gt; dict[str, Any]:</code> | Trả response dict để validator dùng tiếp. |
| 146 | <code>        template = self.prompt_path.read_text(encoding=&quot;utf-8&quot;)</code> | Đọc prompt template UTF-8 từ file. |
| 147 | <code>        prompt = template.rstrip() + &quot;\n\nINPUT GRAPH DATA:\n&quot; + json.dumps(</code> | Ghép template đã rstrip với nhãn và JSON graph. |
| 148 | <code>            graph_prompt_data(graph, start_region, goal_region), ensure_ascii=False</code> | Tạo payload graph nhỏ gọn, giữ Unicode trong JSON. |
| 149 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 150 | <code>        result, resolved_model = self._get_model_json(prompt)</code> | Gọi hàm dùng chung gửi request và parse JSON model. |
| 151 | <code>        return {</code> | Bắt đầu response chuẩn của provider weights. |
| 152 | <code>            &quot;provider_metadata&quot;: {</code> | Nhóm thông tin nguồn và cấu hình request. |
| 153 | <code>                &quot;provider&quot;: &quot;openrouter&quot;,</code> | Provider có tên openrouter. |
| 154 | <code>                &quot;requested_model&quot;: self.model,</code> | Model đã yêu cầu. |
| 155 | <code>                &quot;resolved_model&quot;: resolved_model,</code> | Model thực tế nếu được envelope báo về. |
| 156 | <code>                &quot;temperature&quot;: self.temperature,</code> | Temperature đã dùng. |
| 157 | <code>            },</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 158 | <code>            &quot;edge_weights&quot;: result.get(&quot;edge_weights&quot;),</code> | Lấy edge_weights từ JSON model; trường thiếu cho None và sẽ bị validator bác bỏ. |
| 159 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 160 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 161 | <code>    def _get_model_json(self, prompt: str) -&gt; tuple[dict[str, Any], str &#124; None]:</code> | Hàm dùng chung cho cả edge cost và region score, trả (JSON model, tên model thực tế). |
| 162 | <code>        &quot;&quot;&quot;Send one JSON-object prompt using the existing safe transport policy.&quot;&quot;&quot;</code> | Docstring mô tả gửi prompt yêu cầu JSON object. |
| 163 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 164 | <code>        request_body = {</code> | Khởi tạo body HTTP request dạng dict. |
| 165 | <code>            &quot;model&quot;: self.model,</code> | Đặt model cần gọi. |
| 166 | <code>            &quot;messages&quot;: [{&quot;role&quot;: &quot;user&quot;, &quot;content&quot;: prompt}],</code> | Gửi một message role=user chứa toàn bộ template và dữ liệu graph. |
| 167 | <code>            &quot;response_format&quot;: {&quot;type&quot;: &quot;json_object&quot;},</code> | Yêu cầu định dạng JSON object; vẫn cần parse và validation sau khi nhận. |
| 168 | <code>            &quot;stream&quot;: False,</code> | Yêu cầu response không streaming. |
| 169 | <code>            &quot;temperature&quot;: self.temperature,</code> | Đặt temperature cấu hình. |
| 170 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 171 | <code>        request = urllib.request.Request(</code> | Tạo HTTP Request của thư viện chuẩn urllib. |
| 172 | <code>            f&quot;{self.base_url}/chat/completions&quot;,</code> | Ghép endpoint /chat/completions vào base URL. |
| 173 | <code>            data=json.dumps(request_body).encode(&quot;utf-8&quot;),</code> | Serialize body thành JSON rồi encode UTF-8 thành bytes. |
| 174 | <code>            headers={</code> | Bắt đầu dictionary các HTTP header. |
| 175 | <code>                &quot;Authorization&quot;: f&quot;Bearer {self.api_key}&quot;,</code> | Header Authorization theo dạng Bearer kèm API key. |
| 176 | <code>                &quot;Content-Type&quot;: &quot;application/json&quot;,</code> | Khai báo body gửi đi là application/json. |
| 177 | <code>                &quot;Accept&quot;: &quot;application/json&quot;,</code> | Yêu cầu response JSON qua Accept. |
| 178 | <code>            },</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 179 | <code>            method=&quot;POST&quot;,</code> | Phương thức HTTP là POST. |
| 180 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 181 | <code>        for attempt in range(2):</code> | Tối đa hai lần thử tổng cộng: lần đầu và một retry. |
| 182 | <code>            try:</code> | Bắt lỗi được đánh dấu retryable của lớp transport. |
| 183 | <code>                payload = self._request_http_json(request)</code> | Gửi HTTP và parse lớp JSON envelope bên ngoài. |
| 184 | <code>                break</code> | Thành công thì thoát vòng retry ngay. |
| 185 | <code>            except _RetryableOpenRouterError as exc:</code> | Chỉ lỗi _RetryableOpenRouterError đi vào nhánh retry này. |
| 186 | <code>                if attempt == 0:</code> | Nếu đây là lần thử đầu... |
| 187 | <code>                    print(exc.retry_message)</code> | ...in lý do retry. |
| 188 | <code>                    continue</code> | ...chuyển sang lần thử thứ hai, không có sleep/backoff ở đây. |
| 189 | <code>                raise exc.error from exc</code> | Nếu lần thứ hai vẫn lỗi, ném lỗi LLM cuối cùng; không có lần thứ ba. |
| 190 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 191 | <code>        try:</code> | Bắt đầu lấy nội dung model từ envelope đã parse. |
| 192 | <code>            model_text = payload[&quot;choices&quot;][0][&quot;message&quot;][&quot;content&quot;]</code> | Đi vào choices[0].message.content; đây thường là một CHUỖI chứa JSON khác. |
| 193 | <code>        except (KeyError, IndexError, TypeError) as exc:</code> | Bắt thiếu key, choices rỗng hoặc cấu trúc sai kiểu. |
| 194 | <code>            raise LLMProviderError(</code> | Tạo lỗi envelope thiếu nội dung model. |
| 195 | <code>                &quot;OpenRouter response did not contain choices[0].message.content&quot;</code> | Mô tả đường dẫn field bắt buộc trong response. |
| 196 | <code>            ) from exc</code> | Giữ nguyên nhân cấu trúc sai qua from exc. |
| 197 | <code>        if not isinstance(model_text, str):</code> | Nội dung model phải là string để parse JSON lần hai. |
| 198 | <code>            raise LLMProviderError(&quot;OpenRouter model content must be a JSON string&quot;)</code> | Báo lỗi nếu content là null/list/kiểu khác. |
| 199 | <code>        try:</code> | Bắt lỗi parse JSON của nội dung model. |
| 200 | <code>            result = json.loads(model_text)</code> | Parse lớp JSON thứ hai bên trong content. |
| 201 | <code>        except json.JSONDecodeError as exc:</code> | Bắt nội dung model không phải JSON đúng cú pháp. |
| 202 | <code>            raise LLMProviderError(f&quot;LLM model content returned invalid JSON: {exc}&quot;) from exc</code> | Báo lỗi model JSON; bước này nằm ngoài vòng retry nên không tự retry. |
| 203 | <code>        if not isinstance(result, dict):</code> | JSON model bắt buộc là object/dict. |
| 204 | <code>            raise LLMProviderError(&quot;LLM model content must decode to a JSON object&quot;)</code> | Từ chối JSON model là list, số hoặc null. |
| 205 | <code>        resolved_model = payload.get(&quot;model&quot;)</code> | Đọc tên model thực tế từ envelope ngoài. |
| 206 | <code>        if not isinstance(resolved_model, str):</code> | Nếu tên model không phải chuỗi... |
| 207 | <code>            resolved_model = None</code> | ...chuẩn hóa thành None. |
| 208 | <code>        return result, resolved_model</code> | Trả nội dung JSON model và resolved_model. |
| 209 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 210 | <code>    def _request_http_json(self, request: urllib.request.Request) -&gt; dict[str, Any]:</code> | Hàm transport gửi request, kiểm tra lỗi HTTP/bytes và parse JSON envelope. |
| 211 | <code>        try:</code> | Bắt đầu phạm vi xử lý lỗi mạng và HTTP. |
| 212 | <code>            with urllib.request.urlopen(request, timeout=self.timeout) as response:</code> | Mở request với timeout; context manager đóng response khi rời khối. |
| 213 | <code>                status = getattr(response, &quot;status&quot;, None)</code> | Thử đọc thuộc tính status, dùng None nếu response không có. |
| 214 | <code>                if status is None:</code> | Nếu chưa lấy được status... |
| 215 | <code>                    status = response.getcode()</code> | ...dùng phương thức getcode() dự phòng. |
| 216 | <code>                headers = getattr(response, &quot;headers&quot;, None)</code> | Lấy headers nếu có. |
| 217 | <code>                content_type = (</code> | Bắt đầu đọc content type. |
| 218 | <code>                    headers.get(&quot;Content-Type&quot;) if headers else None</code> | Lấy Content-Type từ headers nếu headers tồn tại. |
| 219 | <code>                ) or &quot;unknown&quot;</code> | Thiếu hoặc rỗng thì gán unknown cho thông báo debug. |
| 220 | <code>                try:</code> | Bắt riêng trường hợp body bị đọc thiếu. |
| 221 | <code>                    raw_body = response.read()</code> | Đọc toàn bộ response body thành bytes. |
| 222 | <code>                except http.client.IncompleteRead as exc:</code> | Bắt IncompleteRead: kết nối/body bị cắt ngắn trong quá trình đọc. |
| 223 | <code>                    raw_body = exc.partial</code> | Giữ phần bytes nhận được để không mất chứng cứ debug. |
| 224 | <code>                    error = self._invalid_http_json_error(</code> | Tạo lỗi chi tiết và lưu raw response. |
| 225 | <code>                        status, content_type, raw_body, exc</code> | Truyền status, kiểu nội dung, bytes còn giữ được và exception gốc. |
| 226 | <code>                    )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 227 | <code>                    raise _RetryableOpenRouterError(</code> | Bọc lỗi đọc thiếu thành lỗi retryable. |
| 228 | <code>                        error,</code> | Mang theo lỗi người dùng sẽ thấy nếu retry thất bại. |
| 229 | <code>                        &quot;Retrying OpenRouter request once because the response was malformed...&quot;,</code> | Thông báo sẽ thử lại một lần vì response bị hỏng. |
| 230 | <code>                    ) from exc</code> | Kết thúc tạo exception có liên kết nguyên nhân gốc. |
| 231 | <code>        except urllib.error.HTTPError as exc:</code> | Bắt HTTPError trước URLError vì HTTPError thuộc họ lỗi urllib. |
| 232 | <code>            detail = exc.read().decode(&quot;utf-8&quot;, errors=&quot;replace&quot;)</code> | Đọc body lỗi, thay byte UTF-8 hỏng bằng ký tự thay thế thay vì lỗi decode tiếp. |
| 233 | <code>            error = self._http_error(exc.code, detail)</code> | Chuyển status và detail thành lỗi mô tả phù hợp. |
| 234 | <code>            if 500 &lt;= exc.code &lt;= 599:</code> | Chỉ status 500..599 ở nhánh HTTP được retry. |
| 235 | <code>                raise _RetryableOpenRouterError(</code> | Tạo tín hiệu retry cho lỗi server. |
| 236 | <code>                    error,</code> | Kèm exception LLM đã mô tả. |
| 237 | <code>                    f&quot;Retrying OpenRouter request once after transient HTTP {exc.code}...&quot;,</code> | Thông báo status 5xx làm phát sinh retry. |
| 238 | <code>                ) from exc</code> | Ném retryable exception kèm nguyên nhân HTTP. |
| 239 | <code>            raise error from exc</code> | Với HTTP không phải 5xx, ném lỗi ngay; 401/403/429 không retry. |
| 240 | <code>        except _RetryableOpenRouterError:</code> | Nếu lỗi đã được bọc retryable trong khối read... |
| 241 | <code>            raise</code> | ...ném lại nguyên vẹn để vòng ngoài quyết định retry. |
| 242 | <code>        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:</code> | Bắt lỗi URL/network, timeout và connection reset được liệt kê. |
| 243 | <code>            safe_error = self._redact_text(str(exc))</code> | Redact API key nếu chuỗi lỗi mạng chứa chính xác key. |
| 244 | <code>            error = LLMProviderError(f&quot;OpenRouter network error: {safe_error}&quot;)</code> | Tạo exception LLM mô tả lỗi mạng đã che key. |
| 245 | <code>            raise _RetryableOpenRouterError(</code> | Bọc lỗi mạng để cho phép một retry. |
| 246 | <code>                error,</code> | Đưa exception cuối cùng vào wrapper. |
| 247 | <code>                &quot;Retrying OpenRouter request once after a transient network error...&quot;,</code> | Đưa thông báo retry lỗi mạng vào wrapper. |
| 248 | <code>            ) from exc</code> | Ném wrapper có liên kết nguyên nhân mạng. |
| 249 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 250 | <code>        media_type = content_type.lower().split(&quot;;&quot;, 1)[0].strip()</code> | Chuẩn hóa Content-Type về chữ thường và bỏ phần tham số sau dấu ;. |
| 251 | <code>        if media_type == &quot;text/event-stream&quot; or raw_body.lstrip().startswith(b&quot;data:&quot;):</code> | Nhận diện SSE bằng media type hoặc tiền tố data: sau khi bỏ whitespace. |
| 252 | <code>            saved_path = self._save_debug_response(raw_body)</code> | Lưu raw response SSE để debug, có che API key. |
| 253 | <code>            raise LLMProviderError(</code> | SSE ngoài mong đợi là LLMProviderError thường, không retryable. |
| 254 | <code>                &quot;OpenRouter returned an unexpected streaming/SSE response even though &quot;</code> | Phần thông báo API trả stream ngoài mong đợi... |
| 255 | <code>                &quot;stream=false was requested.\n&quot;</code> | ...dù request đã đặt stream=false. |
| 256 | <code>                f&quot;HTTP status: {status}\n&quot;</code> | Đưa HTTP status vào thông báo. |
| 257 | <code>                f&quot;Content-Type: {content_type}\n&quot;</code> | Đưa Content-Type vào thông báo. |
| 258 | <code>                f&quot;Response bytes: {len(raw_body)}\n&quot;</code> | Đưa số bytes đã nhận vào thông báo. |
| 259 | <code>                f&quot;Raw response saved to {saved_path}&quot;</code> | Đưa đường dẫn raw response đã lưu vào thông báo. |
| 260 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 261 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 262 | <code>        try:</code> | Bắt lỗi decode UTF-8 và parse envelope. |
| 263 | <code>            decoded_body = raw_body.decode(&quot;utf-8&quot;)</code> | Decode bytes HTTP thành chuỗi Unicode UTF-8. |
| 264 | <code>            payload = json.loads(decoded_body)</code> | Parse chuỗi envelope thành object Python; chưa parse content của model. |
| 265 | <code>        except (UnicodeDecodeError, json.JSONDecodeError) as exc:</code> | Bắt lỗi byte không phải UTF-8 hoặc JSON envelope sai cú pháp. |
| 266 | <code>            error = self._invalid_http_json_error(status, content_type, raw_body, exc)</code> | Lưu raw response và tạo lỗi đầy đủ thông tin HTTP. |
| 267 | <code>            raise _RetryableOpenRouterError(</code> | Chuyển lỗi envelope thành tín hiệu retryable. |
| 268 | <code>                error,</code> | Kèm exception thông báo chi tiết. |
| 269 | <code>                &quot;Retrying OpenRouter request once because the response was malformed...&quot;,</code> | Thông báo sẽ retry một lần vì envelope sai định dạng. |
| 270 | <code>            ) from exc</code> | Ném wrapper kèm nguyên nhân parse. |
| 271 | <code>        if not isinstance(payload, dict):</code> | Kiểm tra envelope parse được nhưng có phải dict hay không. |
| 272 | <code>            error = self._invalid_http_json_error(</code> | Nếu là list/null/số: xây lỗi JSON envelope sai schema. |
| 273 | <code>                status,</code> | Cung cấp status cho thông báo debug. |
| 274 | <code>                content_type,</code> | Cung cấp Content-Type cho thông báo debug. |
| 275 | <code>                raw_body,</code> | Cung cấp bytes gốc để lưu debug. |
| 276 | <code>                ValueError(&quot;top-level HTTP JSON must be an object&quot;),</code> | Tạo nguyên nhân: JSON ngoài cùng phải là object. |
| 277 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 278 | <code>            raise _RetryableOpenRouterError(</code> | Bọc lỗi sai kiểu envelope để retry. |
| 279 | <code>                error,</code> | Giữ error đã tạo. |
| 280 | <code>                &quot;Retrying OpenRouter request once because the response was malformed...&quot;,</code> | Cung cấp thông báo retry envelope không đúng. |
| 281 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 282 | <code>        return payload</code> | Trả envelope dict hợp lệ để _get_model_json lấy content. |
| 283 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 284 | <code>    def _invalid_http_json_error(</code> | Hàm tạo exception mô tả HTTP JSON không dùng được; chưa tự raise tại đây. |
| 285 | <code>        self,</code> | self truy cập đường dẫn debug và API key để redact. |
| 286 | <code>        status: int &#124; str,</code> | Nhận HTTP status. |
| 287 | <code>        content_type: str,</code> | Nhận Content-Type. |
| 288 | <code>        raw_body: bytes,</code> | Nhận raw bytes đã đọc. |
| 289 | <code>        parse_error: Exception,</code> | Nhận exception giải thích decode/parse sai ở đâu. |
| 290 | <code>    ) -&gt; LLMProviderError:</code> | Trả một LLMProviderError object. |
| 291 | <code>        saved_path = self._save_debug_response(raw_body)</code> | Lưu bytes response qua hàm có che key. |
| 292 | <code>        return LLMProviderError(</code> | Bắt đầu dựng exception cuối cùng dành cho người dùng. |
| 293 | <code>            &quot;OpenRouter returned invalid HTTP JSON.\n&quot;</code> | Dòng mở đầu cho biết HTTP envelope JSON không hợp lệ. |
| 294 | <code>            f&quot;HTTP status: {status}\n&quot;</code> | Hiển thị status. |
| 295 | <code>            f&quot;Content-Type: {content_type}\n&quot;</code> | Hiển thị content type. |
| 296 | <code>            f&quot;Response bytes: {len(raw_body)}\n&quot;</code> | Hiển thị số bytes. |
| 297 | <code>            f&quot;JSON parsing error: {self._redact_text(str(parse_error))}\n&quot;</code> | Hiển thị parse error sau khi che key nếu có. |
| 298 | <code>            f&quot;Raw response saved to {saved_path}&quot;</code> | Hiển thị đường dẫn debug hoặc mô tả lỗi lưu file. |
| 299 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 300 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 301 | <code>    def _save_debug_response(self, raw_body: bytes) -&gt; str:</code> | Hàm lưu raw response và trả đường dẫn dạng string. |
| 302 | <code>        path = self.debug_response_path</code> | Lấy đường dẫn cấu hình. |
| 303 | <code>        try:</code> | Nếu lưu debug gặp lỗi, không để nó che mất lỗi HTTP chính. |
| 304 | <code>            path.parent.mkdir(parents=True, exist_ok=True)</code> | Tạo thư mục cha nếu chưa có. |
| 305 | <code>            path.write_bytes(self._redact_bytes(raw_body))</code> | Ghi bytes sau khi thay chính xác API key bằng [REDACTED]. |
| 306 | <code>            return str(path)</code> | Trả đường dẫn để gắn vào thông báo. |
| 307 | <code>        except OSError as exc:</code> | Bắt lỗi hệ thống file khi lưu debug. |
| 308 | <code>            return f&quot;{path} (save failed: {self._redact_text(str(exc))})&quot;</code> | Trả đường dẫn kèm thông tin save failed đã che key. |
| 309 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 310 | <code>    def _redact_text(self, value: str) -&gt; str:</code> | Hàm che key trong chuỗi text. |
| 311 | <code>        return value.replace(self.api_key, &quot;[REDACTED]&quot;) if self.api_key else value</code> | Nếu có key thì replace mọi lần xuất hiện đúng key; nếu không thì giữ nguyên. |
| 312 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 313 | <code>    def _redact_bytes(self, value: bytes) -&gt; bytes:</code> | Hàm che key trong bytes response. |
| 314 | <code>        if not self.api_key:</code> | Khi không có API key... |
| 315 | <code>            return value</code> | ...trả bytes nguyên trạng. |
| 316 | <code>        return value.replace(self.api_key.encode(&quot;utf-8&quot;), b&quot;[REDACTED]&quot;)</code> | Encode key sang bytes rồi thay bằng marker [REDACTED]. |
| 317 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 318 | <code>    def _http_error(self, status: int, detail: str) -&gt; LLMProviderError:</code> | Chuyển mã HTTP và nội dung lỗi thành LLMProviderError dễ đọc. |
| 319 | <code>        compact_detail = self._redact_text(&quot; &quot;.join(detail.split()))</code> | Gom whitespace thành một khoảng trắng và che key trước khi đưa detail ra ngoài. |
| 320 | <code>        suffix = f&quot; Details: {compact_detail}&quot; if compact_detail else &quot;&quot;</code> | Tạo phần Details chỉ khi detail không rỗng. |
| 321 | <code>        if status in (401, 403):</code> | Nhận diện lỗi xác thực/ủy quyền 401 hoặc 403. |
| 322 | <code>            return LLMProviderError(</code> | Tạo exception cho lỗi xác thực. |
| 323 | <code>                f&quot;OpenRouter authentication failed (HTTP {status}). Check OPENROUTER_API_KEY.{suffix}&quot;</code> | Thông báo kiểm tra OPENROUTER_API_KEY, thêm detail đã che key. |
| 324 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 325 | <code>        if status == 429:</code> | Nhận diện lỗi 429 do giới hạn request/quota. |
| 326 | <code>            return LLMProviderError(</code> | Tạo exception rate limit. |
| 327 | <code>                &quot;OpenRouter free-model rate limit reached (HTTP 429). Wait for the limit &quot;</code> | Thông báo của code gắn nhãn free-model và yêu cầu chờ... |
| 328 | <code>                f&quot;to reset; free services have restricted quotas.{suffix}&quot;</code> | ...đến khi quota hồi phục; đây là nội dung thông báo, không phải phép kiểm tra model có miễn phí không. |
| 329 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 330 | <code>        lowered_detail = compact_detail.lower()</code> | Đổi detail sang chữ thường để so khớp không phân biệt hoa/thường. |
| 331 | <code>        if status in (400, 422) and &quot;response_format&quot; in lowered_detail and any(</code> | Với 400/422, yêu cầu detail có response_format và thêm một từ mô tả không hỗ trợ. |
| 332 | <code>            word in lowered_detail for word in (&quot;unsupported&quot;, &quot;not support&quot;, &quot;invalid&quot;)</code> | any kiểm tra unsupported, not support hoặc invalid xuất hiện trong detail. |
| 333 | <code>        ):</code> | Kết thúc điều kiện nhiều dòng; dấu : mở thân khối điều kiện. |
| 334 | <code>            return LLMProviderError(</code> | Tạo exception model không hỗ trợ format yêu cầu. |
| 335 | <code>                f&quot;OpenRouter model &#x27;{self.model}&#x27; does not support &quot;</code> | Nêu model đang dùng... |
| 336 | <code>                &quot;response_format={\&quot;type\&quot;:\&quot;json_object\&quot;}. Choose a model that &quot;</code> | ...và cấu hình JSON object không được hỗ trợ... |
| 337 | <code>                f&quot;supports JSON output; no fallback model was attempted.{suffix}&quot;</code> | ...gợi ý tự chọn model hỗ trợ, không tự fallback. |
| 338 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 339 | <code>        unavailable_words = (&quot;model&quot;, &quot;unavailable&quot;, &quot;no endpoints&quot;, &quot;not found&quot;, &quot;provider&quot;)</code> | Tập từ khóa heuristic để nhận diện model/provider không khả dụng. |
| 340 | <code>        if status in (404, 502, 503) or (</code> | Xem 404, 502, 503 là không khả dụng hoặc xét thêm trường hợp 400... |
| 341 | <code>            status == 400 and any(word in compact_detail.lower() for word in unavailable_words)</code> | ...mà detail có ít nhất một từ khóa phía trên. |
| 342 | <code>        ):</code> | Kết thúc điều kiện nhiều dòng; dấu : mở thân khối điều kiện. |
| 343 | <code>            if self.model == &quot;openrouter/free&quot;:</code> | Phân biệt đang dùng router openrouter/free hay một model cụ thể. |
| 344 | <code>                guidance = (</code> | Bắt đầu thông báo hướng dẫn nếu router không khả dụng. |
| 345 | <code>                    &quot;Try again later or manually select another model whose ID ends in &quot;</code> | Gợi ý thử lại sau hoặc tự chọn model khác có ID kết thúc... |
| 346 | <code>                    &quot;&#x27;:free&#x27;.&quot;</code> | ...bằng :free. |
| 347 | <code>                )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 348 | <code>            else:</code> | Nhánh model cụ thể, khác openrouter/free. |
| 349 | <code>                guidance = &quot;To manually use the free-model router, set OPENROUTER_MODEL=openrouter/free.&quot;</code> | Gợi ý người dùng tự đổi OPENROUTER_MODEL; code không tự thay giá trị cấu hình. |
| 350 | <code>            return LLMProviderError(</code> | Tạo exception model không khả dụng. |
| 351 | <code>                f&quot;OpenRouter model &#x27;{self.model}&#x27; is unavailable (HTTP {status}). &quot;</code> | Nêu model và HTTP status. |
| 352 | <code>                f&quot;{guidance} No paid fallback was attempted.{suffix}&quot;</code> | Ghép hướng dẫn và khẳng định không có fallback trả phí tự động. |
| 353 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 354 | <code>        return LLMProviderError(f&quot;OpenRouter API returned HTTP {status}.{suffix}&quot;)</code> | Trường hợp chưa phân loại: trả lỗi HTTP tổng quát kèm detail. |
| 355 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 356 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 357 | <code>def parse_weight_response(response: str &#124; dict[str, Any]) -&gt; dict[str, Any]:</code> | Hàm chuẩn hóa response weights dạng chuỗi/dict và kiểm tra schema ngoài. |
| 358 | <code>    if isinstance(response, str):</code> | Nếu còn là chuỗi... |
| 359 | <code>        try:</code> | ...bắt lỗi JSON. |
| 360 | <code>            response = json.loads(response)</code> | Parse chuỗi JSON thành Python object. |
| 361 | <code>        except json.JSONDecodeError as exc:</code> | Bắt JSON sai cú pháp. |
| 362 | <code>            raise LLMProviderError(f&quot;LLM returned invalid JSON: {exc}&quot;) from exc</code> | Chuyển thành LLMProviderError và giữ nguyên nhân. |
| 363 | <code>    if not isinstance(response, dict):</code> | Kết quả phải là dict. |
| 364 | <code>        raise LLMProviderError(&quot;LLM response must be a JSON object&quot;)</code> | Sai kiểu object thì báo lỗi. |
| 365 | <code>    if not isinstance(response.get(&quot;edge_weights&quot;), list):</code> | edge_weights phải là list. |
| 366 | <code>        raise LLMProviderError(&quot;LLM response field &#x27;edge_weights&#x27; must be a list&quot;)</code> | Báo lỗi trường edge_weights thiếu/sai kiểu. |
| 367 | <code>    return response</code> | Trả dict sau khi kiểm tra lớp ngoài. |
| 368 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 369 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 370 | <code>def validate_edge_weights(</code> | Hàm validation topology và giá trị cost, sau đó bù cạnh thiếu. |
| 371 | <code>    response: str &#124; dict[str, Any],</code> | Response có thể là chuỗi JSON hoặc dict. |
| 372 | <code>    graph: dict[str, Any],</code> | Graph chuẩn hóa cung cấp topology có thẩm quyền. |
| 373 | <code>    missing_weight: float = NEUTRAL_MISSING_WEIGHT,</code> | Cost bù mặc định 0.5. Khác validator score vùng, hàm này chưa kiểm tra miền của missing_weight do người gọi tùy chỉnh. |
| 374 | <code>) -&gt; tuple[dict[tuple[str, str], float], list[tuple[str, str]]]:</code> | Trả dict key là tuple cạnh có hướng và list các cạnh được bù. |
| 375 | <code>    &quot;&quot;&quot;Validate topology and range; default only individually missing edges.&quot;&quot;&quot;</code> | Docstring: chỉ bù từng cạnh thiếu, không thay toàn response rỗng. |
| 376 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 377 | <code>    parsed = parse_weight_response(response)</code> | Parse và kiểm tra schema ngoài trước. |
| 378 | <code>    region_ids = {vertex[&quot;id&quot;] for vertex in graph[&quot;vertices&quot;]}</code> | Tập ID vùng thật trong graph. |
| 379 | <code>    valid_edges = {</code> | Tạo tập cạnh hợp lệ. |
| 380 | <code>        (edge[&quot;source&quot;], edge[&quot;target&quot;]) for edge in graph[&quot;directed_edges&quot;]</code> | Mỗi cạnh là cặp có thứ tự (source,target); A→B khác B→A. |
| 381 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 382 | <code>    weights: dict[tuple[str, str], float] = {}</code> | Bảng weights đã qua kiểm tra, ban đầu rỗng. |
| 383 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 384 | <code>    for index, item in enumerate(parsed[&quot;edge_weights&quot;]):</code> | Duyệt records cùng index để báo lỗi đúng vị trí. |
| 385 | <code>        if not isinstance(item, dict):</code> | Mỗi item phải là dict. |
| 386 | <code>            raise LLMProviderError(f&quot;edge_weights[{index}] must be an object&quot;)</code> | Báo record không phải object. |
| 387 | <code>        source, target, weight = item.get(&quot;source&quot;), item.get(&quot;target&quot;), item.get(&quot;weight&quot;)</code> | Đọc source, target và weight; trường thiếu cho None. |
| 388 | <code>        if not isinstance(source, str) or not isinstance(target, str):</code> | Hai đầu cạnh phải là chuỗi. |
| 389 | <code>            raise LLMProviderError(f&quot;edge_weights[{index}] needs string source and target&quot;)</code> | Báo sai kiểu source/target. |
| 390 | <code>        if source not in region_ids or target not in region_ids:</code> | Cả hai ID phải có trong graph. |
| 391 | <code>            raise LLMProviderError(f&quot;Weight references unknown region: {source}-&gt;{target}&quot;)</code> | Từ chối tham chiếu vùng không tồn tại. |
| 392 | <code>        key = (source, target)</code> | Tạo key tuple cho cạnh có hướng. |
| 393 | <code>        if key not in valid_edges:</code> | Cạnh phải thuộc directed_edges cung cấp. |
| 394 | <code>            raise LLMProviderError(f&quot;Weight references nonexistent edge: {source}-&gt;{target}&quot;)</code> | Từ chối LLM bịa cạnh, kể cả khi hai ID đều có thật. |
| 395 | <code>        if isinstance(weight, bool) or not isinstance(weight, (int, float)):</code> | Loại bool và mọi giá trị ngoài int/float; bool cần loại riêng vì isinstance(True,int) là True. |
| 396 | <code>            raise LLMProviderError(f&quot;Weight for {source}-&gt;{target} must be numeric&quot;)</code> | Báo cost không phải số hợp lệ. |
| 397 | <code>        numeric_weight = float(weight)</code> | Chuẩn hóa cost thành float. |
| 398 | <code>        if not 0.0 &lt; numeric_weight &lt;= 1.0:</code> | Yêu cầu 0 < cost ≤ 1; phép so sánh này cũng loại NaN và vô cực. |
| 399 | <code>            raise LLMProviderError(</code> | Tạo lỗi cost ngoài khoảng cho phép. |
| 400 | <code>                f&quot;Weight for {source}-&gt;{target}: Weight must be greater than 0 &quot;</code> | Nêu cạnh lỗi và yêu cầu cost lớn hơn 0... |
| 401 | <code>                &quot;and less than or equal to 1.&quot;</code> | ...đồng thời nhỏ hơn hoặc bằng 1. |
| 402 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 403 | <code>        if key in weights:</code> | Kiểm tra đã có cost cho đúng cạnh này chưa. |
| 404 | <code>            if weights[key] == numeric_weight:</code> | Nếu cost mới bằng chính xác cost cũ sau chuyển float... |
| 405 | <code>                warnings.warn(</code> | ...phát warning thay vì thất bại. |
| 406 | <code>                    f&quot;Ignored identical duplicate LLM edge-weight record for {source}-&gt;{target}.&quot;,</code> | Nội dung warning xác định cạnh bị lặp giống nhau. |
| 407 | <code>                    DuplicateEdgeWeightWarning,</code> | Category DuplicateEdgeWeightWarning để CLI gom và đếm. |
| 408 | <code>                    stacklevel=2,</code> | stacklevel=2 quy vị trí warning về caller validator. |
| 409 | <code>                )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 410 | <code>                continue</code> | Bỏ record trùng, giữ cost đầu tiên. |
| 411 | <code>            raise LLMProviderError(</code> | Nếu duplicate mà cost khác nhau thì tạo lỗi xung đột. |
| 412 | <code>                f&quot;Conflicting duplicate weights for {source}-&gt;{target}: &quot;</code> | Nội dung chỉ rõ cạnh đang có hai giá trị... |
| 413 | <code>                f&quot;{weights[key]} and {numeric_weight}&quot;</code> | ...và in cả cost cũ lẫn cost mới; không tự lấy trung bình/min/max. |
| 414 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 415 | <code>        weights[key] = numeric_weight</code> | Ghi cost đã validate vào bảng. |
| 416 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 417 | <code>    if valid_edges and not weights:</code> | Nếu topology có cạnh nhưng không nhận được cost nào... |
| 418 | <code>        raise LLMProviderError(&quot;LLM response contains no usable edge weights&quot;)</code> | ...từ chối response rỗng, không tự tạo tuyến hoàn toàn mặc định. |
| 419 | <code>    missing = sorted(valid_edges - weights.keys())</code> | Hiệu tập hợp tìm cạnh thiếu; sorted tạo thứ tự xác định cho danh sách missing. |
| 420 | <code>    for key in missing:</code> | Duyệt mỗi cạnh thiếu. |
| 421 | <code>        weights[key] = missing_weight</code> | Gán missing_weight, mặc định 0.5. |
| 422 | <code>    return weights, missing</code> | Trả weights đầy đủ và danh sách đã bù để CLI cảnh báo. |
