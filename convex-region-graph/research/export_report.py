"""Build the Vietnamese study report from recorded results, without API calls.

Optional HTML export requires the markdown package. Figures need matplotlib.
"""
import argparse,base64,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.figures import draw_concepts,map_plot,save,COLORS
import matplotlib.pyplot as plt
import numpy as np

def load(path):return json.loads(path.read_text())
def num(v,d=2):return '—' if v is None else f'{v:.{d}f}'
def mean(values):
 values=[v for v in values if v is not None]
 return statistics.fmean(values) if values else None
def table(head,rows):return '\n'+' | '.join(head)+'\n'+' | '.join(['---']*len(head))+'\n'+'\n'.join(' | '.join(str(v) for v in r) for r in rows)+'\n'

def build(maps,output):
 maps=Path(maps);output=Path(output);output.mkdir(parents=True,exist_ok=True);figdir=output/'figures'
 names=['hole','flappy','narrow','room'];data={n:{f:load(maps/n/(f+'.json')) for f in ['map','graph','import_audit','runs','analysis','llm_prior']} for n in names}
 draw_concepts(figdir)
 for n in names:map_plot(maps/n,figdir)
 fig,axes=plt.subplots(2,2,figsize=(11,7),sharey=True)
 selected=['none','region_area','region_uniform','heuristic','llm']
 for ax,n in zip(axes.flat,names):
  records={r['mode']:r for r in data[n]['runs']['summary']};values=[100*records[m]['success_rate'] for m in selected]
  ax.bar(range(5),values,color=[COLORS['gray'],COLORS['blue'],COLORS['blue'],COLORS['orange'],COLORS['green']])
  for i,v in enumerate(values):ax.text(i,v+2,f'{v:.0f}%',ha='center',fontsize=9)
  ax.set_xticks(range(5),['none','area','uniform','heuristic','LLM'],rotation=15);ax.set_ylim(0,115);ax.set_title(n,loc='left',fontweight='bold');ax.set_ylabel('Thành công (%)')
 fig.suptitle('10 seed mỗi chế độ • 2.500 bước • RRT Python nghiên cứu',fontsize=15,color=COLORS['ink']);fig.tight_layout();save(fig,figdir/'success_rates')
 parts=['# Đánh giá LLM-guided RRT trên GCR-Dataset\n\nBản kết quả hoàn tất ngày 08/10/2026. Dùng dữ liệu người dùng cung cấp và code DACN-main; mọi con số dưới đây lấy từ JSON đã lưu.']
 parts.append('''## Phạm vi và kết quả chính

Đã chuyển đổi cả 4 map, chạy **480 lượt chính** (4 map × 12 chế độ × 10 seed), **30 lượt bổ sung** ở ngân sách cao hơn và **2 pilot gọi lại API thật**. Tổng cộng 512 lượt RRT. Đã tự vẽ 3 hình giải thích và 4 hình bản đồ.

Đây là **RRT Python nghiên cứu, không phải benchmark sáu planner ROS/C++**. Docker trên máy chưa hoạt động nên chưa xác nhận kết quả trong ROS. Phần cập nhật động hiện là prototype Python.

LLM không tốt hơn trong mọi trường hợp: `narrow` đạt 10/10 so với `none` 0/10 ở 2.500 bước, nhưng `hole` có đường LLM trung bình dài hơn heuristic. `room` thất bại toàn bộ ở ngân sách này; tăng lên 10.000 bước cho kết quả khác. Các lần dùng cùng một prior LLM cố định, chưa đo biến thiên giữa các lần model sinh điểm.

## 1. Dataset, đơn vị và điều kiện kiểm tra

Nguồn là bốn file `.poly`. Graph gốc có cạnh shared_length=0; các cạnh chỉ chạm điểm không tạo cửa cho robot có kích thước. Do chưa có mã định nghĩa d_shape, d_corridor, d_distance, d_trav và cost của dataset, báo cáo không suy đoán công thức các trường đó. Đồ thị được dựng lại từ hình học bằng DACN.

Giả định mô phỏng: cạnh dài nhất mỗi map = 20 m; bán kính robot 0,10 m; biên an toàn 0,05 m. Đây chưa phải kích thước vật lý do anh Huy xác nhận. Start/goal được chọn xa nhau trong thành phần liên thông an toàn lớn nhất, giữ nguyên giữa các chế độ. Metadata lưu phép scale, nguồn, hash và điểm đầu/cuối.

Robot được kiểm tra bằng tâm điểm với khoảng cách tối thiểu **0,15 m tới vật cản và biên ngoài** trên toàn đoạn chuyển động; tương đương điều kiện tránh vật cản đã nở cho robot đĩa trong kiểm tra này. Không cộng bán kính lần thứ hai vào hình học đã nở. Biên phân rã vùng không phải vật cản.''')
 parts.append(table(['Map','Graph gốc: vùng/cạnh','Cạnh gốc W=0','Graph dựng lại: vùng/cạnh có hướng','Cách phân rã'],[[n,f"{data[n]['import_audit']['source_graph_vertices']}/{data[n]['import_audit']['source_graph_edges']}",data[n]['import_audit']['zero_shared_length_edges'],f"{data[n]['import_audit']['rebuilt_vertices']}/{data[n]['import_audit']['rebuilt_directed_edges']}",data[n]['map']['provenance']['decomposition_backend']] for n in names]))
 parts.append('Map `narrow` làm ACD cũ báo lỗi, nên importer dùng constrained Delaunay rồi ghép vùng lồi bằng hàm DACN. Đã kiểm tra độ phủ và chồng lấn. Lưới 0,2 m bỏ sót lối nối của narrow; lưới chính dùng 0,1 m và đã đối chiếu thêm 0,05 m. Các thành phần liên thông được tính trên lưới, không phải chứng minh liên thông liên tục.')
 parts.append('''## 2. Shape, corridor và distance

### Shape — hình dạng của một vùng

AR = λmax/λmin, với hai eigenvalue của covariance cho phân bố **đều theo diện tích** polygon. Không lấy căn và không dùng covariance của riêng các đỉnh. Compactness C = P²/(4πA). AR và C càng lớn thường biểu thị vùng kéo dài/kém gọn. Trong heuristic, chuẩn hóa từng đặc trưng trên map rồi tính Qshape = 1 − (norm(AR)+norm(C))/2; đóng góp tối đa 0,08 điểm.

Ví dụ hai hình cùng diện tích 4 m²: vuông 2×2 có AR=1, C≈1,27; chữ nhật 4×1 có AR=16, C≈1,99. Vùng vuông thuận lợi hơn theo riêng shape, nhưng vùng dài vẫn có thể là lối đi bắt buộc.

![Shape](figures/shape.png)

### Corridor — hành lang tạo bởi chuỗi vùng

Với sequence R1→R2→…→Rk, corridor Ω = R1 ∪ R2 ∪ … ∪ Rk. Hai vùng liên tiếp có portal chung dài W. Code thu hai đầu portal một khoảng r = robot_radius+safety_margin, nên Ws=max(0,W−2r). Conductance vùng = ΣW/P; safe_conductance dùng Ws. Đặc trưng cạnh Ts=Ws×min(CL_i,CL_j), đơn vị m², không phải xác suất an toàn.

Ví dụ W=1,2 m, r=0,15 m thì Ws=0,9 m. Nếu mean clearance hai bên 0,5 và 0,3 m thì Ts=0,27 m². Corridor không phải một con số shape và không đồng nghĩa clearance; nó là tập không gian cho phép planner hoạt động. Cửa rộng tăng lựa chọn chuyển tiếp, nhưng vẫn phải kiểm tra va chạm thực tế.

![Corridor](figures/corridor.png)

### Distance — gần đích và chi phí đi thực tế

Heuristic vùng dùng d_i=||centroid_i−centroid_goal|| và D=||centroid_start−centroid_goal||. Progress=clip(1−d_i/D,0,1); detour=clip((d_i−D)/D,0,1). Hai đóng góp là +0,24×progress và −0,12×detour. Đây là khoảng cách Euclid giữa centroid, không phải chiều dài đường tránh vật cản và không phải khoảng cách từ node cây hiện tại.

Ví dụ D=10 m: d_i=4 m cho progress=0,6, cộng 0,144; d_i=14 m cho detour=0,4, trừ 0,048. Có thể phải đi xa goal trước để vòng qua tường. Vì vậy distance cần được xét cùng topology, portal và vùng bắt buộc.

![Distance](figures/distance.png)

## 3. Kiểm tra tiêu chí và cách chấm điểm

LLM nhận các vùng/centroid, diện tích/đường kính, shape, clearance, degree/conductance, cạnh có hướng và các độ rộng portal, cùng start/goal và thông số robot. Bản thí nghiệm bỏ thông tin lặp, làm tròn số 5 chữ số thập phân và yêu cầu trả `region_scores` đủ mọi ID. Khi cập nhật động có thêm số node được chấp nhận theo vùng, tập vùng đã khám phá, bước lặp, prior hiện tại và độ dài đường tốt nhất nếu có.

**Heuristic có công thức cố định; LLM đánh giá theo prompt định tính.** Không trình bày công thức heuristic như nội suy nội bộ của LLM. Cả hai trả điểm [0,1]. Sampler chọn P(R_i)=s_i/Σs_j, sau đó lấy mẫu đều trong vùng; điểm 0,8 không có nghĩa xác suất thành công 80%. Ví dụ điểm 0,8; 0,4; 0,2 tương ứng xác suất chọn vùng khoảng 57,1%; 28,6%; 14,3%.

Chuẩn hóa min–max theo từng map; thiếu dữ liệu hoặc cả map có cùng giá trị thì dùng 0,5 trung tính. Tổng đóng góp được chặn [0,1]. Các trọng số hiện là thiết kế heuristic, chưa được học hay tối ưu thống kê.''')
 parts.append(table(['Thành phần heuristic vùng','Đóng góp'],[['Điểm nền','+0,20'],['Tiến gần goal','+0,24 × progress'],['Số kết nối giữ lại (safe_degree)','+0,14 × norm'],['Mean clearance','+0,14 × norm'],['Diện tích','+0,08 × norm'],['Shape','+0,08 × Qshape'],['Detour','−0,12 × detour'],['Vùng bắt buộc trong topology','+0,20'],['Vùng start hoặc goal','+0,12']]))
 parts.append('Năm nhóm đặc trưng gồm Size, Shape, Clearance, Connectivity/Conductance và Portal. Công thức heuristic vùng hiện chỉ dùng một phần: area thay vì cả diameter; safe_degree thay vì trực tiếp conductance; portal chủ yếu vào cost cạnh. Không nên nói cả năm nhóm đều có một trọng số độc lập trong điểm vùng.')
 parts.append('Cost cạnh heuristic = clip(0,18 + 0,22·norm(length) + 0,15·(1−norm(W)) + 0,15·(1−norm(Ws)) + 0,12·(1−norm(Ts)) − 0,10·edge_progress + 0,08·max(−edge_progress,0) + 0,10·(1−score_target), 0,01, 1). length là khoảng cách centroid hai vùng; edge_progress=(d_source−d_target)/max(d_source,d_target,ε). Chi phí này không có đơn vị mét và chưa được hiệu chỉnh để tương đương chiều dài đường.')
 examples=[]
 for name,rid in [('flappy','C16'),('flappy','C8'),('narrow','C5')]:
  r=next(x for x in data[name]['analysis']['score_audit']['rows'] if x['id']==rid);d=r['descriptors'];c=r['contributions']
  examples.append([name+'/'+rid,num(r['baseline_score'],3),num(r['llm_score'],3),num(d['area'],3),num(d['aspect_ratio']),num(d['mean_clearance'],3),d['safe_degree'],num(c['required_bottleneck'])])
 parts.append(table(['Vùng','Heuristic','LLM','A (m²)','AR','CL (m)','safe_degree','Cộng bottleneck'],examples))
 r=next(x for x in data['narrow']['analysis']['score_audit']['rows'] if x['id']=='C5')
 parts.append('Ví dụ tính đầy đủ narrow/C5: '+ ' + '.join(f"{k}({num(v,4)})" for k,v in r['contributions'].items() if v)+' = '+num(r['baseline_score'],4)+'. Vùng này có thêm 0,20 vì bỏ nó sẽ làm mất đường start→goal đang có. Điểm LLM khác vì không bị ràng buộc bởi trọng số heuristic. Code đã sửa trường hợp đồ thị vốn không có đường: không được đánh dấu mọi vùng trung gian là bottleneck.')
 parts.append('### Đối chiếu từng nhóm bằng bỏ một thành phần (ablation)\n\nMỗi ô là số lần thành công/10; chỉ bỏ thành phần được ghi khỏi điểm heuristic, giữ phần còn lại và cùng ngân sách.')
 abm=['heuristic','heuristic_no_shape','heuristic_no_distance','heuristic_no_clearance','heuristic_no_connectivity']
 parts.append(table(['Chế độ']+names,[[m]+[str(next(r for r in data[n]['runs']['summary'] if r['mode']==m)['successes'])+'/10' for n in names] for m in abm]))
 parts.append('Trong narrow, bỏ distance làm thành công giảm từ 6/10 xuống 2/10; trong flappy, bỏ một số thành phần lại tăng thành công. Đây là bằng chứng trọng số chưa tốt đồng đều trên mọi map, không phải bằng chứng một tiêu chí luôn vô ích. Bỏ connectivity ở đây bỏ cả safe_degree và thưởng bottleneck; chưa tách riêng hai hiệu ứng. Với 10 seed và một prior/model/map, chưa đủ kết luận thống kê tổng quát.')
 parts.append('## 4. Sequence hợp lệ và hành lang chứa đường tốt\n\nKiểm tra ba tầng: (1) đúng ID/start/goal và cạnh có hướng; (2) tìm được đường tránh vật cản trong hợp các vùng; (3) độ dài tối ưu trong corridor có bằng tối ưu trên toàn **cùng lưới** không. Kiểm tra union không bắt đường phải đi đúng thứ tự sequence. Lưới là 8 hướng, không chứng minh tối ưu liên tục.')
 seqrows=[]
 for n in names:
  for mode,v in data[n]['analysis']['sequence_audit'].items():
   seqrows.append([n,'heuristic' if mode=='heuristic' else 'LLM vùng + cost hình học',v['topology_valid'],v.get('corridor_grid_feasible'),num(v.get('global_grid_length')),num(v.get('corridor_grid_length')),num(v.get('corridor_vs_global_grid_gap_pct'))])
 parts.append(table(['Map','Cách chọn sequence','Topo hợp lệ','Đường trong corridor, h=0,1','L toàn map (m)','L corridor (m)','Chênh (%)'],seqrows))
 parts.append('`hole` giữ được tối ưu lưới dù chính đường tham chiếu được Dijkstra chọn có một phần ngoài corridor: có đường khác đồng tối ưu. `flappy` có corridor hợp lệ nhưng dài hơn khoảng 4,7%. `narrow` và `room` chưa tìm được đường trong corridor đã chọn trên cả lưới 0,1 m và kiểm tra 0,05 m cho sequence heuristic. Điều này không chứng minh không có đường liên tục; nó đủ để không công nhận sequence là đã được xác thực về hình học.')
 parts.append('Một phát hiện cụ thể: trong narrow, trên safe_portal C5→C11, chỉ 23/101 điểm kiểm tra đạt clearance 0,15 m. Việc thu hai đầu portal không bảo đảm toàn phần còn lại cách xa mọi vật cản. Đây là spot check, không phải chứng nhận toàn portal. RRT trong thí nghiệm luôn kiểm tra từng đoạn chính xác, nên không sử dụng nhãn “safe” làm thay thế collision check. Nên giữ nhánh lấy mẫu ngoài corridor hoặc kiểm tra khả thi trước khi khóa planner vào một sequence.')
 parts.append('## 5. Kết quả lấy mẫu và cơ chế giảm điểm\n\n12 chế độ × 10 seed (42–51) × 2.500 bước. Bước mở rộng 0,7 m; nối goal khi cách ≤1,4 m; RRT không rewiring, không goal bias. Chạy đủ ngân sách và giữ kết nối goal tốt nhất. Cùng seed không có nghĩa cùng mọi mẫu ngẫu nhiên. Độ dài trung bình chỉ tính các lần thành công, nên cần đọc cùng tỷ lệ thành công.')
 mainrows=[]
 for n in names:
  for r in data[n]['runs']['summary']:
   if r['mode'] in selected:mainrows.append([n,r['mode'],f"{r['successes']}/{r['runs']}",num(r['path_length_mean']),num(r['path_length_stdev']),num(r['first_solution_iteration_mean'],0)])
 parts.append(table(['Map','Chế độ','Thành công','L TB (m)','SD (m)','Bước tìm đường đầu TB'],mainrows))
 parts.append('![Tỷ lệ thành công](figures/success_rates.png)\n\n`none` lấy mẫu bounding box; `region_area` chọn vùng theo diện tích (đều trên không gian tự do phân rã); `region_uniform` cho mọi vùng cùng điểm. Cả hai đối chứng không dùng LLM. Flappy có region_area 10/10 tương tự LLM; vì thế không thể gán toàn bộ chênh lệch với none cho suy luận LLM. Narrow vẫn cho thấy prior LLM tốt hơn các đối chứng về tỷ lệ thành công ở ngân sách này. Chi phí lấy điểm LLM ban đầu không nằm trong thời gian planner.')
 parts.append('### Giảm điểm theo số node được thêm\n\nSau mỗi 20 node **được chấp nhận trong chính vùng i**, cập nhật s_i=max(min(0,05,s_i_initial),(1−α)s_i). Mẫu bị từ chối không làm giảm điểm. Ví dụ s=0,8, α=15%: sau 20 node còn 0,68; sau 40 node còn 0,578. Xác suất lấy mẫu được chuẩn hóa lại nên giảm điểm một vùng làm tỷ trọng vùng khác tăng. Khi prior mới được nhận, áp lại decay theo tổng số node đã thêm.')
 parts.append(table(['Mức giảm']+names,[[mode]+[str(next(r for r in data[n]['runs']['summary'] if r['mode']==mode)['successes'])+'/10' for n in names] for mode in ['llm','llm_decay_5pct','llm_decay_15pct','llm_decay_30pct']]))
 parts.append('Chưa có mức giảm thắng nhất quán: narrow giảm 5% hoặc 15% làm tỷ lệ thành công kém hơn prior tĩnh; flappy giữ 10/10 nhưng đường trung bình dài hơn. Chưa nên bật decay mặc định. Cần kiểm tra thêm cơ chế chỉ giảm ở vùng không tạo tiến triển, đồng thời bảo vệ bottleneck; đây là hướng tiếp theo, chưa được triển khai trong thử nghiệm này.')
 extra=[]
 for n in ['narrow','room']:
  for r in load(maps/n/'supplement.json')['summary']:extra.append([n,r['mode'],f"{r['successes']}/5",num(r['path_length_mean'])])
 parts.append('### Kiểm tra bổ sung: 10.000 bước, 5 seed\n\nCohort riêng, không gộp vào bảng 2.500 bước. Tăng ngân sách vì một số chế độ chưa có đường để so sánh.\n'+table(['Map','Chế độ','Thành công','L TB (m)'],extra))
 parts.append('## 6. Gọi lại LLM: hiệu quả, độ trễ và chi phí\n\nPilot thực chạy trên hole, seed 42, 2.500 bước, cùng prior khởi tạo. `new_region` gọi khi cây thêm node vào vùng mới, cooldown 100 bước; `interval` gọi mỗi 250 bước. Giới hạn hai lần gọi thêm. Lỗi API giữ prior cũ. Đây là lời gọi đồng bộ nên planner chờ trong lúc gọi API. Hai pilot n=1 chỉ là kiểm tra khả thi, không đủ chọn chính sách tốt nhất.')
 static=next(r for r in data['hole']['runs']['results'] if r['mode']=='llm' and r['seed']==42)
 dynrows=[['LLM tĩnh',num(static['path_length']),static['first_solution_iteration'],0,'0,00',num(static['planning_seconds_excluding_api'],3)]]
 for trigger in ['new_region','interval']:
  r=load(maps/'hole'/('dynamic_'+trigger+'.json'));dynrows.append([trigger,num(r['path_length']),r['first_solution_iteration'],len(r['refresh_results']),num(r['api_seconds']),num(r['planning_seconds_excluding_api'],3)])
 parts.append(table(['Chính sách','L (m)','Bước tìm đường đầu','Lần gọi thêm','Chờ API thêm (s)','Planner, bỏ API (s)'],dynrows))
 parts.append('Chi phí tạo prior hole ban đầu là '+num(data['hole']['llm_prior']['metadata']['latency_seconds'])+' giây, dùng chung và chưa tính trong bảng pilot. Pilot interval/new_region có thể cải thiện chiều dài riêng seed này nhưng thêm khoảng 191/229 giây chờ; chưa hợp lý cho điều khiển thời gian thực. Hướng phù hợp để thử tiếp là cache prior, chỉ gọi khi trì trệ và cập nhật bất đồng bộ; hiện prototype chưa có cập nhật bất đồng bộ.')
 parts.append(table(['Map','Model cố định: token input/output','Độ trễ tạo prior thành công (s)','Cost provider báo (USD)'],[[n,' / '.join(str(sum((u or {}).get(k,0) for u in data[n]['llm_prior']['metadata']['usage_per_attempt'])) for k in ['prompt_tokens','completion_tokens']),num(data[n]['llm_prior']['metadata']['latency_seconds']),data[n]['llm_prior']['metadata']['reported_cost_usd']] for n in names]))
 parts.append('Model dùng để so sánh: `nvidia/nemotron-3-super-120b-a12b:free`; 4 prior đủ toàn bộ ID. 4 lần refresh thành công cũng được provider báo cost=0. Cohort thử router `openrouter/free` trước đó có 4 lời gọi lỗi (token limit/JSON không hợp lệ), và lần đầu dùng model cố định cho room bị timeout. Tất cả usage nhận được báo 0 USD; request timeout không có usage nên không khẳng định tổng phí thực tế bằng 0. Có thể kiểm tra lịch sử tài khoản để đối soát. Log giữ kết quả lỗi, không dùng điểm giả thay thế.')
 replay=[]
 for n in names:
  rows=data[n]['analysis']['refresh_schedule_replay']
  for trigger in ['new_region','interval']:
   for cooldown in [100,500]:
    counts=[r['potential_calls'] for r in rows if r['trigger']==trigger and r['cooldown']==cooldown]
    replay.append([n,trigger,cooldown,num(mean(counts),1),min(counts),max(counts)])
 parts.append('Số lần gọi tiềm năng từ replay trace LLM tĩnh, chưa áp cap=2. Chỉ dùng để dự trù lượng gọi; không phải kết quả hiệu năng của planner động.\n'+table(['Map','Trigger','Cooldown','Số gọi TB','Min','Max'],replay))
 parts.append('''## 7. So sánh none và LLM: định nghĩa overlap

- **Vùng trên đường cuối:** Jaccard=100·|A∩B|/|A∪B|, bỏ thứ tự và số lần lặp.
- **Chuỗi vùng có thứ tự:** 100·2·LCS(a,b)/(|a|+|b|). LCS là dãy con chung dài nhất, có xét thứ tự.
- **Vùng cây đã khám phá:** Jaccard của tập vùng có node cây được chấp nhận; đây không phải tập vùng trên đường cuối.
- **Đường hình học:** 100·[length(P∩buffer(Q,ε))+length(Q∩buffer(P,ε))]/[length(P)+length(Q)], ε=0,2 m. Chỉ đo mức gần nhau theo chiều dài, không chứng minh tối ưu. Phụ thuộc ngưỡng ε.

Nếu một bên không có đường, ba overlap đường/sequence để null và chỉ tổng hợp những seed cả hai thành công. Tỷ lệ thành công báo riêng, không đổi thất bại thành overlap 0%. Vùng khám phá vẫn so sánh được kể cả thất bại. Đường nằm trên biên chung dùng quy tắc ưu tiên vùng trước rồi ID để tránh đếm đôi.''')
 ov=[]
 for n in names:
  rows=data[n]['analysis']['none_vs_llm_overlap'];ov.append([n,sum(r['both_successful'] for r in rows),*[num(mean([r.get(k) for r in rows])) for k in ['region_jaccard_pct','sequence_lcs_pct','path_coverage_pct','explored_region_jaccard_pct']]])
 parts.append(table(['Map','Cặp cùng thành công/10','Vùng đường (%)','LCS (%)','Đường ε=0,2 (%)','Vùng cây, đủ 10 seed (%)'],ov))
 parts.append('Ví dụ hole seed 42: tập vùng đường trùng 100%, nhưng LCS chỉ 83,33% và đường hình học gần nhau 21,49%. Vì thế “trùng bao nhiêu %” phải nói rõ đối tượng. Ở cohort 10.000 bước, narrow có một cặp cùng thành công (seed 42): Jaccard 83,33%; LCS 64,29%; độ phủ đường 35,94%. Không dùng một cặp này đại diện mọi lần chạy.')
 parts.append('## Hình bản đồ và dẫn chứng triển khai\n\nMàu xám là vật cản, viền xanh nhạt là phân rã, đường xanh lá là tham chiếu lưới. Đường none/LLM chỉ hiển thị nếu seed 42 tìm được; thiếu nét vẽ không có nghĩa file bị thiếu.')
 for n in names:parts.append(f'![Map {n}](figures/map_{n}.png)')
 parts.append('''Dẫn chứng trong repo (tên hàm có thể tìm trực tiếp):

| Nội dung | File / hàm |
|---|---|
| Shape và covariance theo diện tích | convex-region-graph/region_descriptors.py: polygon_moments |
| Clearance, conductance, portal traversability | convex-region-graph/region_descriptors.py: enrich_graph |
| Portal thu hẹp hai đầu | convex-region-graph/build_graph.py: erode_portal |
| Điểm vùng, cost cạnh, bottleneck | convex-region-graph/scoring.py |
| Tỷ lệ chọn vùng production | sampling-based-path-finding-main/src/path_finder/include/path_finder/sampler.h: setRegionPrior |
| Import .poly, kiểm tra độ phủ | convex-region-graph/research/import_dataset.py |
| Kiểm tra đoạn, Dijkstra lưới, overlap | convex-region-graph/research/geometry.py |
| Tính contribution và audit sequence | convex-region-graph/research/scoring_audit.py |
| Sự kiện giảm điểm/gọi lại model | convex-region-graph/research/adaptive.py |
| RRT độc lập có trace | convex-region-graph/research/rrt_experiment.py |
| API thật và usage/latency | convex-region-graph/research/llm_study.py |
| Chạy lại thí nghiệm | convex-region-graph/research/README.md |

Đã chạy qua 78 test cũ và 16 test nghiên cứu về collision toàn đoạn, lưới/corridor, overlap, bottleneck, trigger/cooldown, decay và khả năng tái lập. Đây là kiểm thử Python; chưa biên dịch/chạy ROS. Các JSON chứa cả lần thất bại và trace node được chấp nhận, giúp kiểm tra lại bảng kết quả.

Các việc còn cần xác nhận trước khi dùng làm kết luận luận văn: đơn vị/bán kính thật của dataset; công thức d_* từ tác giả graph gốc; chạy cùng thí nghiệm trong ROS; thêm seed và nhiều prior LLM độc lập. Không công bố “LLM luôn tối ưu”, “safe_portal bảo đảm an toàn” hoặc “đường lưới là tối ưu liên tục”.''')
 md='\n\n'.join(parts)+'\n';(output/'REPORT.md').write_text(md)
 try:
  import markdown
  body=markdown.markdown(md,extensions=['tables','fenced_code'])
  for p in figdir.glob('*.png'):body=body.replace('figures/'+p.name,'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode())
  (output/'REPORT.html').write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GCR · Báo cáo thí nghiệm</title><style>body{font-family:system-ui,sans-serif;max-width:1120px;margin:40px auto;padding:0 24px;color:#19354b;line-height:1.65}h1,h2,h3{line-height:1.25}h1{font-size:36px}h2{margin-top:46px;border-top:1px solid #dde6ed;padding-top:25px}table{border-collapse:collapse;width:100%;font-size:13px;display:block;overflow-x:auto}th,td{padding:9px 12px;border:1px solid #dce3e9;text-align:left}th{background:#123451;color:white}tr:nth-child(even){background:#edf4f9}img{display:block;max-width:100%;height:auto;margin:24px auto}code{background:#edf2f6;padding:2px 4px;overflow-wrap:anywhere}pre{padding:12px;background:#edf2f6;overflow:auto}p,li{overflow-wrap:anywhere}@media print{body{max-width:none;margin:0;font-size:10pt}h2{break-before:page}img,table{break-inside:avoid}}</style><body>'+body+'</body></html>')
 except ImportError:pass
 print('Report:',output,flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('maps',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.maps,a.output)
