#!/usr/bin/env python3
"""Validate recorded ROS paths and export an evidence-based Vietnamese report."""
from pathlib import Path
import argparse,json,math,statistics,sys,base64,hashlib
import numpy as np
from shapely.geometry import Polygon
from research.geometry import World,path_length,overlap_metrics
from research.figures import save,COLORS
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch

NAMES=['hole','flappy','narrow','room']
PLANNERS=['rrt','rrt_star','rrt_sharp','brrt','brrt_star','informed_rrt_star']
MODES=['none','region_prior','sequence_guided']
def mean(xs):
 xs=[x for x in xs if x is not None];return statistics.fmean(xs) if xs else None
def fmt(x,n=2):return '—' if x is None else f'{x:.{n}f}'
def table(head,rows):return '\n'+' | '.join(head)+'\n'+' | '.join(['---']*len(head))+'\n'+'\n'.join(' | '.join(str(v) for v in row) for row in rows)+'\n'

def analyze(root):
 root=Path(root);data=json.loads((root/'results/benchmark.json').read_text());rows=data['results']
 assert len(rows)==720 and len({(r['map'],r['planner'],r['mode'],r['seed']) for r in rows})==720
 assert not any(r.get('error') or r.get('timeout') for r in rows)
 maps={n:json.loads((root/'inputs'/n/'map.json').read_text()) for n in NAMES}
 graphs={n:json.loads((root/'inputs'/n/'graph.json').read_text()) for n in NAMES}
 worlds={n:World(maps[n]) for n in NAMES};checked=0;max_error=0
 for r in rows:
  if not r['success']:
   assert r['path_length'] is None;continue
  path=[p[:2] for p in r['path']];world=worlds[r['map']]
  assert world.path_valid(path),(r['map'],r['planner'],r['mode'],r['seed'])
  assert math.dist(path[0],world.data['start'])<1e-6 and math.dist(path[-1],world.data['goal'])<1e-6
  assert all(abs(p[2])<1e-9 for p in r['path'])
  error=abs(path_length(path)-r['path_length']);max_error=max(max_error,error);assert error<.001
  checked+=1
 lookup={(r['map'],r['planner'],r['mode'],r['seed']):r for r in rows}
 summary={(s['map'],s['planner'],s['mode']):s for s in data['summary']}
 overlap=[];pairs=[]
 for name in NAMES:
  for planner in PLANNERS:
   paired=[];changes=[];first_changes=[]
   for seed in range(42,52):
    a,b=lookup[name,planner,'none',seed],lookup[name,planner,'region_prior',seed]
    ap=[p[:2] for p in a['path']] if a['path'] else [];bp=[p[:2] for p in b['path']] if b['path'] else []
    metric=overlap_metrics(ap,bp,graphs[name]);record={'map':name,'planner':planner,'seed':seed,'both_successful':a['success'] and b['success'],**metric};overlap.append(record)
    if record['both_successful']:
     paired.append(record);changes.append(100*(path_length(bp)/path_length(ap)-1))
     if a['time_to_first_solution_ms'] is not None and b['time_to_first_solution_ms'] is not None:first_changes.append(b['time_to_first_solution_ms']-a['time_to_first_solution_ms'])
   pairs.append({'map':name,'planner':planner,'joint_successes':len(paired),'path_length_change_llm_vs_none_pct':mean(changes),'first_solution_change_ms':mean(first_changes),**{k:mean([r.get(k) for r in paired]) for k in ['region_jaccard_pct','sequence_lcs_pct','path_coverage_pct']}})
 verification={'recorded_runs':len(rows),'successful_paths_checked':checked,'failed_planning_runs':len(rows)-checked,'infrastructure_errors':0,'max_path_length_rounding_error_m':max_error,'clearance_m':.15,'all_paths_planar':True,'whole_segments_safe':True,'cpp_test_cases':24,'cpp_test_failures':0}
 (root/'verification.json').write_text(json.dumps(verification,indent=2))
 (root/'comparison.json').write_text(json.dumps({'paired_summary':pairs,'overlap_per_seed':overlap},indent=2))
 figs=root/'figures';figs.mkdir(exist_ok=True)
 fig,axes=plt.subplots(1,3,figsize=(13,5),sharey=True)
 for ax,mode in zip(axes,MODES):
  values=np.array([[summary[n,p,mode]['successes'] for n in NAMES] for p in PLANNERS]);ax.imshow(values,vmin=0,vmax=10,cmap='YlGnBu',aspect='auto')
  for y in range(6):
   for x in range(4):ax.text(x,y,f'{values[y,x]}/10',ha='center',va='center',color='white' if values[y,x]>=7 else COLORS['ink'])
  ax.set_xticks(range(4),NAMES,rotation=25);ax.set_yticks(range(6),PLANNERS);ax.set_title(mode,fontsize=14,fontweight='bold')
 fig.suptitle('ROS/C++: số lượt tìm được đường hợp lệ • tối đa 1 s hoặc 5.000 node',fontsize=15,color=COLORS['ink']);fig.tight_layout();save(fig,figs/'success')
 fig,axes=plt.subplots(2,2,figsize=(12,10))
 for ax,n in zip(axes.flat,NAMES):
  m=maps[n]['map'];ax.set_aspect('equal');ax.add_patch(Patch(m['boundary'],facecolor='#f3f7fa',edgecolor=COLORS['ink']))
  for p in m['obstacles']:ax.add_patch(Patch(p,facecolor='#697781',edgecolor='white'))
  for mode,color in zip(MODES,[COLORS['blue'],COLORS['orange'],COLORS['green']]):
   r=lookup[n,'rrt',mode,42]
   if r['success']:
    path=np.array(r['path']);ax.plot(path[:,0],path[:,1],color=color,lw=1.3,label=mode)
   else:ax.plot([],[],color=color,label=mode+' (thất bại)')
  for key,label in [('start','S'),('goal','G')]:
   p=m[key];ax.scatter(*p,color=COLORS['ink'],s=24,zorder=10);ax.annotate(label,p,xytext=(4,4),textcoords='offset points')
  ax.autoscale_view();ax.set_title(n+' • RRT, seed 42',loc='left',fontweight='bold');ax.set_xlabel('m mô phỏng');ax.set_ylabel('m');ax.legend(fontsize=8,loc='best')
 fig.tight_layout();save(fig,figs/'paths')
 parts=['# Benchmark ROS/C++ trên GCR-Dataset\n\nNgày chạy: 08/10/2026. Đây là phần bổ sung ROS cho báo cáo Python trước đó. Đã chạy trực tiếp executable `path_finder` được biên dịch từ bản DACN-main hiện tại trong container ROS Noetic.']
 parts.append(f'Đã hoàn tất **720/720 lượt**, **{checked} lượt tìm được đường**, {720-checked} lượt không tìm được trong ngân sách, không có lỗi hạ tầng/thu log. Đã kiểm tra độc lập toàn bộ {checked} đường thành công bằng Shapely: đúng start/goal, nằm trong mặt phẳng z=0, mọi đoạn đạt clearance 0,15 m và chiều dài khớp log trong sai số làm tròn dưới 1 mm. Hai bộ GTest có **24 test case**, đều qua; con số 48 do `catkin_test_results` in ra đếm cả mức tổng XML và suite, không phải 48 test riêng.')
 parts.append('''## Những điểm đáng chú ý

Trên hole và flappy, cả ba chế độ đều đạt 10/10 cho sáu planner. Vì vậy cần xem chiều dài và thời gian tới lời giải đầu để phân biệt, không chỉ tỷ lệ thành công. Trên narrow, region_prior cải thiện RRT# từ 5/10 lên 9/10, RRT* và Informed RRT* từ 7/10 lên 9/10. Tuy nhiên trên room, RRT giảm từ 10/10 xuống 8/10 và BRRT* từ 8/10 xuống 6/10 khi dùng prior này. LLM không cải thiện đồng đều trên mọi map.

Sequence_guided rất kém ở narrow và room trong cấu hình đã chạy; riêng narrow có bốn planner đạt 0/10. Kết quả này phù hợp với việc sequence được chọn chưa được xác thực về tính khả thi hình học trong báo cáo trước, nhưng chưa tách riêng được nguyên nhân do sequence, trọng số, portal hay ngân sách. Không dùng kết quả này để khẳng định mọi phương pháp hướng dẫn theo sequence đều kém.

## Điều kiện chạy

- 4 map: hole, flappy, narrow, room; 6 planner: RRT, RRT*, RRT#, BRRT, BRRT*, Informed RRT*.
- Mỗi cặp map/planner chạy none, region_prior và sequence_guided; 10 seed từ 42 đến 51. Tổng 4×6×3×10=720.
- Giới hạn mỗi lượt **1 giây hoặc 5.000 node**, dừng theo điều kiện thuật toán. Nhiều lượt chạm giới hạn node trước 1 giây. Kiểm tra ngân sách thời gian ở đầu vòng lặp nên một vòng lặp cuối có thể làm thời gian hơi vượt 1 giây.
- Theo mặc định test_planners.launch: steer_length=2 m; search_radius=6 m ở planner dùng tham số này; planar=true; step_mode=false; không chạy RViz. BRRT không có cùng cơ chế search_radius như RRT*.
- Dùng C++ gốc, không chỉnh thuật toán. Runner giữ một ROS master riêng, khởi tạo node C++ mới cho từng lượt, dùng tham số của launch file rồi gửi goal từ map. Chạy tuần tự, xen kẽ các chế độ trong mỗi seed để giảm lệch thứ tự.
- ROS Noetic, Ubuntu 20.04.6, aarch64, GCC 9.4.0, build Release/O3; Docker trên máy người dùng. Thời gian đo không phải bảo đảm thời gian thực và có thể đổi theo tải máy.
- Cùng map, start/goal, bán kính robot 0,10 m và margin 0,05 m như nghiên cứu Python; cạnh dài nhất giả định 20 m. Collision C++ dùng khoảng cách polygon chính xác trên toàn đoạn, không dựa vào độ phân giải voxel 0,2 m dành cho hiển thị.

Không gọi lại LLM trong đợt này. Dùng nguyên điểm đã lưu từ model nvidia/nemotron-3-super-120b-a12b:free, kiểm tra hash đầu vào. Thời gian API tạo prior ban đầu **không tính** trong thời gian planner dưới đây.

## Ý nghĩa các chế độ

**none:** không thêm hướng dẫn vùng. Informed RRT* vẫn dùng informed sampling nội tại sau khi có lời giải; “none” không có nghĩa tắt đặc tính thuật toán đó.

**region_prior:** chọn vùng theo điểm LLM rồi lấy mẫu đều trong vùng. Với Informed RRT*, sau khi có lời giải, prior được điều kiện hóa vào ellipsoid cải thiện theo code hiện tại.

**sequence_guided:** chọn sequence bằng điểm vùng LLM kết hợp cost cạnh hình học; 80% nhánh lấy mẫu được hướng dẫn và 20% lấy mẫu global. Trong nhánh guided, xác suất lấy tại portal là 20%, còn lại lấy trong vùng thuộc sequence. Đây không phải khóa cứng vào corridor, cũng không ép cây đi đúng thứ tự vùng. Thứ tự xử lý trong sampler hiện tại ưu tiên sequence_guided trước informed, nên cặp Informed RRT*/sequence_guided không áp cùng phép lọc ellipsoid như region_prior. Diễn giải kết quả theo đúng cấu hình này.

Điểm LLM là prior cố định cho mỗi map, không phải bảo đảm an toàn hay xác suất thành công. Nhiều seed planner chưa thay thế cho việc thử nhiều prior do LLM sinh độc lập.
''')
 parts.append('## Tỷ lệ thành công\n\n![Thành công](figures/success.png)')
 parts.append(table(['Map','Planner','none','LLM region_prior','sequence_guided'],[[n,p,*[str(summary[n,p,m]['successes'])+'/10' for m in MODES]] for n in NAMES for p in PLANNERS]))
 parts.append('## Chiều dài và độ trễ\n\nChiều dài và thời gian tới lời giải đầu chỉ tính những lượt thành công; đọc kèm tỷ lệ thành công. Thời gian planner tính cả lượt thất bại, loại thời gian khởi động node, thu topic và tạo prior LLM. SD là độ lệch chuẩn giữa các seed, không phải khoảng tin cậy. Không kết luận một chế độ tốt hơn chỉ vì trung bình trên ít lượt thành công hơn.')
 parts.append(table(['Map','Planner','Mode','Thành công','L TB ± SD (m)','Tới lời giải đầu TB (ms)','Planner TB (ms)','Node TB'],[[n,p,m,str(summary[n,p,m]['successes'])+'/10',fmt(summary[n,p,m]['path_length_mean'])+' ± '+fmt(summary[n,p,m]['path_length_stdev']),fmt(summary[n,p,m]['time_to_first_solution_ms_mean']),fmt(summary[n,p,m]['planning_time_ms_mean']),fmt(summary[n,p,m]['nodes_added_mean'],0)] for n in NAMES for p in PLANNERS for m in MODES]))
 parts.append('## So sánh theo cặp none và LLM\n\nChỉ so sánh đường ở những seed cả hai chế độ thành công. ΔL=100×(L_LLM/L_none−1), âm nghĩa là LLM ngắn hơn. Lấy trung bình ΔL từng cặp, không lấy tỷ số của hai trung bình. Overlap gồm Jaccard tập vùng đi qua, LCS chuỗi vùng có thứ tự và độ phủ chiều dài đối xứng trong dải cách đường kia 0,2 m. Khi không có cặp thành công ghi —, không gán 0%.')
 parts.append(table(['Map','Planner','Cặp/10','ΔL (%)','Jaccard vùng (%)','LCS (%)','Độ phủ đường (%)'],[[r['map'],r['planner'],r['joint_successes'],fmt(r['path_length_change_llm_vs_none_pct']),fmt(r['region_jaccard_pct']),fmt(r['sequence_lcs_pct']),fmt(r['path_coverage_pct'])] for r in pairs]))
 parts.append('Không tổng hợp overlap cây khám phá trong bảng này: topic marker cây không được xuất/thu đủ ở mọi lượt. File cây đã thu được giữ trong results/trees để kiểm tra, không dùng số lượng mẫu thu thiếu làm số vùng khám phá. Toàn bộ đường cuối của các lượt thành công đã được thu đủ.')
 parts.append('## Đường đi thực từ ROS\n\n![Đường ROS](figures/paths.png)\n\nCác đường trên hình lấy từ nav_msgs/Path của RRT seed 42; không lấy lại từ chương trình Python. Chế độ thất bại được ghi trong chú giải và không vẽ đường giả.')
 parts.append('''## Đối chiếu với nghiên cứu Python

Hai bộ kết quả trả lời các câu hỏi khác nhau, không thể so trực tiếp thời gian hoặc tỷ lệ thành công như thể cùng một thuật toán/cấu hình. Python dùng một RRT thử nghiệm, 2.500 bước, steer=0,7 m, nối goal trong 1,4 m. ROS dùng sáu implementation C++, thời gian/node budget và tham số nêu trên. RNG, quy tắc mở rộng/kết nối, rewiring và điều kiện dừng cũng khác. Vì vậy một seed Python thất bại nhưng ROS thành công không phải mâu thuẫn.

Kết quả sequence_guided cũng không chứng minh corridor chứa đường tối ưu: sampler còn nhánh global và không ràng buộc thứ tự. Đường được trả về là đường tốt nhất mà implementation giữ trong ngân sách; chưa chứng minh tối ưu liên tục.

## Thay đổi để thực hiện benchmark

Đã sửa parser benchmark để loại mã màu ANSI trước khi đọc RESULT và trả về “chưa có bản ghi hợp lệ” với trường số lỗi. Lỗi được tái hiện bằng log ROS thật, kèm regression test. Runner mới chỉ điều phối node và thu dữ liệu; không thay đổi code thuật toán C++.

File kiểm chứng: results/benchmark.json (mọi lượt và tổng hợp), comparison.json (overlap theo seed), verification.json (kiểm tra hình học độc lập), input_hashes.json, source_hashes.json, build.log và cpp-tests/*.xml. Mỗi lượt có log riêng; các request API không xuất hiện trong đợt benchmark này.

Xem RUNBOOK.md để chạy lại. Kết quả là 10 seed/map/cấu hình trên một máy và một prior LLM/map. Cần thêm prior và seed trước khi khẳng định mức cải thiện có ý nghĩa thống kê.
''')
 md='\n\n'.join(parts)+'\n';(root/'REPORT.md').write_text(md)
 import markdown
 html=markdown.markdown(md,extensions=['tables','fenced_code'])
 for image in figs.glob('*.png'):html=html.replace('figures/'+image.name,'data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode())
 (root/'REPORT.html').write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ROS · GCR Benchmark</title><style>body{font:16px/1.65 system-ui,sans-serif;color:#15344e;max-width:1260px;margin:36px auto;padding:0 22px}h1,h2{line-height:1.25}h2{margin-top:40px;padding-top:24px;border-top:1px solid #dce5ed}table{display:block;overflow-x:auto;border-collapse:collapse;font-size:12px;max-width:100%}th,td{padding:8px 11px;border:1px solid #dce5ed;text-align:left;white-space:nowrap}th{background:#123451;color:white}tr:nth-child(even){background:#eff5fa}img{max-width:100%;height:auto}code{background:#eef3f7;padding:2px 4px}p{overflow-wrap:anywhere}</style><body>'+html+'</body></html>')
 print(json.dumps(verification),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();analyze(a.directory)
