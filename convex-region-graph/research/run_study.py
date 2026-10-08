"""Run paired-seed research RRT experiments and sequence/score audits."""
import argparse
import json
import statistics
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scoring import deterministic_scoring, deterministic_edge_cost_records
from llm_region_planner import dijkstra
from research.geometry import World, GridReference, overlap_metrics
from research.rrt_experiment import run_rrt
from research.scoring_audit import audit_scores, sequence_audit
from research.adaptive import AdaptivePrior


def summarize(rows):
    records=[]
    for mode in sorted({r['mode'] for r in rows}):
        selected=[r for r in rows if r['mode']==mode];good=[r for r in selected if r['success']]
        item={'mode':mode,'runs':len(selected),'successes':len(good),'success_rate':len(good)/len(selected)}
        for field in ['path_length','first_solution_iteration','planning_seconds_excluding_api','nodes_added']:
            values=[r[field] for r in selected if r.get(field) is not None]
            item[field+'_mean']=statistics.fmean(values) if values else None
            item[field+'_stdev']=statistics.stdev(values) if len(values)>1 else None
        records.append(item)
    return records


def study(directory,repeats=10,iterations=2500):
    directory=Path(directory);data=json.loads((directory/'map.json').read_text());graph=json.loads((directory/'graph.json').read_text())
    world=World(data);start=graph['planning']['start_region'];goal=graph['planning']['goal_region']
    baseline=deterministic_scoring(graph,start,goal)
    base={r['id']:r['score'] for r in baseline['region_scores']}
    llm=json.loads((directory/'llm_prior.json').read_text())['scores'] if (directory/'llm_prior.json').exists() else None
    areas={v['id']:v['area'] for v in graph['vertices']}
    max_area=max(areas.values())
    modes={'none':(None,0),'region_uniform':({i:1.0 for i in base},0),
           'region_area':({i:a/max_area for i,a in areas.items()},0),'heuristic':(base,0)}
    for label,terms in [('no_shape',['shape']),('no_distance',['goal_progress','detour_penalty']),('no_clearance',['clearance']),('no_connectivity',['connectivity','required_bottleneck'])]:
        scores={r['id']:max(.001,min(1,sum(v for k,v in r['contributions'].items() if k not in terms))) for r in baseline['region_scores']}
        modes['heuristic_'+label]=(scores,0)
    if llm:
        modes['llm']=(llm,0)
        for rate in [.05,.15,.30]:modes[f'llm_decay_{int(rate*100)}pct']=(llm,rate)
    rows=[]
    for seed in range(42,42+repeats):
        for mode,(scores,decay) in modes.items():
            record=run_rrt(world,graph,scores,seed=seed,iterations=iterations,decay=decay)
            record['mode']=mode;rows.append(record)
        print(directory.name,'completed seed',seed,flush=True)
        (directory/'runs.json').write_text(json.dumps({'implementation':'portable Python RRT research harness, not ROS planners','iterations':iterations,'results':rows,'summary':summarize(rows)},ensure_ascii=False,indent=2))
    analyze(directory, rows)


def analyze(directory, rows=None):
    directory=Path(directory)
    data=json.loads((directory/'map.json').read_text());graph=json.loads((directory/'graph.json').read_text())
    world=World(data);start=graph['planning']['start_region'];goal=graph['planning']['goal_region']
    baseline=deterministic_scoring(graph,start,goal);base={r['id']:r['score'] for r in baseline['region_scores']}
    llm=json.loads((directory/'llm_prior.json').read_text())['scores'] if (directory/'llm_prior.json').exists() else None
    stored=json.loads((directory/'runs.json').read_text());iterations=stored['iterations']
    if rows is None: rows=stored['results']
    seeds=sorted({r['seed'] for r in rows})
    grid=GridReference(world,.1);reference=grid.shortest(data['map']['start'],data['map']['goal'])
    sequences={}
    for name,scores in [('heuristic',base),('llm_region_scores_plus_geometric_edge_cost',llm)]:
        if scores is None:continue
        costs=deterministic_edge_cost_records(graph,scores,goal)
        route=dijkstra(graph,{(e['source'],e['target']):e['cost'] for e in costs},start,goal)
        sequences[name]=sequence_audit(graph,route.get('sequence',[]),world,grid,reference)
    audit=audit_scores(graph,start,goal,reference,llm)
    overlap=[];by_key={(r['mode'],r['seed']):r for r in rows}
    if llm:
        for seed in seeds:
            a,b=by_key[('none',seed)],by_key[('llm',seed)]
            record={'seed':seed,'both_successful':a['success'] and b['success'],**overlap_metrics(a['path'],b['path'],graph)}
            aa,bb=set(a['explored_regions']),set(b['explored_regions'])
            record['explored_region_jaccard_pct']=100*len(aa&bb)/len(aa|bb) if aa|bb else None
            overlap.append(record)
    schedule=[]
    for row in [r for r in rows if r['mode']=='llm']:
        history={e['iteration']:e['region'] for e in row['accepted_history']}
        for trigger in ['new_region','interval']:
            for cooldown in [100,500]:
                prior=AdaptivePrior(llm,refresh=trigger,interval=250,cooldown=cooldown,max_calls=10000)
                prior.visited.add(start)
                for i in range(1,iterations+1):prior.observe(i,history.get(i))
                schedule.append({'seed':row['seed'],'trigger':trigger,'cooldown':cooldown,'potential_calls':prior.calls,'mode':'offline_event_replay_no_API_no_counterfactual_performance_claim'})
    results={'sequence_audit':sequences,'score_audit':audit,'none_vs_llm_overlap':overlap,'refresh_schedule_replay':schedule}
    (directory/'analysis.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(directory.name,'complete',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--repeats',type=int,default=10);p.add_argument('--iterations',type=int,default=2500)
    p.add_argument('--analyze-only',action='store_true')
    a=p.parse_args()
    if a.analyze_only:analyze(a.directory)
    else:study(a.directory,a.repeats,a.iterations)
