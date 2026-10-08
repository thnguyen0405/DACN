"""Recheck stored region sequences on a finer discrete reference graph."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.geometry import World,GridReference
from research.scoring_audit import sequence_audit

def check(directory,step=.05):
 directory=Path(directory);g=json.loads((directory/'graph.json').read_text());data=json.loads((directory/'map.json').read_text())
 world=World(data);grid=GridReference(world,step);reference=grid.shortest(data['map']['start'],data['map']['goal'])
 analysis=json.loads((directory/'analysis.json').read_text())
 result={'step':step,'reference':reference,'sequence_audit':{key:sequence_audit(g,value['sequence'],world,grid,reference) for key,value in analysis['sequence_audit'].items()}}
 (directory/'resolution_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(directory.name,'resolution check complete',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--step',type=float,default=.05)
 a=p.parse_args();check(a.directory,a.step)
