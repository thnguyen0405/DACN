"""Generate presentation SVGs of the current demo and optional project flows."""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent
INK = '#153e32'
GREEN = '#a9edc7'
PURPLE = '#5145bd'
PINK = '#eaa5f6'
BLUE = '#e8f1ff'


class Diagram:
    def __init__(self, height, title, subtitle):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="{height}" viewBox="0 0 2400 {height}">',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9" fill="none" stroke="#153e32" stroke-width="1.8"/></marker></defs>',
            '<rect width="2400" height="100%" fill="white"/>',
            '<g font-family="Arial, Helvetica, sans-serif">']
        self.text(65, 65, title, 39, 'start', INK, 700)
        self.text(65, 108, subtitle, 24, 'start', '#566477')

    def text(self, x, y, value, size=27, anchor='middle', color=INK, weight=400):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-weight="{weight}">{escape(value)}</text>')

    def box(self, cx, cy, w, h, lines, small=(), fill=GREEN, terminal=False, stroke=None):
        self.parts.append(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="{h/2 if terminal else 13}" fill="{fill}" stroke="{stroke or fill}" stroke-width="2"/>')
        color = 'white' if terminal else INK
        heights = [32] * len(lines) + [27] * len(small)
        y = cy - sum(heights) / 2 + 24
        for line in lines:
            self.text(cx, y, line, 27, color=color, weight=600)
            y += 32
        for line in small:
            self.text(cx, y, line, 22, color=color if terminal else '#38584c')
            y += 27

    def diamond(self, cx, cy, w, h, lines, small=()):
        pts = f'{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}'
        self.parts.append(f'<polygon points="{pts}" fill="{PINK}"/>')
        y = cy - (len(lines)*31 + len(small)*24)/2 + 22
        for line in lines:
            self.text(cx, y, line, 26, weight=600)
            y += 31
        for line in small:
            self.text(cx, y, line, 20)
            y += 24

    def edge(self, points, label=None, at=None, dashed=False, arrow=True):
        d = 'M ' + ' L '.join(f'{x} {y}' for x,y in points)
        self.parts.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round"' + (' stroke-dasharray="9 7"' if dashed else '') + (' marker-end="url(#arrow)"' if arrow else '') + '/>')
        if label:
            x,y = at
            w = len(label)*12 + 22
            self.parts.append(f'<rect x="{x-w/2}" y="{y-23}" width="{w}" height="31" rx="5" fill="white"/>')
            self.text(x,y,label,23)

    def note(self, x, y, w, h, title, lines, fill='#f4f6fb'):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}"/>')
        self.text(x+24,y+37,title,25,'start',INK,700)
        for i,line in enumerate(lines):
            self.text(x+24,y+73+30*i,line,23,'start','#465368')

    def save(self, name):
        (OUT / name).write_text('\n'.join(self.parts + ['</g></svg>']), encoding='utf-8')


def main_flow():
    d = Diagram(1400, '01  |  LUỒNG DEMO: GRAPH → LLM → RRT → RVIZ',
        'Chế độ region_prior đang dùng cho hole, narrow, flappy và room · Python chuẩn bị dữ liệu, C++ tìm đường')
    d.text(65,167,'A. CHUẨN BỊ BẢN ĐỒ VÀ GỌI LLM',22,'start',PURPLE,700)
    d.box(130,250,170,96,['Bắt đầu'],fill=PURPLE,terminal=True)
    d.box(445,250,330,126,['Chọn bản đồ'],['map.json','start, goal, robot, vật cản'])
    d.box(865,250,360,126,['Phân rã không gian trống','thành các vùng lồi'],['regions.json'])
    d.box(1285,250,360,126,['Dựng GCR có hướng'],['Vùng = đỉnh; portal = cạnh','Thu hẹp / lọc portal'])
    d.box(1715,250,360,126,['Tính đặc trưng vùng'],['Diện tích, hình dạng, clearance','Kết nối → graph.json'])
    d.box(2150,250,340,126,['LLM chấm điểm vùng'],['Graph + start/goal + prompt','Điểm [0,1] và lý do'])
    for a,b in [(215,280),(610,685),(1045,1105),(1465,1535),(1895,1980)]:
        d.edge([(a,250),(b,250)])
    d.text(65,420,'B. KIỂM TRA OUTPUT VÀ NẠP PRIOR VÀO C++',22,'start',PURPLE,700)
    d.diamond(2150,570,300,190,['Phản hồi','hợp lệ?'])
    d.box(1720,570,360,140,['Xuất prior cho C++'],['demo_prior.json →','demo_sampling_prior.json'])
    d.box(1285,570,360,140,['Khởi tạo planner'],['Nạp map, start/goal, prior','RRT / RRT* / RRT# / BRRT…'])
    d.box(850,570,360,140,['Lấy mẫu x_rand'],['Chọn vùng theo score / Σscore','Lấy điểm đều trong vùng'])
    d.box(420,570,360,140,['Mở rộng cây'],['Nearest → Steer','Theo biến thể planner'])
    d.edge([(2150,313),(2150,475)])
    d.edge([(2000,570),(1900,570)],'Có',(1950,549))
    d.edge([(1540,570),(1465,570)])
    d.edge([(1105,570),(1030,570)])
    d.edge([(670,570),(600,570)])
    d.box(2150,795,340,105,['Dừng và báo lỗi'],['Sửa dữ liệu / gọi lại thủ công'],fill='#ffe3e0')
    d.edge([(2150,665),(2150,742)],'Không',(2203,710))
    d.text(650,875,'C. VÒNG LẶP TÌM ĐƯỜNG VÀ KẾT QUẢ',22,'start',PURPLE,700)
    d.diamond(420,1020,300,180,['Điểm / đoạn','không va chạm?'])
    d.box(850,1020,360,140,['Cập nhật cây và nghiệm'],['Thêm nút; nối goal / hai cây','Rewire nếu planner hỗ trợ'])
    d.diamond(1285,1020,320,190,['Đạt điều kiện','dừng?'],['Tùy planner'])
    d.box(1720,1020,360,140,['Trả kết quả'],['Nghiệm tốt nhất đã tìm được','hoặc báo không có nghiệm'])
    d.box(2150,1020,340,140,['RViz + [RESULT]'],['Đường đi, cây, vùng','Thời gian, chiều dài, số nút'])
    d.edge([(420,640),(420,930)])
    d.edge([(570,1020),(670,1020)],'Có',(620,998))
    d.edge([(1030,1020),(1125,1020)])
    d.edge([(1445,1020),(1540,1020)],'Có',(1492,998))
    d.edge([(1900,1020),(1980,1020)])
    d.edge([(420,1110),(420,1170),(1285,1170),(1285,1115)],'Không: bỏ mẫu, vẫn kiểm tra ngân sách',(835,1170))
    d.edge([(1285,925),(1285,740),(850,740),(850,640)],'Chưa: tiếp tục lấy mẫu',(1100,740))
    d.box(2150,1200,210,85,['Kết thúc'],fill=PURPLE,terminal=True)
    d.edge([(2150,1090),(2150,1157)])
    d.note(65,1255,2270,112,'CÁCH ĐỌC ĐÚNG',[
        'Điểm LLM cố định trong một lượt ROS; demo region_prior không cần Dijkstra. LLM không tạo quỹ đạo hay xác nhận an toàn.',
        'Điều kiện dừng phụ thuộc planner: đạt nghiệm hoặc hết ngân sách. Informed RRT* có thể lọc mẫu theo miền informed sau nghiệm đầu.'
    ])
    d.save('01-demo-flow.svg')


def extension_flow():
    d = Diagram(1540,'02  |  CÁC NHÁNH KHÁC VÀ THỬ NGHIỆM CỦA DỰ ÁN',
        'Các chế độ lấy mẫu là lựa chọn thay thế nhau; cập nhật điểm động chạy trong RRT Python riêng')
    d.text(65,172,'A. CÁC CHẾ ĐỘ LẤY MẪU TRONG ROS/C++',22,'start',PURPLE,700)
    d.box(320,285,470,130,['Baseline: guidance_mode = none'],['Không cần LLM / prior','Sampler gốc của planner'],fill=BLUE)
    d.box(320,495,470,130,['Điểm vùng hợp lệ'],['LLM thật / heuristic / mock','Ghi rõ nguồn điểm'])
    d.box(940,495,480,130,['region_prior'],['Chọn vùng theo trọng số','Lấy điểm đều theo diện tích'])
    d.box(320,755,470,130,['Chi phí các cạnh hiện có'],['LLM hoặc heuristic hình học','Kiểm tra ID và miền giá trị'])
    d.box(940,755,480,130,['Dijkstra trên GCR'],['Tối thiểu tổng edge cost','Xuất chuỗi vùng start → goal'])
    d.box(1510,675,430,120,['sequence_guided'],['Vùng theo chuỗi + portal','Trộn lấy mẫu toàn cục'])
    d.box(1510,860,430,110,['corridor'],['Lấy mẫu trong hợp vùng tuyến'])
    d.box(2120,495,420,150,['Vòng lặp planner C++'],['Lấy mẫu → mở rộng cây','Kiểm tra va chạm → cập nhật','Xuất RViz + metrics'])
    d.edge([(555,285),(2120,285),(2120,420)])
    d.edge([(555,495),(700,495)])
    d.edge([(1180,495),(1910,495)])
    d.edge([(555,755),(700,755)])
    d.edge([(1180,755),(1230,755),(1230,675),(1295,675)])
    d.edge([(1230,755),(1230,860),(1295,860)])
    d.edge([(1725,675),(1830,675),(1830,540),(1910,540)])
    d.edge([(1725,860),(2290,860),(2290,570)])
    d.text(320,620,'Nhánh chọn tuyến dùng edge cost',22,color='#576577')
    d.text(1510,765,'Demo hỗn hợp: 80% guided / 20% global',20,color='#576577')
    d.text(65,963,'B. CẬP NHẬT ĐIỂM ĐỘNG — NGHIÊN CỨU PYTHON, CHƯA TÍCH HỢP ROS',22,'start',PURPLE,700)
    d.box(290,1090,420,140,['RRT Python đang chạy'],['Điểm ban đầu: llm_prior.json','Theo dõi vòng lặp, nút, vùng'])
    d.diamond(865,1090,350,200,['Đến lúc','chấm lại?'],['Còn lượt gọi'])
    d.box(1430,1090,480,140,['Gọi lại LLM'],['Graph + vùng đã thăm + số nút','Điểm hiện tại + nghiệm tốt nhất'])
    d.box(2070,1090,470,140,['Áp dụng điểm mới'],['Dùng cho mẫu tiếp theo','Lỗi → giữ nguyên điểm cũ'])
    d.edge([(500,1090),(690,1090)])
    d.edge([(1040,1090),(1190,1090)],'Có',(1115,1067))
    d.edge([(1670,1090),(1835,1090)])
    d.edge([(865,1190),(865,1245),(290,1245),(290,1160)],'Không',(565,1245))
    d.edge([(2070,1160),(2070,1300),(105,1300),(105,1160)],'Tiếp tục trên cây hiện có',(1530,1300))
    d.note(65,1350,1120,155,'TRIGGER MẶC ĐỊNH',[
        'Chọn một: mỗi 250 vòng lặp HOẶC thêm nút vào vùng mới.',
        'Cooldown 100 vòng; tối đa 2 lần gọi thêm (kể cả lần lỗi).',
        'Decay nếu bật: giảm điểm sau mỗi 20 nút trong vùng; không gọi LLM.'
    ])
    d.note(1215,1350,1120,155,'ĐÁNH GIÁ KẾT QUẢ',[
        'Nhiều map × seed × planner × chế độ, cùng ngân sách.',
        'Success rate, thời gian nghiệm đầu, chiều dài, va chạm, chi phí API.',
        'reference.json: đường ngắn nhất trên lưới; không phải tối ưu liên tục.'
    ],fill='#eef8f1')
    d.save('02-project-branches.svg')


if __name__ == '__main__':
    main_flow()
    extension_flow()
