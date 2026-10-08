"""Import ACD .poly maps without trusting undocumented normalized graph costs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import math
from shapely.geometry import Polygon, Point
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_graph import build_pipeline, build_graph, merge_convex_regions, normalize_polygon
from region_descriptors import enrich_graph
from research.geometry import World, GridReference


def read_poly(path):
    lines=[line.split('#',1)[0].strip() for line in Path(path).read_text().splitlines()]
    lines=[line for line in lines if line]
    count=int(lines[0]); cursor=1; outer=[]; holes=[]
    for _ in range(count):
        n,kind=lines[cursor].split(); n=int(n); cursor+=1
        points=[list(map(float,line.split())) for line in lines[cursor:cursor+n]]; cursor+=n
        if any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in points): raise ValueError('Invalid coordinates')
        order=list(map(int,lines[cursor].split()));cursor+=1
        if sorted(order)!=list(range(1,n+1)):raise ValueError('Invalid .poly vertex ordering')
        poly=[points[i-1] for i in order]
        if kind=='out':outer.append(poly)
        elif kind=='in':holes.append(poly)
        else:raise ValueError('Unknown polygon chain type')
    if cursor!=len(lines) or len(outer)!=1:raise ValueError('Expected exactly one outer boundary, no trailing data')
    geometry=Polygon(outer[0],holes)
    if not geometry.is_valid:raise ValueError('Input polygon is not valid')
    return outer[0],holes


def region_for(point,graph):
    for v in graph['vertices']:
        if Polygon(v['polygon']).covers(Point(point)):return v['id']
    raise ValueError('No region contains endpoint')


def convert(path,output,long_side=20.0,radius=0.1,margin=0.05,step=0.1):
    begin=time.perf_counter();boundary,holes=read_poly(path)
    xs=[p[0] for p in boundary];ys=[p[1] for p in boundary]
    x0,y0=min(xs),min(ys); scale=long_side/max(max(xs)-x0,max(ys)-y0)
    transform=lambda ring:[[(x-x0)*scale,(y-y0)*scale] for x,y in ring]
    data={'map':{'boundary':transform(boundary),'obstacles':[transform(p) for p in holes],
                 'robot_radius':radius,'safety_margin':margin},
          'provenance':{'source':str(Path(path).resolve()),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'unit_assumption':'simulation metres; physical dataset units unspecified',
            'long_side_m':long_side,'source_to_m_scale':scale,'source_origin':[x0,y0],
            'endpoint_policy':'far-apart pair in largest safe 8-neighbour lattice component'}}
    world=World(data);grid=GridReference(world,step)
    start,goal,components=grid.endpoints();data['map'].update(start=start,goal=goal)
    data['provenance']['safe_grid_components']=components
    backend='repository_acd'
    try:
        graph,regions,_=build_pipeline(data)
    except ValueError as exc:
        # Valid polygons with several holes can defeat the legacy bridge/ear
        # clipper. Constrained triangles cover exactly the original free space.
        from shapely import constrained_delaunay_triangles
        triangles=constrained_delaunay_triangles(world.free)
        pieces=merge_convex_regions([normalize_polygon(list(t.exterior.coords)[:-1],1e-9) for t in triangles.geoms],1e-9)
        regions={'regions':[{'id':f'C{i}','polygon':poly} for i,poly in enumerate(pieces)]}
        graph=build_graph(regions,required_clearance=radius+margin)
        geometry={'boundary':data['map']['boundary'],'obstacles':data['map']['obstacles']}
        graph['planning']={**{k:data['map'][k] for k in ('start','goal','robot_radius','safety_margin')},'required_clearance':radius+margin}
        enrich_graph(graph,geometry)
        backend='constrained_delaunay_plus_repository_convex_merge'
        data['provenance']['legacy_decomposition_error']=str(exc)
    from shapely.ops import unary_union
    coverage=unary_union([Polygon(v['polygon']) for v in graph['vertices']])
    mismatch=coverage.symmetric_difference(world.free).area
    overlap=sum(Polygon(v['polygon']).area for v in graph['vertices'])-coverage.area
    if mismatch>1e-7*world.free.area or overlap>1e-7*world.free.area:raise ValueError('Decomposition coverage/overlap mismatch')
    data['provenance']['decomposition_backend']=backend
    data['provenance']['coverage_error_area']=mismatch
    graph['planning'].update(start_region=region_for(start,graph),goal_region=region_for(goal,graph))
    source_graph=Path(str(path)+'-ACD.graph.json')
    audit={}
    if source_graph.exists():
        old=json.loads(source_graph.read_text());audit={
            'source_graph_vertices':len(old['vertices']),'source_graph_edges':len(old['edges']),
            'zero_shared_length_edges':sum(e.get('shared_length',0)<=0 for e in old['edges']),
            'unverified_fields':['d_shape','d_corridor','d_distance','d_trav','cost'],
            'policy':'original graph retained as source data, not used as robot-safe graph; recomputed from .poly',
            'original_graph_sha256':hashlib.sha256(source_graph.read_bytes()).hexdigest()}
    reference=grid.shortest(start,goal)
    audit.update(rebuilt_vertices=len(graph['vertices']),rebuilt_directed_edges=len(graph['directed_edges']),
                 safe_grid_components=components,preparation_seconds=time.perf_counter()-begin)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,value in [('map',data),('graph',graph),('regions',regions),('reference',reference),('import_audit',audit)]:
        (output/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(output.name,json.dumps(audit),flush=True)
    return data,graph,reference


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--long-side',type=float,default=20);p.add_argument('--radius',type=float,default=.1)
    p.add_argument('--margin',type=float,default=.05);p.add_argument('--grid-step',type=float,default=.1)
    a=p.parse_args()
    for source in sorted(a.dataset.glob('*/*.poly')):
        convert(source,a.output/source.stem,a.long_side,a.radius,a.margin,a.grid_step)
