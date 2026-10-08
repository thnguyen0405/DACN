"""Explain baseline contributions; assess LLM scores against reference regions."""
import math
from shapely.geometry import Polygon, LineString
from scoring import deterministic_scoring
from research.geometry import path_region_sequence


def audit_scores(graph,start,goal,reference,llm=None):
    baseline=deterministic_scoring(graph,start,goal)
    target=set(path_region_sequence(reference['path'],graph)) if reference else set()
    by_id={v['id']:v for v in graph['vertices']}
    rows=[]
    for record in baseline['region_scores']:
        rid=record['id'];v=by_id[rid]
        rows.append({'id':rid,'on_reference':rid in target,'baseline_score':record['score'],
                     'contributions':record['contributions'],'descriptors':v.get('descriptors'),
                     'llm_score':None if llm is None else llm.get(rid)})
    def ranking(scores):
        chosen=sorted(scores,key=lambda k:(-scores[k],k))[:max(1,math.ceil(.25*len(scores)))]
        return {'top_quarter_regions':chosen,'reference_recall_top_quarter':len(target&set(chosen))/len(target) if target else None,
                'reference_sampling_mass':sum(scores.get(i,0) for i in target)/sum(scores.values()) if sum(scores.values()) else None}
    return {'rows':rows,'baseline':ranking({r['id']:r['score'] for r in baseline['region_scores']}),
            'llm':ranking(llm) if llm else None,
            'interpretation':'reference is one discrete shortest path; alternative equally good corridors may receive low overlap'}


def sequence_audit(graph,sequence,world,grid,reference):
    vertices={v['id']:v for v in graph['vertices']}
    edge_set={(e['source'],e['target']) for e in graph['directed_edges']}
    start,goal=graph['planning']['start_region'],graph['planning']['goal_region']
    valid=bool(sequence) and sequence[0]==start and sequence[-1]==goal and all(i in vertices for i in sequence) and all((a,b) in edge_set for a,b in zip(sequence,sequence[1:]))
    result={'sequence':sequence,'topology_valid':valid,'continuous_optimality':'not_proven'}
    if not valid:return result
    result['portal_spot_checks']=[]
    for source,target in zip(sequence,sequence[1:]):
        edge=next(e for e in graph['directed_edges'] if e['source']==source and e['target']==target)
        if 'safe_portal' not in edge: continue
        a,b=edge['safe_portal']
        accepted=sum(world.valid([(1-t/100)*a[k]+(t/100)*b[k] for k in (0,1)]) for t in range(101))
        result['portal_spot_checks'].append({'source':source,'target':target,
            'valid_samples':accepted,'samples':101,'interpretation':'finite spot check, not a safety proof'})
    from shapely.ops import unary_union
    corridor=unary_union([Polygon(vertices[i]['polygon']) for i in sequence])
    start_point,goal_point=world.data['start'],world.data['goal']
    restricted=grid.shortest(start_point,goal_point,corridor)
    result.update(corridor_grid_feasible=restricted is not None,
                  global_grid_length=reference['length'] if reference else None,
                  corridor_grid_length=restricted['length'] if restricted else None,
                  grid_step_m=grid.step)
    if reference:
        line=LineString(reference['path'])
        result['reference_path_length_inside_corridor_pct']=100*line.intersection(corridor).length/line.length
        result['contains_this_reference_path']=line.difference(corridor).length<1e-8
    if restricted and reference:
        result['corridor_vs_global_grid_gap_pct']=100*(restricted['length']/reference['length']-1)
        result['retains_grid_optimum']=abs(restricted['length']-reference['length'])<1e-8
    else:result.update(corridor_vs_global_grid_gap_pct=None,retains_grid_optimum=False)
    return result
