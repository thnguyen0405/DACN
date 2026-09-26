#!/usr/bin/env python3
"""Run independent seeded ROS planner processes and save measurements.
Source ROS and devel/setup.bash first. Uses an isolated ROS master port.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

RESULT=re.compile(r'\[RESULT\] planner=(\w+) guidance=(\w+) success=([01]) wall_seconds=([\d.e+-]+) path_length=([\d.e+-]+)')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map',type=Path,required=True)
    p.add_argument('--prior',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('benchmark.json'))
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--search-time',type=float,default=1.0)
    p.add_argument('--port',type=int,default=11329)
    p.add_argument('--planners',nargs='+',default=['rrt','rrt_star','rrt_sharp','brrt','brrt_star'])
    args=p.parse_args()
    if args.repeats<1 or args.search_time<=0: p.error('Positive repeats and search-time required')
    env=dict(os.environ,ROS_MASTER_URI=f'http://localhost:{args.port}',ROS_HOSTNAME='localhost')
    rows=[]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    logs=args.output.parent/(args.output.stem+'_logs');logs.mkdir(exist_ok=True)
    for planner in args.planners:
        for mode in ('none','region_prior'):
            for seed in range(42,42+args.repeats):
                command=['roslaunch','--port',str(args.port),'path_finder','test_planners.launch',
                    f'map_file:={args.map.resolve()}',f'sampling_prior_file:={args.prior.resolve()}',
                    f'planner:={planner}',f'guidance_mode:={mode}',f'random_seed:={seed}',
                    f'search_time:={args.search_time}','step_mode:=false','planar:=true','use_informed_sampling:=false','launch_prefix:=stdbuf -oL -eL']
                log_path=logs/f'{planner}-{mode}-{seed}.log'
                with log_path.open('w') as log:
                    process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    match=None
                    try:
                        deadline=time.monotonic()+args.search_time+30
                        while time.monotonic()<deadline:
                            text=log_path.read_text(errors='replace')
                            match=RESULT.search(text)
                            if match or process.poll() is not None: break
                            time.sleep(.1)
                    finally:
                        if process.poll() is None:
                            os.killpg(process.pid,signal.SIGINT)
                            try: process.wait(timeout=8)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid,signal.SIGKILL);process.wait()
                match = match or RESULT.search(log_path.read_text(errors='replace'))
                row={'planner':planner,'mode':mode,'seed':seed,'log':str(log_path)}
                if match:
                    row.update(success=match[3]=='1',wall_seconds=float(match[4]),
                               path_length=float(match[5]) if match[3]=='1' else None)
                else: row.update(success=False,error='No result: inspect log')
                rows.append(row)
                print(json.dumps(row),flush=True)
                args.output.write_text(json.dumps({'map':str(args.map),'prior':str(args.prior),
                    'planar':True,'informed':False,'search_time':args.search_time,'results':rows},indent=2)+'\n')
    return 1 if any('error' in row for row in rows) else 0

if __name__=='__main__': raise SystemExit(main())
