"""One explicitly labelled live dynamic-LLM pilot, with a strict call cap."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.geometry import World
from research.rrt_experiment import run_rrt
from research.llm_study import StudyProvider

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
 p.add_argument('--env-file',type=Path,required=True);p.add_argument('--trigger',choices=['interval','new_region'],required=True)
 p.add_argument('--iterations',type=int,default=2500);p.add_argument('--max-calls',type=int,default=2)
 a=p.parse_args();graph=json.loads((a.directory/'graph.json').read_text());world=World(json.loads((a.directory/'map.json').read_text()))
 scores=json.loads((a.directory/'llm_prior.json').read_text())['scores']
 provider=StudyProvider(graph,a.directory/('dynamic_'+a.trigger),a.env_file,model=json.loads((a.directory/'llm_prior.json').read_text())['metadata']['requested_model'])
 result=run_rrt(world,graph,scores,iterations=a.iterations,seed=42,refresh=a.trigger,refresh_callback=provider.score,max_calls=a.max_calls)
 result['mode']='live_dynamic_'+a.trigger
 (a.directory/('dynamic_'+a.trigger+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False))
 print(json.dumps({k:result[k] for k in ['mode','success','path_length','wall_seconds','api_seconds','refresh_results']}),flush=True)
