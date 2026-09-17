# Giải thích từng dòng: llm_planner.py

Nhánh cost cạnh: graph + response/provider → validate → Dijkstra → route.json và route.svg. Cost càng thấp càng được ưu tiên. Route chứa ID vùng, chưa chứa đường liên tục. Dijkstra được import từ weighted_search.py.

Nguồn: [llm_planner.py](/Users/nguyen/BK/SEM7/DACN/Motion_Planner/convex-region-graph/llm_planner.py). Số dòng khớp bản đọc ngày 17/09/2026 (130 dòng). Code nguồn không bị sửa.

Bảng giữ cả dòng trống và dấu đóng/mở để bạn đối chiếu không bị lệch số dòng. Với một câu lệnh xuống nhiều dòng, đọc các dòng liền nhau như một biểu thức.

| Dòng | Code gốc | Giải thích tiếng Việt |
| --- | --- | --- |
| 1 | <code>#!/usr/bin/env python3</code> | Chỉ dẫn chạy file bằng python3 khi thực thi trực tiếp. |
| 2 | <code>&quot;&quot;&quot;Assign LLM edge costs and find a valid directed region sequence.&quot;&quot;&quot;</code> | Docstring: gán chi phí cạnh bằng LLM rồi tìm chuỗi vùng hợp lệ trên graph có hướng. |
| 3 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 4 | <code>from __future__ import annotations</code> | Hoãn đánh giá type annotation; các chú thích kiểu hỗ trợ đọc code/tooling, không tự validate dữ liệu lúc chạy. |
| 5 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 6 | <code>import argparse</code> | Import bộ phân tích đối số dòng lệnh của thư viện chuẩn. |
| 7 | <code>import json</code> | Import JSON encoder/decoder để chuyển giữa chuỗi JSON và object Python. |
| 8 | <code>import sys</code> | Import sys để ghi lỗi vào stderr và làm việc với tiến trình. |
| 9 | <code>import warnings</code> | Import hệ thống cảnh báo; warning có thể được ghi nhận mà không dừng chương trình. |
| 10 | <code>from pathlib import Path</code> | Import lớp Path biểu diễn đường dẫn và thao tác đọc/ghi file/thư mục. |
| 11 | <code>from typing import Any</code> | Any là chú thích kiểu linh hoạt cho dữ liệu JSON có nhiều kiểu giá trị. |
| 12 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 13 | <code>from graph_utils import load_json_object, prepare_planning_graph, require_region</code> | Import ba hàm đọc JSON, kiểm tra graph và kiểm tra ID start/goal. |
| 14 | <code>from llm_weight_provider import (</code> | Bắt đầu import các thành phần của lớp provider và validator. |
| 15 | <code>    DuplicateEdgeWeightWarning,</code> | Loại cảnh báo khi LLM lặp cạnh với đúng cùng trọng số. |
| 16 | <code>    LLMProviderError,</code> | Loại exception chung cho lỗi provider/response LLM. |
| 17 | <code>    LLMWeightProvider,</code> | Interface trừu tượng giúp planner không phụ thuộc trực tiếp một API cụ thể. |
| 18 | <code>    OpenRouterWeightProvider,</code> | Provider cụ thể gọi OpenRouter. |
| 19 | <code>    load_dotenv,</code> | Hàm đọc biến cấu hình từ file .env. |
| 20 | <code>    validate_edge_weights,</code> | Validator kiểm tra cạnh và trọng số, đồng thời bổ sung các cạnh bị thiếu. |
| 21 | <code>)</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 22 | <code>from route_visualization import route_svg</code> | Import hàm sinh SVG biểu diễn route và weights. |
| 23 | <code>from weighted_search import dijkstra_region_path</code> | Import thuật toán Dijkstra; thuật toán không được triển khai trong file này. |
| 24 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 25 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 26 | <code>def plan_route(</code> | Hàm nghiệp vụ plan_route: kiểm tra đầu vào, lấy weights và tìm route. |
| 27 | <code>    raw_graph: dict[str, Any],</code> | raw_graph là graph JSON chưa qua prepare_planning_graph. |
| 28 | <code>    start_region: str,</code> | ID vùng bắt đầu, kiểu chuỗi. |
| 29 | <code>    goal_region: str,</code> | ID vùng đích, kiểu chuỗi. |
| 30 | <code>    weight_response: dict[str, Any] &#124; None = None,</code> | Có thể truyền response có sẵn; None nghĩa là cần gọi provider. |
| 31 | <code>    provider: LLMWeightProvider &#124; None = None,</code> | Provider là tùy chọn nếu đã có weight_response. |
| 32 | <code>) -&gt; tuple[dict[str, Any], dict[str, Any], dict[tuple[str, str], float], list[tuple[str, str]]]:</code> | Kiểu trả về gồm route, graph chuẩn hóa, bảng (source,target)→weight và danh sách cạnh thiếu. |
| 33 | <code>    graph = prepare_planning_graph(raw_graph)</code> | Kiểm tra/copy graph và chỉ dùng directed_edges làm topology lập kế hoạch. |
| 34 | <code>    require_region(graph, start_region, &quot;start&quot;)</code> | Kiểm tra start_region tồn tại. |
| 35 | <code>    require_region(graph, goal_region, &quot;goal&quot;)</code> | Kiểm tra goal_region tồn tại. |
| 36 | <code>    if weight_response is None:</code> | Chỉ gọi API nếu người gọi chưa cung cấp response. |
| 37 | <code>        if provider is None:</code> | Nếu không có response thì cần provider. |
| 38 | <code>            raise LLMProviderError(&quot;A weight response or LLM provider is required&quot;)</code> | Thiếu cả hai nguồn dữ liệu: dừng bằng lỗi rõ ràng. |
| 39 | <code>        weight_response = provider.get_edge_weights(graph, start_region, goal_region)</code> | Gọi interface provider lấy response weights đã parse JSON, chưa validation nghiệp vụ. |
| 40 | <code>    weights, missing = validate_edge_weights(weight_response, graph)</code> | Kiểm tra weights; cạnh thiếu riêng lẻ được mặc định 0.5. |
| 41 | <code>    route = dijkstra_region_path(graph, weights, start_region, goal_region)</code> | Dijkstra tối thiểu hóa tổng weights trên graph có hướng; chưa tạo đường hình học cho robot. |
| 42 | <code>    return route, graph, weights, missing</code> | Trả bốn kết quả cho bên gọi sử dụng/ghi file/hiển thị. |
| 43 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 44 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 45 | <code>def parse_args(argv: list[str] &#124; None = None) -&gt; argparse.Namespace:</code> | Định nghĩa parser; argv=None dùng đối số tiến trình, truyền list tiện cho test. |
| 46 | <code>    parser = argparse.ArgumentParser(description=__doc__)</code> | Tạo parser với mô tả lấy từ docstring module. |
| 47 | <code>    parser.add_argument(&quot;graph&quot;, type=Path, help=&quot;GCR JSON file&quot;)</code> | Tham số vị trí graph: đường dẫn JSON. |
| 48 | <code>    parser.add_argument(&quot;--start&quot;, required=True, help=&quot;Start region ID&quot;)</code> | Bắt buộc --start là ID vùng. |
| 49 | <code>    parser.add_argument(&quot;--goal&quot;, required=True, help=&quot;Goal region ID&quot;)</code> | Bắt buộc --goal là ID vùng. |
| 50 | <code>    parser.add_argument(&quot;--provider&quot;, choices=[&quot;openrouter&quot;], default=&quot;openrouter&quot;)</code> | CLI hiện chỉ cho phép provider openrouter; chưa có lựa chọn API khác. |
| 51 | <code>    parser.add_argument(&quot;--weights&quot;, type=Path, help=&quot;Reuse a JSON weight response; skips the API&quot;)</code> | --weights chỉ định response đã lưu; có nó thì bỏ qua API. |
| 52 | <code>    parser.add_argument(&quot;--weights-output&quot;, type=Path, default=Path(&quot;outputs/llm_weights.json&quot;))</code> | Đường dẫn lưu response mới từ API; không phải bảng weights đã bù thiếu. |
| 53 | <code>    parser.add_argument(&quot;--route-output&quot;, type=Path, default=Path(&quot;outputs/route.json&quot;))</code> | Đường dẫn route JSON đầu ra. |
| 54 | <code>    parser.add_argument(&quot;--svg-output&quot;, type=Path, default=Path(&quot;outputs/route.svg&quot;))</code> | Đường dẫn SVG minh họa route. |
| 55 | <code>    parser.add_argument(&quot;--prompt&quot;, type=Path, default=Path(__file__).parent / &quot;prompts&quot; / &quot;edge_weight_prompt.txt&quot;)</code> | Prompt mặc định tìm tương đối với chính file Python, không phụ thuộc cwd. |
| 56 | <code>    parser.add_argument(&quot;--env-file&quot;, type=Path, default=Path(&quot;.env&quot;))</code> | .env mặc định tìm theo thư mục đang chạy, khác cách định vị prompt ở trên. |
| 57 | <code>    return parser.parse_args(argv)</code> | Parse đối số và trả Namespace. |
| 58 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 59 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 60 | <code>def main(argv: list[str] &#124; None = None) -&gt; int:</code> | Hàm CLI trả exit code cho tiến trình. |
| 61 | <code>    args = parse_args(argv)</code> | Parse tham số trước try; lỗi argparse tự kết thúc theo cơ chế của argparse. |
| 62 | <code>    try:</code> | Bắt đầu khối xử lý có chuyển exception thường gặp thành exit code 1. |
| 63 | <code>        print(&quot;Loading GCR...&quot;)</code> | In trạng thái đang nạp graph. |
| 64 | <code>        raw_graph = load_json_object(args.graph)</code> | Đọc JSON object từ file. |
| 65 | <code>        graph = prepare_planning_graph(raw_graph)</code> | Kiểm tra cấu trúc graph trước khi gọi provider. |
| 66 | <code>        print(f&quot;\nStart region: {args.start}\nGoal region: {args.goal}\n&quot;)</code> | In các ID start và goal. |
| 67 | <code>        print(f&quot;Directed edges loaded: {len(graph[&#x27;directed_edges&#x27;])}\n&quot;)</code> | In số cạnh có hướng thật sự dùng cho lập kế hoạch. |
| 68 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 69 | <code>        provider = None</code> | Khởi tạo provider=None cho nhánh offline. |
| 70 | <code>        if args.weights:</code> | Có đường dẫn weights thì chọn chạy offline. |
| 71 | <code>            print(f&quot;Reusing weights from {args.weights}; API call skipped.&quot;)</code> | Thông báo rõ không gọi API. |
| 72 | <code>            response = load_json_object(args.weights)</code> | Đọc response weights từ JSON đã lưu. |
| 73 | <code>        else:</code> | Nếu không có weights file thì chuyển sang nhánh gọi API. |
| 74 | <code>            load_dotenv(args.env_file)</code> | Nạp .env nhưng không ghi đè biến môi trường đã có. |
| 75 | <code>            print(&quot;Calling LLM API...&quot;)</code> | In trạng thái sắp gọi API. |
| 76 | <code>            provider = OpenRouterWeightProvider(args.prompt)</code> | Tạo provider, đọc cấu hình model/key/temperature và đường dẫn prompt. |
| 77 | <code>            response = provider.get_edge_weights(graph, args.start, args.goal)</code> | Gọi API ngay tại đây. Trong CLI edge mode, kiểm tra ID start/goal nằm ở plan_route phía sau nên ID sai vẫn có thể dẫn tới một request trước khi bị chặn. |
| 78 | <code>            metadata = response.get(&quot;provider_metadata&quot;, {})</code> | Lấy metadata nếu có, mặc định dict rỗng. |
| 79 | <code>            requested_model = metadata.get(&quot;requested_model&quot;) or provider.model</code> | Lấy model đã yêu cầu, dự phòng bằng thuộc tính provider.model. |
| 80 | <code>            print(f&quot;Requested model: {requested_model}&quot;)</code> | In model đã yêu cầu. |
| 81 | <code>            resolved_model = metadata.get(&quot;resolved_model&quot;)</code> | Lấy model thực tế được API báo về. |
| 82 | <code>            if resolved_model:</code> | Chỉ in resolved_model khi có giá trị. |
| 83 | <code>                print(f&quot;Resolved model: {resolved_model}&quot;)</code> | In model thực tế, có thể khác tên router yêu cầu. |
| 84 | <code>            args.weights_output.parent.mkdir(parents=True, exist_ok=True)</code> | Tạo thư mục chứa bản lưu response. |
| 85 | <code>            args.weights_output.write_text(</code> | Bắt đầu ghi response API trước khi validate weights nghiệp vụ. |
| 86 | <code>                json.dumps(response, indent=2, ensure_ascii=False) + &quot;\n&quot;, encoding=&quot;utf-8&quot;</code> | Serialize response gồm metadata, giữ Unicode và định dạng dễ đọc. |
| 87 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 88 | <code>            print(f&quot;Saved LLM response to {args.weights_output}&quot;)</code> | In nơi đã lưu response để có thể chạy lại offline. |
| 89 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 90 | <code>        with warnings.catch_warnings(record=True) as caught_warnings:</code> | Thu warnings vào list trong phạm vi gọi plan_route. |
| 91 | <code>            warnings.simplefilter(&quot;always&quot;, DuplicateEdgeWeightWarning)</code> | Luôn ghi nhận cảnh báo cạnh lặp giống nhau, không bỏ qua vì bộ lọc mặc định. |
| 92 | <code>            route, graph, weights, missing = plan_route(</code> | Gọi hàm nghiệp vụ và nhận route, graph, bảng weights, danh sách thiếu. |
| 93 | <code>                raw_graph, args.start, args.goal, weight_response=response, provider=provider</code> | Truyền response đã có nên plan_route sẽ không gọi API lần thứ hai. |
| 94 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 95 | <code>        duplicate_count = sum(</code> | Đếm số cảnh báo cạnh lặp bằng tổng các giá trị boolean. |
| 96 | <code>            issubclass(item.category, DuplicateEdgeWeightWarning)</code> | True nếu category của warning là DuplicateEdgeWeightWarning hoặc lớp con. |
| 97 | <code>            for item in caught_warnings</code> | Duyệt các warning đã thu được. |
| 98 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 99 | <code>        if duplicate_count:</code> | Chỉ thông báo số bản ghi trùng nếu có ít nhất một warning phù hợp. |
| 100 | <code>            noun = &quot;record&quot; if duplicate_count == 1 else &quot;records&quot;</code> | Chọn từ record/records theo số lượng để log đúng ngữ pháp. |
| 101 | <code>            print(</code> | Bắt đầu in thông báo bỏ qua bản ghi trùng. |
| 102 | <code>                f&quot;Warning: ignored {duplicate_count} identical duplicate &quot;</code> | Nội dung log gồm số bản ghi trùng giống hệt nhau. |
| 103 | <code>                f&quot;LLM edge-weight {noun}.&quot;</code> | Nối phần cuối thông báo; hai literal cạnh nhau được Python nối tự động. |
| 104 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 105 | <code>        print(f&quot;\nValidated weights for {len(weights)} directed edges.&quot;)</code> | In số cạnh đã có weight sau khi bổ sung mặc định. |
| 106 | <code>        if missing:</code> | Nếu tồn tại các cạnh bị bỏ sót... |
| 107 | <code>            print(f&quot;Warning: assigned neutral weight 0.5 to {len(missing)} missing edges.&quot;)</code> | ...in số cạnh nhận cost trung lập 0.5. |
| 108 | <code>        print(&quot;Running Dijkstra...\n&quot;)</code> | Log ghi Running Dijkstra nhưng Dijkstra thực tế đã chạy ở dòng 41 trong lời gọi dòng 92. |
| 109 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 110 | <code>        args.route_output.parent.mkdir(parents=True, exist_ok=True)</code> | Tạo thư mục chứa route JSON. |
| 111 | <code>        args.route_output.write_text(</code> | Bắt đầu ghi route. |
| 112 | <code>            json.dumps(route, indent=2, ensure_ascii=False) + &quot;\n&quot;, encoding=&quot;utf-8&quot;</code> | Encode route dict thành JSON đẹp rồi ghi UTF-8. |
| 113 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 114 | <code>        args.svg_output.parent.mkdir(parents=True, exist_ok=True)</code> | Tạo thư mục chứa SVG route. |
| 115 | <code>        args.svg_output.write_text(route_svg(graph, weights, route), encoding=&quot;utf-8&quot;)</code> | Vẽ topology, trọng số và tuyến được chọn; ghi SVG. |
| 116 | <code>        if route[&quot;valid&quot;]:</code> | Phân nhánh theo việc graph search có tìm được đường hay không. |
| 117 | <code>            print(&quot;Selected region sequence:\n&quot;)</code> | In tiêu đề chuỗi vùng đã chọn. |
| 118 | <code>            print(&quot; -&gt; &quot;.join(route[&quot;sequence&quot;]))</code> | Ghép các ID bằng mũi tên để dễ đọc. |
| 119 | <code>            print(f&quot;\nTotal LLM cost: {route[&#x27;total_cost&#x27;]}&quot;)</code> | In tổng chi phí LLM; giá trị này không có đơn vị mét. |
| 120 | <code>        else:</code> | Nhánh graph không có đường có hướng từ start tới goal. |
| 121 | <code>            print(route[&quot;reason&quot;])</code> | In lý do thất bại từ route record. |
| 122 | <code>        print(f&quot;Route JSON: {args.route_output}\nRoute SVG:  {args.svg_output}&quot;)</code> | In đường dẫn hai artifact đã ghi. |
| 123 | <code>        return 0 if route[&quot;valid&quot;] else 2</code> | Exit code 0 khi có route, 2 khi đầu vào hợp lệ nhưng không có đường. |
| 124 | <code>    except (OSError, ValueError, LLMProviderError) as exc:</code> | Bắt lỗi file, dữ liệu và provider; không phải bắt mọi exception có thể có. |
| 125 | <code>        print(f&quot;Error: {exc}&quot;, file=sys.stderr)</code> | In thông báo lỗi vào stderr. |
| 126 | <code>        return 1</code> | Exit code 1 cho lỗi nạp/xử lý/gọi API. |
| 127 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 128 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 129 | <code>if __name__ == &quot;__main__&quot;:</code> | Chỉ chạy CLI nếu file là chương trình chính. |
| 130 | <code>    raise SystemExit(main())</code> | Gọi main và dùng giá trị trả về làm exit status của tiến trình. |
