"""Original explanatory figures and plots built from recorded study results."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/dacn-matplotlib')
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch, Rectangle
from region_descriptors import polygon_moments

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
COLORS={'ink':'#123451','green':'#21896b','blue':'#3575c8','orange':'#d79027','gray':'#b9c2cb'}


def save(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=180,bbox_inches='tight',facecolor='white')
    fig.savefig(path.with_suffix('.svg'),bbox_inches='tight',facecolor='white')
    plt.close(fig)


def draw_concepts(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(10,4.5));ax.set_aspect('equal');ax.axis('off')
    square=[(0,0),(2,0),(2,2),(0,2)];long=[(4,0.5),(8,0.5),(8,1.5),(4,1.5)]
    for poly,label,color in [(square,'Vùng vuông',COLORS['green']),(long,'Vùng kéo dài',COLORS['blue'])]:
        d=polygon_moments(poly);ax.add_patch(Patch(poly,facecolor=color,alpha=.35,edgecolor=color,lw=2))
        x=np.mean([p[0] for p in poly]);ax.text(x,-.5,f"{label}\nA = {d['area']:.0f} m²   AR = {d['aspect_ratio']:.0f}\nC = {d['compactness']:.2f}",ha='center',va='top')
    ax.set_xlim(-.5,8.5);ax.set_ylim(-2.1,3)
    ax.set_title('SHAPE: cùng diện tích, mức kéo dài khác nhau',loc='left',color=COLORS['ink'],fontsize=17,fontweight='bold')
    ax.text(4,-1.8,'AR = λmax / λmin;  C = P² / (4πA). Vùng dài vẫn có thể là đường bắt buộc.',ha='center',fontsize=11)
    save(fig,output/'shape')
    fig,ax=plt.subplots(figsize=(10,4.5));ax.set_aspect('equal');ax.axis('off')
    for x,label in [(0,'R₁'),(3,'R₂'),(6,'R₃')]:
        ax.add_patch(Rectangle((x,0),3,2,facecolor=COLORS['green'],alpha=.18,edgecolor=COLORS['green'],lw=2));ax.text(x+1.5,.5,label,ha='center',fontsize=18)
    for x in [3,6]:
        ax.plot([x,x],[0,2],color='#999999',lw=5)
        ax.plot([x,x],[.4,1.6],color=COLORS['orange'],lw=10)
        ax.plot([x,x],[.7,1.3],color=COLORS['blue'],lw=5)
    ax.plot([.5,2,4.5,7,8.5],[1,1.2,1,1.2,1],color=COLORS['ink'],lw=2,ls='--')
    ax.text(4.5,2.6,'CORRIDOR: hợp các vùng trong sequence R₁ → R₂ → R₃',ha='center',fontsize=16,fontweight='bold',color=COLORS['ink'])
    ax.text(4.5,-.65,'Vàng: portal gốc W. Xanh: phần sau thu hẹp Ws = max(0, W − 2r).',ha='center')
    ax.text(4.5,-1.25,'r = robot_radius + safety_margin. Corridor còn phải kiểm tra va chạm toàn đoạn.',ha='center')
    ax.set_xlim(-.5,9.5);ax.set_ylim(-1.7,3.2);save(fig,output/'corridor')
    fig,ax=plt.subplots(figsize=(10,5));ax.set_aspect('equal');ax.axis('off')
    ax.add_patch(Rectangle((4,0),1,5,facecolor='#576572'));ax.text(4.5,2.5,'Vật cản',color='white',rotation=90,ha='center',va='center')
    s=(2,2);g=(7,2);q=(2,5.7)
    ax.plot([s[0],g[0]],[s[1],g[1]],'--',color='#cc5252',label='Khoảng cách Euclid: 5 m (đi xuyên vật cản)')
    path=np.array([s,q,(5.7,5.7),g]);ax.plot(path[:,0],path[:,1],color=COLORS['green'],lw=3,label='Đường vòng minh họa; không khẳng định tối ưu')
    for p,label in [(s,'S'),(g,'G'),(q,'Q')]:ax.scatter(*p,s=70,color=COLORS['ink']);ax.text(p[0]-.3,p[1]+.25,label,fontsize=15)
    ax.text(4.5,6.8,'DISTANCE: gần đích theo Euclid chưa chắc dễ đi tới',ha='center',fontsize=16,fontweight='bold',color=COLORS['ink'])
    ax.legend(loc='lower center',bbox_to_anchor=(.5,-.13),frameon=False)
    ax.set_xlim(0,9);ax.set_ylim(-.6,7.3);save(fig,output/'distance')


def map_plot(directory,output):
    directory=Path(directory);data=json.loads((directory/'map.json').read_text())['map'];graph=json.loads((directory/'graph.json').read_text())
    fig,ax=plt.subplots(figsize=(8,7));ax.set_aspect('equal')
    ax.add_patch(Patch(data['boundary'],facecolor='#f4f7fa',edgecolor=COLORS['ink']))
    for poly in data['obstacles']:ax.add_patch(Patch(poly,facecolor='#546271',edgecolor='white'))
    for v in graph['vertices']:ax.add_patch(Patch(v['polygon'],facecolor='none',edgecolor='#7cb5aa',lw=.45,alpha=.7))
    reference=json.loads((directory/'reference.json').read_text())
    if reference:
        points=np.array(reference['path']);ax.plot(points[:,0],points[:,1],color=COLORS['green'],lw=2,label='Tham chiếu lưới 0,1 m')
    if (directory/'runs.json').exists():
        rows=json.loads((directory/'runs.json').read_text())['results']
        for mode,color in [('none',COLORS['blue']),('llm',COLORS['orange'])]:
            r=next((r for r in rows if r['mode']==mode and r['seed']==42 and r['success']),None)
            if r:
                points=np.array(r['path']);ax.plot(points[:,0],points[:,1],color=color,lw=1.8,label=mode+' — seed 42')
    for key,label in [('start','S'),('goal','G')]:
        point=data[key];ax.scatter(*point,s=80,color=COLORS['ink'],zorder=9);ax.annotate(label,point,xytext=(5,6),textcoords='offset points',fontsize=13,fontweight='bold')
    ax.set_title(directory.name+' | '+str(len(graph['vertices']))+' vùng sau chuyển đổi',loc='left',fontsize=16,fontweight='bold',color=COLORS['ink'])
    ax.set_xlabel('m (đơn vị mô phỏng)');ax.set_ylabel('m');ax.legend(fontsize=9,loc='best')
    save(fig,Path(output)/('map_'+directory.name))
