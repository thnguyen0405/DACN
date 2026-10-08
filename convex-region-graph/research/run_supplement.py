"""Separate higher-budget sensitivity check; never pool with the main cohort."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.geometry import World,overlap_metrics
from research.rrt_experiment import run_rrt
from research.run_study import summarize
from scoring import deterministic_scoring

def run(directory,iterations=10000,repeats=5):
 directory=Path(directory);g=json.loads((directory/'graph.json').read_text());w=World(json.loads((directory/'map.json').read_text()))
 p=g['planning'];base=deterministic_scoring(g,p['start_region'],p['goal_region'])
 modes={'none':None,'heuristic':{x['id']:x['score'] for x in base['region_scores']}}
 if (directory/'llm_prior.json').exists():modes['llm']=json.loads((directory/'llm_prior.json').read_text())['scores']
 rows=[]
 for seed in range(42,42+repeats):
  for mode,scores in modes.items():
   record=run_rrt(w,g,scores,seed=seed,iterations=iterations);record['mode']=mode;rows.append(record)
  print(directory.name,seed,flush=True)
 overlap=[]
 if 'llm' in modes:
  for seed in range(42,42+repeats):
   a=next(r for r in rows if r['seed']==seed and r['mode']=='none');b=next(r for r in rows if r['seed']==seed and r['mode']=='llm')
   overlap.append({'seed':seed,'both_successful':a['success'] and b['success'],**overlap_metrics(a['path'],b['path'],g)})
 (directory/'supplement.json').write_text(json.dumps({'iterations':iterations,'repeats':repeats,'results':rows,'summary':summarize(rows),'overlap':overlap},ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--iterations',type=int,default=10000);p.add_argument('--repeats',type=int,default=5);a=p.parse_args();run(a.directory,a.iterations,a.repeats)
