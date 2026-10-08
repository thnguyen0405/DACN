#!/usr/bin/env python3
"""Run the unchanged ROS C++ executable serially on a dedicated ROS master.

Use the launch file's default parameters, explicit private namespaces, a real
/goal message, nav_msgs/Path and tree markers. No replacement Python planner.
"""
from pathlib import Path
import argparse,gzip,json,math,os,signal,subprocess,time,sys,xml.etree.ElementTree as ET
import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path as PathMessage
from visualization_msgs.msg import Marker
sys.path.insert(0,str(Path(__file__).parent))
from benchmark import parse_result,summarize

PLANNERS=['rrt','rrt_star','rrt_sharp','brrt','brrt_star','informed_rrt_star']
MODES=['none','region_prior','sequence_guided']

def parameters(launch,overrides):
 tree=ET.parse(launch).getroot();args={n.attrib['name']:n.attrib.get('default','') for n in tree.findall('arg')};args.update(overrides)
 flat={}
 for p in tree.find('node').findall('param'):
  val=p.attrib['value']
  if val.startswith('$(arg '):val=args[val[6:-1]]
  typ=p.attrib.get('type')
  if typ=='bool' or val in ['true','false']:val=val=='true'
  elif typ=='int':val=int(val)
  elif typ=='double':val=float(val)
  elif typ!='str':
   try:val=int(val)
   except ValueError:
    try:val=float(val)
    except ValueError:pass
  flat[p.attrib['name']]=val
 nested={}
 for key,val in flat.items():
  d=nested;keys=key.split('/')
  for k in keys[:-1]:d=d.setdefault(k,{})
  d[keys[-1]]=val
 return nested

def stop(proc):
 if proc.poll() is None:
  os.killpg(proc.pid,signal.SIGINT)
  try:proc.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--maps',nargs='+',default=['hole','flappy','narrow','room']);p.add_argument('--planners',nargs='+',default=PLANNERS)
 p.add_argument('--modes',nargs='+',default=MODES);p.add_argument('--repeats',type=int,default=10);p.add_argument('--search-time',type=float,default=1)
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 if (a.output/'runs.jsonl').exists():raise FileExistsError('Use a new output directory; existing runs must not be mixed')
 rospy.init_node('gcr_benchmark_collector',anonymous=True,disable_signals=True)
 pub=rospy.Publisher('/goal',PoseStamped,queue_size=1)
 ws=a.root/'sampling-based-path-finding-main';binary=ws/'devel/lib/path_finder/path_finder';launch=ws/'src/path_finder/launch/test_planners.launch'
 rows=[];start=time.monotonic();jobs=[]
 # Interleave conditions within seed instead of running all none before all LLM.
 for seed in range(42,42+a.repeats):
  for name in a.maps:
   for planner in a.planners:
    for mode in a.modes:jobs.append((seed,name,planner,mode))
 meta={'implementation':'ROS Noetic C++ production executable','search_time_seconds':a.search_time,'seed_start':42,'repeats':a.repeats,'planners':a.planners,'modes':a.modes,'maps':a.maps,'llm_api_time_included':False,'execution':'serial, dedicated ROS master; default launch settings; goal published after initialization','total_expected':len(jobs)}
 for index,(seed,name,planner,mode) in enumerate(jobs):
  ns='/gcr_run_'+str(index);directory=a.root/'inputs'/name
  overrides={'map_file':str(directory/'map.json'),'sampling_prior_file':str(directory/'sampling_prior.json'),'sequence_strategy_file':str(directory/'sequence_strategy.json'),'corridor_file':str(directory/'sequence_strategy.json'),'planner':planner,'guidance_mode':mode,'random_seed':str(seed),'auto_goal':'false','search_time':str(a.search_time),'use_informed_sampling':'false','step_mode':'false'}
  params=parameters(launch,overrides);rospy.set_param(ns,params)
  capture={'path':None,'tree':set()}
  def receive_path(msg):
   if msg.poses:capture['path']=[[p.pose.position.x,p.pose.position.y,p.pose.position.z] for p in msg.poses]
  def receive_tree(msg):
   capture['tree'].update((p.x,p.y,p.z) for p in msg.points)
  pathsub=rospy.Subscriber(ns+'/'+planner+'_final_path',PathMessage,receive_path,queue_size=1)
  treesub=rospy.Subscriber(ns+'/tree_edges',Marker,receive_tree,queue_size=2)
  logfile=a.output/'logs'/f'{name}-{planner}-{mode}-{seed}.log';logfile.parent.mkdir(exist_ok=True)
  run_start=time.monotonic();parsed=None;sent=False;timeout=False
  with logfile.open('w') as log:
   process=subprocess.Popen(['stdbuf','-oL','-eL',str(binary),'__name:='+ns[1:]],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:
    deadline=time.monotonic()+a.search_time+20
    while time.monotonic()<deadline:
     text=logfile.read_text(errors='replace');parsed=parse_result(text)
     if parsed:
      if not parsed['success'] or capture['path'] is not None:break
     if not sent and '[Planner] Initial start' in text and pub.get_num_connections()>0:
      coordinates=json.loads((directory/'map.json').read_text())['map']['goal'];goal=PoseStamped();goal.header.frame_id='map';goal.header.stamp=rospy.Time.now();goal.pose.position.x=coordinates[0];goal.pose.position.y=coordinates[1];goal.pose.orientation.w=1;pub.publish(goal);sent=True
     if process.poll() is not None:break
     time.sleep(.025)
    else:timeout=True
   finally:stop(process)
  pathsub.unregister();treesub.unregister();rospy.delete_param(ns)
  tree_path=None
  if capture['tree']:
   tree_path='trees/'+logfile.stem+'.json.gz';target=a.output/tree_path;target.parent.mkdir(exist_ok=True)
   with gzip.open(target,'wt') as f:json.dump(sorted(capture['tree']),f)
  row={'map':name,'planner':planner,'mode':mode,'seed':seed,'timeout':timeout,'log':str(logfile.relative_to(a.output)),'wall_seconds':time.monotonic()-run_start,'path':capture['path'],'tree_file':tree_path,'captured_tree_points':len(capture['tree'])}
  if parsed:
   assert parsed['planner']==planner and parsed['mode']==mode
   row.update(parsed)
   if parsed['success'] and capture['path'] is None:row['error']='Successful RESULT but missing final path topic'
  else:row.update(success=False,error='timeout' if timeout else 'No valid RESULT')
  if timeout:row['error']='timeout'
  rows.append(row)
  # Append durable records; summary is small and updated every run.
  with (a.output/'runs.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  status={**meta,'completed':len(rows),'elapsed_seconds':time.monotonic()-start,'errors':sum('error' in r for r in rows)}
  (a.output/'status.json').write_text(json.dumps(status,indent=2))
  print(f"{len(rows)}/{len(jobs)} {name} {planner} {mode} seed={seed} success={row['success']} time={row.get('planning_time_ms')} error={row.get('error')}",flush=True)
  if 'error' in row:
   print('Stopping on infrastructure/capture error; investigate before continuing.',flush=True);return 1
 # Summaries never merge distinct maps.
 (a.output/'benchmark.json').write_text(json.dumps({**meta,'results':rows,'summary':[{**s,'map':name} for name in a.maps for s in summarize([r for r in rows if r['map']==name])]},indent=2))
 rospy.signal_shutdown('benchmark complete');return 0
if __name__=='__main__':sys.exit(main())
