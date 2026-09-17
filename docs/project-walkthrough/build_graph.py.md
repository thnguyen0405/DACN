# Giải thích từng dòng: build_graph.py

Đầu vào: các polygon lồi. Đầu ra: graph.json và graph.svg. Trọng tâm là hình học giao nhau, không có LLM và không chạy RRT. Thứ tự đọc: main → build_graph → normalize_polygon/intersection_relation → các phép toán hình học. Các hàm chỉ được định nghĩa lúc import; thân hàm chạy khi được gọi.

Nguồn: [build_graph.py](/Users/nguyen/BK/SEM7/DACN/Motion_Planner/convex-region-graph/build_graph.py). Số dòng khớp bản đọc ngày 17/09/2026 (339 dòng). Code nguồn không bị sửa.

Bảng giữ cả dòng trống và dấu đóng/mở để bạn đối chiếu không bị lệch số dòng. Với một câu lệnh xuống nhiều dòng, đọc các dòng liền nhau như một biểu thức.

| Dòng | Code gốc | Giải thích tiếng Việt |
| --- | --- | --- |
| 1 | <code>#!/usr/bin/env python3</code> | Chỉ dẫn hệ điều hành chạy script bằng python3 khi thực thi trực tiếp. |
| 2 | <code>&quot;&quot;&quot;Build a Graph of Convex Regions from 2D convex polygons.</code> | Docstring: mô tả xây graph từ các đa giác lồi 2D, chỉ dùng thư viện chuẩn. |
| 3 | <code>&nbsp;</code> | Docstring: mô tả xây graph từ các đa giác lồi 2D, chỉ dùng thư viện chuẩn. |
| 4 | <code>The implementation intentionally uses only the Python standard library so the</code> | Docstring: mô tả xây graph từ các đa giác lồi 2D, chỉ dùng thư viện chuẩn. |
| 5 | <code>demo is easy to run on a clean machine.</code> | Docstring: mô tả xây graph từ các đa giác lồi 2D, chỉ dùng thư viện chuẩn. |
| 6 | <code>&quot;&quot;&quot;</code> | Docstring: mô tả xây graph từ các đa giác lồi 2D, chỉ dùng thư viện chuẩn. |
| 7 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 8 | <code>from __future__ import annotations</code> | Hoãn đánh giá type annotation; các chú thích kiểu hỗ trợ đọc code/tooling, không tự validate dữ liệu lúc chạy. |
| 9 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 10 | <code>import argparse</code> | Import bộ phân tích đối số dòng lệnh của thư viện chuẩn. |
| 11 | <code>import json</code> | Import JSON encoder/decoder để chuyển giữa chuỗi JSON và object Python. |
| 12 | <code>import math</code> | Import các phép toán như hypot và isfinite phục vụ hình học/kiểm tra số. |
| 13 | <code>from collections import deque</code> | Import hàng đợi hai đầu deque; BFS dùng popleft để lấy phần tử đầu hiệu quả. |
| 14 | <code>from pathlib import Path</code> | Import lớp Path biểu diễn đường dẫn và thao tác đọc/ghi file/thư mục. |
| 15 | <code>from typing import Iterable</code> | Import kiểu chú thích Iterable, chỉ đầu vào có thể duyệt được. |
| 16 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 17 | <code>Point = tuple[float, float]</code> | Đặt bí danh Point cho tuple gồm hai số thực (x, y); không tạo lớp hình học mới. |
| 18 | <code>Polygon = list[Point]</code> | Polygon là danh sách các Point theo thứ tự quanh biên. |
| 19 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 20 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 21 | <code>def cross(a: Point, b: Point, c: Point) -&gt; float:</code> | Khai báo cross(a,b,c), trả về tích có hướng 2D của vector AB và AC. |
| 22 | <code>    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])</code> | Tính ABx*ACy − ABy*ACx. Dương: c bên trái a→b; âm: bên phải; 0: thẳng hàng. |
| 23 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 24 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 25 | <code>def signed_area(poly: Polygon) -&gt; float:</code> | Khai báo hàm tính diện tích có dấu bằng công thức shoelace. |
| 26 | <code>    return 0.5 * sum(</code> | Cộng các tích chéo của từng cạnh rồi nhân 1/2. |
| 27 | <code>        poly[i][0] * poly[(i + 1) % len(poly)][1]</code> | Lấy x_i*y_(i+1); phép modulo nối đỉnh cuối về đỉnh đầu. |
| 28 | <code>        - poly[(i + 1) % len(poly)][0] * poly[i][1]</code> | Trừ x_(i+1)*y_i, tạo đóng góp có dấu của cạnh i. |
| 29 | <code>        for i in range(len(poly))</code> | Duyệt tất cả chỉ số đỉnh trong biểu thức generator đưa vào sum. |
| 30 | <code>    )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 31 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 32 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 33 | <code>def polygon_area(poly: Polygon) -&gt; float:</code> | Khai báo diện tích hình học không âm. |
| 34 | <code>    return abs(signed_area(poly))</code> | Lấy trị tuyệt đối diện tích có dấu, không phụ thuộc chiều duyệt đỉnh. |
| 35 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 36 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 37 | <code>def normalize_polygon(raw: Iterable[Iterable[float]], tol: float) -&gt; Polygon:</code> | Nhận polygon thô và sai số tol; trả polygon đã chuẩn hóa và kiểm tra. |
| 38 | <code>    poly = [(float(p[0]), float(p[1])) for p in raw]</code> | Chuyển mỗi tọa độ sang float và mỗi điểm sang tuple (x,y). |
| 39 | <code>    if len(poly) &gt; 1 and distance(poly[0], poly[-1]) &lt;= tol:</code> | Nếu đỉnh cuối gần trùng đỉnh đầu trong tol thì coi đó là điểm đóng polygon lặp lại. |
| 40 | <code>        poly.pop()</code> | Xóa điểm cuối lặp để không có cạnh đóng dư. |
| 41 | <code>    if len(poly) &lt; 3:</code> | Kiểm tra số phần tử còn lại nhỏ hơn ba. |
| 42 | <code>        raise ValueError(&quot;Each region must contain at least three distinct points&quot;)</code> | Báo lỗi thiếu đỉnh; lưu ý dòng này không tự kiểm tra mọi cặp đỉnh có khác nhau hay không. |
| 43 | <code>    if signed_area(poly) &lt; 0:</code> | Diện tích âm nghĩa là thứ tự đỉnh theo chiều kim đồng hồ. |
| 44 | <code>        poly.reverse()</code> | Đảo tại chỗ để chuẩn hóa thành ngược chiều kim đồng hồ (CCW). |
| 45 | <code>    if polygon_area(poly) &lt;= tol:</code> | Loại đa giác có diện tích quá nhỏ theo tol. |
| 46 | <code>        raise ValueError(&quot;A region has zero or near-zero area&quot;)</code> | Ném lỗi polygon suy biến hoặc gần suy biến. |
| 47 | <code>    if not is_convex(poly, tol):</code> | Gọi kiểm tra dấu góc quay để kiểm tra tính lồi. |
| 48 | <code>        raise ValueError(&quot;All input regions must be convex polygons&quot;)</code> | Từ chối polygon không vượt qua kiểm tra tính lồi. |
| 49 | <code>    return poly</code> | Trả polygon đã chuẩn hóa. |
| 50 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 51 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 52 | <code>def is_convex(poly: Polygon, tol: float) -&gt; bool:</code> | Kiểm tra các góc quay liên tiếp có cùng dấu hay không; giả định đầu vào là biên polygon đơn hợp lệ. |
| 53 | <code>    signs = []</code> | Tạo danh sách dấu của những góc quay đáng kể. |
| 54 | <code>    for i in range(len(poly)):</code> | Duyệt từng bộ ba đỉnh liên tiếp, có vòng về đầu. |
| 55 | <code>        value = cross(poly[i], poly[(i + 1) % len(poly)], poly[(i + 2) % len(poly)])</code> | Tính tích có hướng tại bộ ba đỉnh i, i+1, i+2. |
| 56 | <code>        if abs(value) &gt; tol:</code> | Bỏ góc gần thẳng hàng để sai số số thực không tạo đổi dấu giả. |
| 57 | <code>            signs.append(value &gt; 0)</code> | Lưu True cho góc quay dương, False cho góc âm. |
| 58 | <code>    return bool(signs) and all(s == signs[0] for s in signs)</code> | Cần ít nhất một góc không suy biến và mọi dấu đều giống dấu đầu. |
| 59 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 60 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 61 | <code>def distance(a: Point, b: Point) -&gt; float:</code> | Khai báo khoảng cách Euclid giữa hai điểm 2D. |
| 62 | <code>    return math.hypot(a[0] - b[0], a[1] - b[1])</code> | hypot(dx,dy) tính căn(dx²+dy²). |
| 63 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 64 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 65 | <code>def edges(poly: Polygon):</code> | Tạo generator sinh lần lượt các cạnh polygon. |
| 66 | <code>    for i, point in enumerate(poly):</code> | enumerate trả đồng thời chỉ số i và tọa độ đỉnh hiện tại. |
| 67 | <code>        yield point, poly[(i + 1) % len(poly)]</code> | yield cặp đầu–cuối cạnh; modulo tạo cạnh từ đỉnh cuối về đầu. |
| 68 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 69 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 70 | <code>def point_on_segment(p: Point, a: Point, b: Point, tol: float) -&gt; bool:</code> | Kiểm tra p nằm trên đoạn hữu hạn ab trong sai số cho phép. |
| 71 | <code>    if abs(cross(a, b, p)) &gt; tol:</code> | Nếu tích có hướng khác 0 đáng kể thì p không cùng đường thẳng ab. |
| 72 | <code>        return False</code> | Trả False ngay khi không thẳng hàng. |
| 73 | <code>    return (</code> | Trả kết quả kết hợp điều kiện giới hạn x và y bên dưới. |
| 74 | <code>        min(a[0], b[0]) - tol &lt;= p[0] &lt;= max(a[0], b[0]) + tol</code> | Tọa độ x của p phải thuộc khoảng x của hai đầu đoạn, nới tol. |
| 75 | <code>        and min(a[1], b[1]) - tol &lt;= p[1] &lt;= max(a[1], b[1]) + tol</code> | Đồng thời tọa độ y phải thuộc khoảng y của hai đầu đoạn, nới tol. |
| 76 | <code>    )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 77 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 78 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 79 | <code>def segments_intersect(a: Point, b: Point, c: Point, d: Point, tol: float) -&gt; bool:</code> | Kiểm tra hai đoạn ab và cd có giao nhau, kể cả tiếp xúc ở biên. |
| 80 | <code>    c1, c2, c3, c4 = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)</code> | Tính vị trí tương đối của c,d với ab và của a,b với cd. |
| 81 | <code>    if ((c1 &gt; tol and c2 &lt; -tol) or (c1 &lt; -tol and c2 &gt; tol)) and (</code> | Kiểm tra c và d ở hai phía đối nhau một cách rõ rệt so với ab. |
| 82 | <code>        (c3 &gt; tol and c4 &lt; -tol) or (c3 &lt; -tol and c4 &gt; tol)</code> | Đồng thời a và b phải ở hai phía đối nhau so với cd. |
| 83 | <code>    ):</code> | Kết thúc điều kiện nhiều dòng; dấu : mở thân khối điều kiện. |
| 84 | <code>        return True</code> | Hai điều kiện cùng đúng: các đoạn cắt nhau ở phần trong. |
| 85 | <code>    return any(</code> | Nếu không cắt xuyên nhau, dùng any để xét các trường hợp chạm biên/thẳng hàng. |
| 86 | <code>        (</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 87 | <code>            abs(value) &lt;= tol and point_on_segment(point, x, y, tol)</code> | Một đầu mút phải vừa thẳng hàng vừa nằm trong đoạn đối diện. |
| 88 | <code>            for value, point, x, y in (</code> | Duyệt bốn tình huống gồm tích có hướng, điểm cần thử và hai đầu đoạn. |
| 89 | <code>                (c1, c, a, b),</code> | Thử c thuộc ab, dùng c1. |
| 90 | <code>                (c2, d, a, b),</code> | Thử d thuộc ab, dùng c2. |
| 91 | <code>                (c3, a, c, d),</code> | Thử a thuộc cd, dùng c3. |
| 92 | <code>                (c4, b, c, d),</code> | Thử b thuộc cd, dùng c4. |
| 93 | <code>            )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 94 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 95 | <code>    )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 96 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 97 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 98 | <code>def collinear_overlap_length(a: Point, b: Point, c: Point, d: Point, tol: float) -&gt; float:</code> | Tính độ dài phần chung của hai đoạn thẳng hàng. |
| 99 | <code>    if abs(cross(a, b, c)) &gt; tol or abs(cross(a, b, d)) &gt; tol:</code> | Kiểm tra cả c và d đều nằm trên đường thẳng ab. |
| 100 | <code>        return 0.0</code> | Không thẳng hàng thì không có phần chồng thẳng hàng: trả 0. |
| 101 | <code>    axis = 0 if abs(b[0] - a[0]) &gt;= abs(b[1] - a[1]) else 1</code> | Chọn trục mà ab có độ chiếu lớn hơn, tránh chia cho giá trị quá nhỏ. |
| 102 | <code>    lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))</code> | Cận trái giao hai khoảng chiếu là max của hai cận trái. |
| 103 | <code>    hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))</code> | Cận phải giao hai khoảng chiếu là min của hai cận phải. |
| 104 | <code>    projected = max(0.0, hi - lo)</code> | Độ dài giao trên trục: max(0,hi−lo), nên khoảng rời nhau cho 0. |
| 105 | <code>    base_projection = abs(b[axis] - a[axis])</code> | Độ dài hình chiếu của toàn bộ ab lên trục đã chọn. |
| 106 | <code>    if base_projection &lt;= tol:</code> | Nếu hình chiếu quá nhỏ, xem đoạn cơ sở suy biến. |
| 107 | <code>        return 0.0</code> | Trả 0 để tránh phép chia không ổn định. |
| 108 | <code>    return projected * distance(a, b) / base_projection</code> | Đổi chiều dài hình chiếu thành chiều dài thật bằng tỉ lệ &#124;ab&#124;/&#124;chiếu(ab)&#124;. |
| 109 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 110 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 111 | <code>def line_intersection(s: Point, e: Point, a: Point, b: Point, tol: float) -&gt; Point:</code> | Tính giao hai đường thẳng s→e và a→b, phục vụ cắt polygon. |
| 112 | <code>    sx, sy = e[0] - s[0], e[1] - s[1]</code> | Vector hướng của đường thẳng s→e. |
| 113 | <code>    ax, ay = b[0] - a[0], b[1] - a[1]</code> | Vector hướng của đường thẳng a→b. |
| 114 | <code>    denominator = sx * ay - sy * ax</code> | Mẫu số là tích có hướng hai vector hướng. |
| 115 | <code>    if abs(denominator) &lt;= tol:</code> | Mẫu gần 0: hai đường gần song song. |
| 116 | <code>        return e</code> | Trả e như xử lý dự phòng; đây không phải khẳng định e là giao điểm toán học duy nhất. |
| 117 | <code>    t = ((a[0] - s[0]) * ay - (a[1] - s[1]) * ax) / denominator</code> | Giải tham số t trong phương trình giao điểm s+t(e−s). |
| 118 | <code>    return s[0] + t * sx, s[1] + t * sy</code> | Trả tọa độ giao điểm bằng cách thế t vào phương trình tham số. |
| 119 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 120 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 121 | <code>def convex_intersection(subject: Polygon, clip: Polygon, tol: float) -&gt; Polygon:</code> | Cắt subject bởi các nửa mặt phẳng của clip để lấy polygon giao. |
| 122 | <code>    &quot;&quot;&quot;Sutherland-Hodgman clipping; both polygons must be CCW and convex.&quot;&quot;&quot;</code> | Docstring nêu thuật toán Sutherland–Hodgman, yêu cầu polygon lồi và CCW. |
| 123 | <code>    output = subject[:]</code> | Sao chép danh sách subject để không sửa danh sách gốc. |
| 124 | <code>    for a, b in edges(clip):</code> | Mỗi cạnh a→b của clip xác định một nửa mặt phẳng phía trong. |
| 125 | <code>        input_points, output = output, []</code> | Kết quả lượt trước trở thành đầu vào; tạo output mới cho lượt cắt hiện tại. |
| 126 | <code>        if not input_points:</code> | Nếu không còn điểm thì giao đã rỗng. |
| 127 | <code>            break</code> | Dừng cắt các cạnh còn lại. |
| 128 | <code>        s = input_points[-1]</code> | Bắt đầu s ở đỉnh cuối để xét cả cạnh đóng polygon. |
| 129 | <code>        for e in input_points:</code> | Duyệt đỉnh e; đoạn đang xét là s→e. |
| 130 | <code>            inside_e = cross(a, b, e) &gt;= -tol</code> | e ở bên trái hoặc sát biên a→b thì được coi là trong. |
| 131 | <code>            inside_s = cross(a, b, s) &gt;= -tol</code> | Xác định tương tự cho đầu s. |
| 132 | <code>            if inside_e:</code> | Xét nhánh đầu cuối e nằm trong. |
| 133 | <code>                if not inside_s:</code> | Nếu s ngoài nhưng e trong thì đoạn đi vào vùng cắt. |
| 134 | <code>                    output.append(line_intersection(s, e, a, b, tol))</code> | Thêm điểm đi vào, tức giao với đường biên. |
| 135 | <code>                output.append(e)</code> | Giữ e vì e nằm trong; áp dụng cả trong→trong và ngoài→trong. |
| 136 | <code>            elif inside_s:</code> | Nếu e ngoài nhưng s trong thì đoạn đi ra khỏi vùng cắt. |
| 137 | <code>                output.append(line_intersection(s, e, a, b, tol))</code> | Giữ điểm đi ra; không giữ e. Nếu cả hai ngoài thì không thêm gì. |
| 138 | <code>            s = e</code> | Chuyển e thành đầu s cho cạnh tiếp theo. |
| 139 | <code>    return output</code> | Sau khi cắt bởi tất cả cạnh, trả danh sách điểm phần giao. |
| 140 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 141 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 142 | <code>def intersection_relation(a: Polygon, b: Polygon, tol: float) -&gt; tuple[str &#124; None, float]:</code> | Phân loại quan hệ hai vùng, trả (tên quan hệ hoặc None, diện tích giao). |
| 143 | <code>    clipped = convex_intersection(a, b, tol)</code> | Tính polygon giao bằng thuật toán cắt. |
| 144 | <code>    area = polygon_area(clipped) if len(clipped) &gt;= 3 else 0.0</code> | Giao có ít hơn ba điểm được coi có diện tích 0. |
| 145 | <code>    if area &gt; tol:</code> | Ưu tiên kiểm tra giao có diện tích dương đáng kể. |
| 146 | <code>        return &quot;overlap&quot;, area</code> | Trả overlap và diện tích giao; bao gồm trường hợp vùng này chứa vùng kia. |
| 147 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 148 | <code>    shared_length = max(</code> | Tìm độ dài chung lớn nhất trong tất cả cặp cạnh hai polygon. |
| 149 | <code>        (collinear_overlap_length(a1, a2, b1, b2, tol) for a1, a2 in edges(a) for b1, b2 in edges(b)),</code> | Generator duyệt tích Descartes các cạnh a và b, tính phần chung thẳng hàng của mỗi cặp. |
| 150 | <code>        default=0.0,</code> | Dùng 0 nếu generator rỗng để max không báo lỗi. |
| 151 | <code>    )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 152 | <code>    if shared_length &gt; tol:</code> | Nếu có một cặp cạnh chung đoạn dài hơn tol... |
| 153 | <code>        return &quot;shared_edge&quot;, 0.0</code> | ...phân loại shared_edge; diện tích giao vẫn 0. |
| 154 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 155 | <code>    if any(segments_intersect(a1, a2, b1, b2, tol) for a1, a2 in edges(a) for b1, b2 in edges(b)):</code> | Nếu chưa overlap/shared_edge nhưng có cặp cạnh giao nhau... |
| 156 | <code>        return &quot;point_contact&quot;, 0.0</code> | ...phân loại point_contact, diện tích 0. |
| 157 | <code>    return None, 0.0</code> | Không giao: trả None để build_graph không tạo cạnh. |
| 158 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 159 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 160 | <code>def centroid(poly: Polygon) -&gt; Point:</code> | Tính trọng tâm theo diện tích polygon; không đơn giản là trung bình đỉnh. |
| 161 | <code>    area6 = 6.0 * signed_area(poly)</code> | Mẫu số công thức trọng tâm bằng 6 lần diện tích có dấu. |
| 162 | <code>    if abs(area6) &lt; 1e-12:</code> | Nếu mẫu rất nhỏ thì dùng xử lý dự phòng. |
| 163 | <code>        return (</code> | Bắt đầu trả tuple trung bình các đỉnh. |
| 164 | <code>            sum(p[0] for p in poly) / len(poly),</code> | Hoành độ dự phòng là trung bình các x. |
| 165 | <code>            sum(p[1] for p in poly) / len(poly),</code> | Tung độ dự phòng là trung bình các y. |
| 166 | <code>        )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 167 | <code>    cx = sum(</code> | Bắt đầu tính tử số trọng tâm x. |
| 168 | <code>        (poly[i][0] + poly[(i + 1) % len(poly)][0])</code> | Lấy tổng hoành độ hai đầu cạnh i. |
| 169 | <code>        * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1])</code> | Nhân tổng x với tích chéo có dấu của hai đầu cạnh. |
| 170 | <code>        for i in range(len(poly))</code> | Cộng đóng góp tất cả cạnh. |
| 171 | <code>    ) / area6</code> | Chia tổng cho 6A để có cx. |
| 172 | <code>    cy = sum(</code> | Bắt đầu tính tử số trọng tâm y. |
| 173 | <code>        (poly[i][1] + poly[(i + 1) % len(poly)][1])</code> | Lấy tổng tung độ hai đầu cạnh i. |
| 174 | <code>        * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1])</code> | Nhân tổng y với tích chéo có dấu của hai đầu cạnh. |
| 175 | <code>        for i in range(len(poly))</code> | Cộng đóng góp tất cả cạnh. |
| 176 | <code>    ) / area6</code> | Chia tổng cho 6A để có cy. |
| 177 | <code>    return cx, cy</code> | Trả tọa độ trọng tâm. |
| 178 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 179 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 180 | <code>def connected_components(vertex_ids: list[str], undirected_edges: list[dict]) -&gt; list[list[str]]:</code> | Tìm các thành phần liên thông của graph vô hướng bằng BFS. |
| 181 | <code>    adjacency = {v: set() for v in vertex_ids}</code> | Tạo tập láng giềng rỗng cho từng đỉnh, kể cả đỉnh cô lập. |
| 182 | <code>    for edge in undirected_edges:</code> | Duyệt từng cạnh vô hướng. |
| 183 | <code>        adjacency[edge[&quot;source&quot;]].add(edge[&quot;target&quot;])</code> | Thêm target vào láng giềng của source. |
| 184 | <code>        adjacency[edge[&quot;target&quot;]].add(edge[&quot;source&quot;])</code> | Thêm source vào láng giềng của target vì đây là liên thông vô hướng. |
| 185 | <code>    unseen, components = set(vertex_ids), []</code> | unseen chứa các đỉnh chưa thăm; components chứa kết quả. |
| 186 | <code>    while unseen:</code> | Chừng nào còn đỉnh chưa thăm, cần bắt đầu một thành phần mới. |
| 187 | <code>        start = min(unseen)</code> | Chọn ID nhỏ nhất theo thứ tự chuỗi để kết quả ổn định. |
| 188 | <code>        queue, component = deque([start]), []</code> | Tạo hàng đợi BFS với start và danh sách thành phần rỗng. |
| 189 | <code>        unseen.remove(start)</code> | Đánh dấu start đã phát hiện bằng cách xóa khỏi unseen. |
| 190 | <code>        while queue:</code> | Tiếp tục BFS khi hàng đợi chưa rỗng. |
| 191 | <code>            u = queue.popleft()</code> | Lấy đỉnh ở đầu hàng đợi, theo FIFO. |
| 192 | <code>            component.append(u)</code> | Thêm đỉnh đang xử lý vào thành phần hiện tại. |
| 193 | <code>            for v in sorted(adjacency[u]):</code> | Duyệt láng giềng theo thứ tự đã sắp xếp. |
| 194 | <code>                if v in unseen:</code> | Chỉ xử lý láng giềng chưa được phát hiện. |
| 195 | <code>                    unseen.remove(v)</code> | Đánh dấu ngay khi đưa vào hàng đợi để tránh đưa trùng. |
| 196 | <code>                    queue.append(v)</code> | Thêm láng giềng vào cuối hàng đợi. |
| 197 | <code>        components.append(component)</code> | BFS xong: lưu toàn bộ thành phần vừa tìm. |
| 198 | <code>    return components</code> | Trả danh sách các thành phần, mỗi thành phần là danh sách ID. |
| 199 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 200 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 201 | <code>def build_graph(data: dict, tol: float = 1e-9) -&gt; dict:</code> | Hàm chính xây GCR; tol mặc định 10⁻⁹. |
| 202 | <code>    regions = []</code> | Khởi tạo danh sách vùng đã chuẩn hóa. |
| 203 | <code>    seen = set()</code> | Tập ID đã gặp để phát hiện trùng. |
| 204 | <code>    for item in data[&quot;regions&quot;]:</code> | Duyệt input data['regions']; file này giả định trường đó tồn tại. |
| 205 | <code>        region_id = str(item[&quot;id&quot;])</code> | Chuyển ID sang chuỗi; vì vậy số 1 và chuỗi '1' trở thành cùng ID. |
| 206 | <code>        if region_id in seen:</code> | Kiểm tra ID bị lặp. |
| 207 | <code>            raise ValueError(f&quot;Duplicate region id: {region_id}&quot;)</code> | Ném lỗi kèm ID trùng. |
| 208 | <code>        seen.add(region_id)</code> | Ghi nhận ID vừa đọc. |
| 209 | <code>        polygon = normalize_polygon(item[&quot;polygon&quot;], tol)</code> | Chuẩn hóa tọa độ, chiều đỉnh, diện tích và tính lồi. |
| 210 | <code>        regions.append({&quot;id&quot;: region_id, &quot;polygon&quot;: polygon, &quot;centroid&quot;: centroid(polygon)})</code> | Lưu ID, polygon chuẩn hóa và trọng tâm tính từ polygon. |
| 211 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 212 | <code>    undirected = []</code> | Khởi tạo danh sách cạnh vô hướng. |
| 213 | <code>    for i, left in enumerate(regions):</code> | Duyệt vùng trái kèm chỉ số. |
| 214 | <code>        for right in regions[i + 1 :]:</code> | Chỉ ghép với vùng đứng sau: mỗi cặp được xét đúng một lần, không tự nối chính nó. |
| 215 | <code>            relation, area = intersection_relation(left[&quot;polygon&quot;], right[&quot;polygon&quot;], tol)</code> | Tính quan hệ hình học và diện tích phần giao của hai vùng. |
| 216 | <code>            if relation:</code> | Chỉ có quan hệ giao nhau mới tạo cạnh. |
| 217 | <code>                undirected.append(</code> | Bắt đầu thêm một record cạnh vô hướng. |
| 218 | <code>                    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 219 | <code>                        &quot;source&quot;: left[&quot;id&quot;],</code> | source lấy ID vùng trái; tên source ở đây chỉ là quy ước lưu cặp. |
| 220 | <code>                        &quot;target&quot;: right[&quot;id&quot;],</code> | target lấy ID vùng phải. |
| 221 | <code>                        &quot;relation&quot;: relation,</code> | Lưu overlap, shared_edge hoặc point_contact. |
| 222 | <code>                        &quot;intersection_area&quot;: round(area, 12),</code> | Làm tròn diện tích giao đến 12 chữ số sau dấu phẩy. |
| 223 | <code>                    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 224 | <code>                )</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 225 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 226 | <code>    directed = []</code> | Khởi tạo danh sách cạnh có hướng. |
| 227 | <code>    for edge in undirected:</code> | Mỗi cạnh vô hướng sẽ tạo hai chiều. |
| 228 | <code>        directed.append({**edge})</code> | **edge giải nén dict để tạo bản sao cạnh chiều ban đầu. |
| 229 | <code>        directed.append({**edge, &quot;source&quot;: edge[&quot;target&quot;], &quot;target&quot;: edge[&quot;source&quot;]})</code> | Sao chép thuộc tính rồi ghi đè source/target đảo ngược; hai chiều có thể được LLM chấm khác nhau sau này. |
| 230 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 231 | <code>    vertices = [</code> | Tạo danh sách vertex sẵn sàng xuất JSON bằng list comprehension. |
| 232 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 233 | <code>            &quot;id&quot;: r[&quot;id&quot;],</code> | Ghi ID vùng vào vertex. |
| 234 | <code>            &quot;centroid&quot;: [round(r[&quot;centroid&quot;][0], 8), round(r[&quot;centroid&quot;][1], 8)],</code> | Làm tròn hai tọa độ trọng tâm tới 8 chữ số thập phân. |
| 235 | <code>            &quot;polygon&quot;: [[x, y] for x, y in r[&quot;polygon&quot;]],</code> | Chuyển các tuple điểm thành list hai phần tử phù hợp schema JSON. |
| 236 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 237 | <code>        for r in regions</code> | Duyệt mọi vùng đã chuẩn hóa để tạo vertex. |
| 238 | <code>    ]</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 239 | <code>    return {</code> | Trả object graph đầy đủ. |
| 240 | <code>        &quot;directed&quot;: True,</code> | Đánh dấu có danh sách cạnh có hướng. |
| 241 | <code>        &quot;vertices&quot;: vertices,</code> | Gắn danh sách vertices. |
| 242 | <code>        &quot;undirected_edges&quot;: undirected,</code> | Gắn danh sách cạnh vô hướng dùng thống kê, BFS và hình minh họa. |
| 243 | <code>        &quot;directed_edges&quot;: directed,</code> | Gắn danh sách cạnh có hướng để planner Python sử dụng. |
| 244 | <code>        &quot;connected_components&quot;: connected_components([r[&quot;id&quot;] for r in regions], undirected),</code> | Tính các thành phần liên thông trên các ID vùng và cạnh vô hướng. |
| 245 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 246 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 247 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 248 | <code>COLORS = [&quot;#ef767a&quot;, &quot;#56c271&quot;, &quot;#5b9cf0&quot;, &quot;#ac72d6&quot;, &quot;#f4a259&quot;, &quot;#49bec7&quot;, &quot;#ed6b9f&quot;, &quot;#9bcf53&quot;]</code> | Bảng tám màu hex; khi nhiều vùng hơn sẽ sử dụng màu vòng lại. |
| 249 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 250 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 251 | <code>def svg_visualization(graph: dict, width: int = 1200, height: int = 650) -&gt; str:</code> | Sinh chuỗi SVG gồm hai panel; không thay đổi topology hay chạy planner. |
| 252 | <code>    vertices = graph[&quot;vertices&quot;]</code> | Lấy danh sách đỉnh từ graph. |
| 253 | <code>    points = [p for v in vertices for p in v[&quot;polygon&quot;]]</code> | Trải phẳng tất cả điểm polygon để tính khung bao bản đồ. |
| 254 | <code>    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)</code> | Tìm giới hạn trái/phải; danh sách rỗng sẽ gây lỗi min/max. |
| 255 | <code>    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)</code> | Tìm giới hạn dưới/trên. |
| 256 | <code>    span_x, span_y = max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)</code> | Bảo đảm độ rộng/cao khung bao không bằng 0 để phép chia an toàn hơn. |
| 257 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 258 | <code>    panel_w, margin = width / 2, 55</code> | Mỗi panel chiếm nửa chiều rộng, chừa lề 55 pixel. |
| 259 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 260 | <code>    def transform(p: Point, panel: int) -&gt; Point:</code> | Hàm con biến tọa độ thế giới thành tọa độ pixel của panel 0 hoặc 1. |
| 261 | <code>        scale = min((panel_w - 2 * margin) / span_x, (height - 2 * margin) / span_y)</code> | Chọn một hệ số scale chung để giữ tỉ lệ và vừa cả chiều rộng lẫn chiều cao. |
| 262 | <code>        used_w, used_h = span_x * scale, span_y * scale</code> | Kích thước thực tế của bản đồ sau khi scale. |
| 263 | <code>        offset_x = panel * panel_w + (panel_w - used_w) / 2</code> | Căn giữa ngang và cộng độ dịch sang panel tương ứng. |
| 264 | <code>        offset_y = (height - used_h) / 2</code> | Căn giữa dọc. |
| 265 | <code>        return offset_x + (p[0] - min_x) * scale, height - offset_y - (p[1] - min_y) * scale</code> | Dịch và scale x,y; đảo chiều y vì SVG có y tăng xuống dưới. |
| 266 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 267 | <code>    lines = [</code> | Tập hợp các dòng XML thành một danh sách chuỗi. |
| 268 | <code>        f&#x27;&lt;svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;{width}&quot; height=&quot;{height}&quot; viewBox=&quot;0 0 {width} {height}&quot;&gt;&#x27;,</code> | Thẻ SVG gốc khai báo namespace, kích thước và hệ tọa độ viewBox. |
| 269 | <code>        &#x27;&lt;rect width=&quot;100%&quot; height=&quot;100%&quot; fill=&quot;#f8fafc&quot;/&gt;&#x27;,</code> | Vẽ nền màu nhạt phủ toàn bộ ảnh. |
| 270 | <code>        f&#x27;&lt;line x1=&quot;{panel_w}&quot; y1=&quot;28&quot; x2=&quot;{panel_w}&quot; y2=&quot;{height-28}&quot; stroke=&quot;#cbd5e1&quot;/&gt;&#x27;,</code> | Vẽ vạch phân chia hai panel. |
| 271 | <code>        f&#x27;&lt;text x=&quot;{panel_w/2}&quot; y=&quot;30&quot; text-anchor=&quot;middle&quot; font-family=&quot;Arial&quot; font-size=&quot;22&quot; font-weight=&quot;700&quot;&gt;Convex regions&lt;/text&gt;&#x27;,</code> | Viết tiêu đề panel trái: các vùng lồi. |
| 272 | <code>        f&#x27;&lt;text x=&quot;{panel_w+panel_w/2}&quot; y=&quot;30&quot; text-anchor=&quot;middle&quot; font-family=&quot;Arial&quot; font-size=&quot;22&quot; font-weight=&quot;700&quot;&gt;Graph of Convex Regions&lt;/text&gt;&#x27;,</code> | Viết tiêu đề panel phải: graph các vùng. |
| 273 | <code>        &#x27;&lt;defs&gt;&lt;marker id=&quot;arrow&quot; markerWidth=&quot;8&quot; markerHeight=&quot;8&quot; refX=&quot;7&quot; refY=&quot;4&quot; orient=&quot;auto&quot;&gt;&lt;path d=&quot;M0,0 L8,4 L0,8 z&quot; fill=&quot;#64748b&quot;/&gt;&lt;/marker&gt;&lt;/defs&gt;&#x27;,</code> | Định nghĩa marker mũi tên dùng chung cho các cạnh. |
| 274 | <code>    ]</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 275 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 276 | <code>    for idx, vertex in enumerate(vertices):</code> | Duyệt từng vùng kèm chỉ số để chọn màu. |
| 277 | <code>        polygon_points = &quot; &quot;.join(f&quot;{x:.2f},{y:.2f}&quot; for x, y in (transform(tuple(p), 0) for p in vertex[&quot;polygon&quot;]))</code> | Biến mỗi đỉnh sang pixel panel trái, định dạng hai chữ số thập phân rồi nối thành thuộc tính points. |
| 278 | <code>        color = COLORS[idx % len(COLORS)]</code> | Chọn màu theo idx modulo số màu. |
| 279 | <code>        lines.append(f&#x27;&lt;polygon points=&quot;{polygon_points}&quot; fill=&quot;{color}&quot; fill-opacity=&quot;0.48&quot; stroke=&quot;#334155&quot; stroke-width=&quot;2&quot;/&gt;&#x27;)</code> | Vẽ polygon tô bán trong suốt và có đường viền. |
| 280 | <code>        cx, cy = transform(tuple(vertex[&quot;centroid&quot;]), 0)</code> | Chuyển trọng tâm sang pixel panel trái. |
| 281 | <code>        lines.append(f&#x27;&lt;circle cx=&quot;{cx:.2f}&quot; cy=&quot;{cy:.2f}&quot; r=&quot;18&quot; fill=&quot;#0f172a&quot;/&gt;&#x27;)</code> | Vẽ hình tròn nền tối tại trọng tâm. |
| 282 | <code>        lines.append(f&#x27;&lt;text x=&quot;{cx:.2f}&quot; y=&quot;{cy+5:.2f}&quot; text-anchor=&quot;middle&quot; fill=&quot;white&quot; font-family=&quot;Arial&quot; font-size=&quot;13&quot;&gt;{vertex[&quot;id&quot;]}&lt;/text&gt;&#x27;)</code> | Viết ID vùng bằng chữ trắng; ID được chèn trực tiếp, chưa XML-escape. |
| 283 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 284 | <code>    positions = {v[&quot;id&quot;]: transform(tuple(v[&quot;centroid&quot;]), 1) for v in vertices}</code> | Tạo ánh xạ ID→tọa độ trọng tâm trong panel graph bên phải. |
| 285 | <code>    for edge in graph[&quot;undirected_edges&quot;]:</code> | Duyệt cặp kết nối; mỗi cặp sẽ được vẽ thành hai mũi tên. |
| 286 | <code>        x1, y1 = positions[edge[&quot;source&quot;]]</code> | Lấy vị trí pixel đỉnh source. |
| 287 | <code>        x2, y2 = positions[edge[&quot;target&quot;]]</code> | Lấy vị trí pixel đỉnh target. |
| 288 | <code>        dx, dy = x2 - x1, y2 - y1</code> | Tính vector từ source đến target. |
| 289 | <code>        length = max(math.hypot(dx, dy), 1e-9)</code> | Tính độ dài vector và chặn mẫu số tối thiểu 10⁻⁹. |
| 290 | <code>        ux, uy = dx / length, dy / length</code> | Chuẩn hóa vector hướng thành (ux,uy). |
| 291 | <code>        # Two slightly offset arrows show that traversal is bidirectional.</code> | Chú thích: dịch nhẹ hai mũi tên để nhìn thấy hai chiều. |
| 292 | <code>        px, py = -uy * 4, ux * 4</code> | Vector vuông góc dài 4 pixel dùng để tách hai mũi tên. |
| 293 | <code>        for reverse in (False, True):</code> | Vẽ lần lượt chiều thuận và chiều ngược. |
| 294 | <code>            if reverse:</code> | Chọn cách tính tọa độ cho chiều ngược. |
| 295 | <code>                sx, sy, tx, ty = x2 - ux * 23 - px, y2 - uy * 23 - py, x1 + ux * 23 - px, y1 + uy * 23 - py</code> | Mũi tên từ target về source; lùi 23 pixel khỏi tâm nút, dịch sang một bên. |
| 296 | <code>            else:</code> | Nhánh chiều thuận. |
| 297 | <code>                sx, sy, tx, ty = x1 + ux * 23 + px, y1 + uy * 23 + py, x2 - ux * 23 + px, y2 - uy * 23 + py</code> | Mũi tên từ source sang target; lùi 23 pixel khỏi tâm nút, dịch sang phía đối diện. |
| 298 | <code>            lines.append(f&#x27;&lt;line x1=&quot;{sx:.2f}&quot; y1=&quot;{sy:.2f}&quot; x2=&quot;{tx:.2f}&quot; y2=&quot;{ty:.2f}&quot; stroke=&quot;#64748b&quot; stroke-width=&quot;1.8&quot; marker-end=&quot;url(#arrow)&quot;/&gt;&#x27;)</code> | Thêm đường SVG với marker-end tham chiếu mũi tên đã định nghĩa. |
| 299 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 300 | <code>    for idx, vertex in enumerate(vertices):</code> | Duyệt vertex lần nữa để vẽ nút đè lên lớp cạnh. |
| 301 | <code>        cx, cy = positions[vertex[&quot;id&quot;]]</code> | Lấy vị trí nút trong panel phải. |
| 302 | <code>        color = COLORS[idx % len(COLORS)]</code> | Chọn cùng màu vùng tương ứng. |
| 303 | <code>        lines.append(f&#x27;&lt;circle cx=&quot;{cx:.2f}&quot; cy=&quot;{cy:.2f}&quot; r=&quot;22&quot; fill=&quot;{color}&quot; stroke=&quot;#334155&quot; stroke-width=&quot;2&quot;/&gt;&#x27;)</code> | Vẽ nút tròn bán kính 22 pixel. |
| 304 | <code>        lines.append(f&#x27;&lt;text x=&quot;{cx:.2f}&quot; y=&quot;{cy+5:.2f}&quot; text-anchor=&quot;middle&quot; fill=&quot;#0f172a&quot; font-family=&quot;Arial&quot; font-size=&quot;14&quot; font-weight=&quot;700&quot;&gt;{vertex[&quot;id&quot;]}&lt;/text&gt;&#x27;)</code> | Viết ID ở giữa nút graph. |
| 305 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 306 | <code>    counts = {}</code> | Dictionary đếm số cạnh theo từng quan hệ. |
| 307 | <code>    for edge in graph[&quot;undirected_edges&quot;]:</code> | Duyệt từng cạnh vô hướng để không đếm đôi. |
| 308 | <code>        counts[edge[&quot;relation&quot;]] = counts.get(edge[&quot;relation&quot;], 0) + 1</code> | Tăng bộ đếm quan hệ, mặc định bắt đầu từ 0. |
| 309 | <code>    summary = &quot;, &quot;.join(f&quot;{key}: {value}&quot; for key, value in sorted(counts.items())) or &quot;no intersections&quot;</code> | Sắp xếp tên quan hệ và tạo chuỗi thống kê; rỗng thì ghi no intersections. |
| 310 | <code>    lines.append(f&#x27;&lt;text x=&quot;{width/2}&quot; y=&quot;{height-14}&quot; text-anchor=&quot;middle&quot; font-family=&quot;Arial&quot; font-size=&quot;13&quot; fill=&quot;#475569&quot;&gt;{len(vertices)} regions · {len(graph[&quot;undirected_edges&quot;])} connections · {summary}&lt;/text&gt;&#x27;)</code> | Viết thống kê số vùng, kết nối và loại giao ở cuối ảnh. |
| 311 | <code>    lines.append(&quot;&lt;/svg&gt;&quot;)</code> | Đóng thẻ SVG gốc. |
| 312 | <code>    return &quot;\n&quot;.join(lines)</code> | Ghép các dòng XML bằng ký tự xuống dòng và trả chuỗi hoàn chỉnh. |
| 313 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 314 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 315 | <code>def parse_args() -&gt; argparse.Namespace:</code> | Định nghĩa phần đọc tham số command line. |
| 316 | <code>    parser = argparse.ArgumentParser(description=__doc__)</code> | Tạo parser, lấy docstring module làm mô tả trợ giúp. |
| 317 | <code>    parser.add_argument(&quot;input&quot;, type=Path, help=&quot;JSON file containing a &#x27;regions&#x27; list&quot;)</code> | Đối số vị trí input bắt buộc, chuyển thành Path. |
| 318 | <code>    parser.add_argument(&quot;--output&quot;, type=Path, default=Path(&quot;graph.json&quot;), help=&quot;Output graph JSON&quot;)</code> | Tùy chọn file graph đầu ra, mặc định graph.json trong thư mục làm việc. |
| 319 | <code>    parser.add_argument(&quot;--svg&quot;, type=Path, default=Path(&quot;graph.svg&quot;), help=&quot;Output visualization SVG&quot;)</code> | Tùy chọn file SVG đầu ra, mặc định graph.svg. |
| 320 | <code>    parser.add_argument(&quot;--tolerance&quot;, type=float, default=1e-9, help=&quot;Geometry tolerance&quot;)</code> | Sai số hình học đọc dưới dạng float, mặc định 10⁻⁹. |
| 321 | <code>    return parser.parse_args()</code> | Parse command line và trả Namespace có các thuộc tính tương ứng. |
| 322 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 323 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 324 | <code>def main() -&gt; None:</code> | Entry point điều phối đọc → xây graph → lưu → in kết quả. |
| 325 | <code>    args = parse_args()</code> | Đọc tham số command line. |
| 326 | <code>    data = json.loads(args.input.read_text(encoding=&quot;utf-8&quot;))</code> | Đọc file UTF-8 rồi giải mã JSON thành object Python. |
| 327 | <code>    graph = build_graph(data, args.tolerance)</code> | Xây graph với tolerance người dùng chọn. |
| 328 | <code>    args.output.parent.mkdir(parents=True, exist_ok=True)</code> | Tạo thư mục cha cho JSON, tạo cả cha còn thiếu, không lỗi nếu đã tồn tại. |
| 329 | <code>    args.svg.parent.mkdir(parents=True, exist_ok=True)</code> | Tạo thư mục cha cho SVG. |
| 330 | <code>    args.output.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + &quot;\n&quot;, encoding=&quot;utf-8&quot;)</code> | Ghi JSON đẹp với indent=2, giữ Unicode, thêm newline cuối file. |
| 331 | <code>    args.svg.write_text(svg_visualization(graph), encoding=&quot;utf-8&quot;)</code> | Sinh và ghi SVG dưới dạng UTF-8. |
| 332 | <code>    print(f&quot;Built {len(graph[&#x27;vertices&#x27;])} vertices and {len(graph[&#x27;undirected_edges&#x27;])} bidirectional connections&quot;)</code> | In số vertex và số kết nối hai chiều, dùng số cạnh vô hướng. |
| 333 | <code>    print(f&quot;Connected components: {graph[&#x27;connected_components&#x27;]}&quot;)</code> | In các thành phần liên thông để thấy graph có bị tách hay không. |
| 334 | <code>    print(f&quot;JSON: {args.output}&quot;)</code> | In đường dẫn JSON đã ghi. |
| 335 | <code>    print(f&quot;SVG:  {args.svg}&quot;)</code> | In đường dẫn SVG đã ghi. |
| 336 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 337 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 338 | <code>if __name__ == &quot;__main__&quot;:</code> | Chỉ chạy main khi file được thực thi trực tiếp, không chạy khi import. |
| 339 | <code>    main()</code> | Gọi main; file này không có try/except tổng để chuyển lỗi thành thông báo ngắn. |
