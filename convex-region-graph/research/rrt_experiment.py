"""Portable 2D RRT research harness, NOT the production ROS RRT implementation.

Same fixed iteration budget, steering, goal connection and collision oracle for
all modes. Paired seeds control RNG initialization, not identical random draws.
"""
import math
import random
import time
import numpy as np
from shapely.geometry import Point, Polygon
from research.geometry import path_length
from research.adaptive import AdaptivePrior


def sample_polygon(rng,polygon):
    # Convex fan, area-weighted triangles = uniform area sampling.
    a=polygon[0];triangles=[(a,b,c) for b,c in zip(polygon[1:],polygon[2:])]
    weights=[abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])) for a,b,c in triangles]
    a,b,c=rng.choices(triangles,weights=weights,k=1)[0]
    u=math.sqrt(rng.random());v=rng.random()
    return ((1-u)*a[0]+u*(1-v)*b[0]+u*v*c[0],(1-u)*a[1]+u*(1-v)*b[1]+u*v*c[1])


def run_rrt(world,graph,scores=None,seed=42,iterations=2500,step=.7,connect=1.4,decay=0.0,
            refresh='none',refresh_callback=None,interval=250,max_calls=2):
    if iterations<1 or step<=0 or connect<=0:raise ValueError('Invalid RRT budget')
    rng=random.Random(seed);start=world.data['start'];goal=world.data['goal']
    if not world.valid(start) or not world.valid(goal):raise ValueError('Invalid endpoints')
    vertices={v['id']:v for v in graph['vertices']};ids=list(vertices)
    polygons={i:Polygon(v['polygon']) for i,v in vertices.items()}
    def locate(p):
        q=Point(p)
        return next((i for i,poly in polygons.items() if poly.covers(q)),None)
    policy=AdaptivePrior(scores,decay=decay,refresh=refresh,interval=interval,max_calls=max_calls) if scores is not None else None
    if policy: policy.visited.add(locate(start))
    nodes=np.empty((iterations+1,2));nodes[0]=start;count=1;parents=[-1];costs=[0.0]
    best=math.inf;best_index=None;first=None;rejected=0;accepted_regions={locate(start)};api_seconds=0;refresh_results=[]
    accepted_history=[];begin=time.perf_counter()
    for iteration in range(1,iterations+1):
        # region_prior matches the repository's score-proportional region draw;
        # no hidden exploration mixture. Uniform mode samples the same bounds.
        if policy:
            region=rng.choices(ids,weights=[policy.scores[i] for i in ids],k=1)[0]
            sample=sample_polygon(rng,vertices[region]['polygon'])
        else:
            x0,y0,x1,y1=world.bounds;sample=(rng.uniform(x0,x1),rng.uniform(y0,y1))
        added=None
        if world.valid(sample):
            near=int(np.argmin(np.sum((nodes[:count]-sample)**2,axis=1)))
            delta=np.array(sample)-nodes[near];length=float(np.linalg.norm(delta))
            if length>1e-12:
                new=nodes[near]+delta*min(1,step/length)
                if world.segment_valid(nodes[near],new):
                    nodes[count]=new;parents.append(near);costs.append(costs[near]+math.dist(nodes[near],new));index=count;count+=1
                    added=locate(new);accepted_regions.add(added)
                    accepted_history.append({'iteration':iteration,'region':added})
                    dg=math.dist(new,goal)
                    if dg<=connect and costs[index]+dg<best and world.segment_valid(new,goal):
                        best=costs[index]+dg;best_index=index
                        if first is None:first=iteration
                else:rejected+=1
            else:rejected+=1
        else:rejected+=1
        if policy and policy.observe(iteration,added) and refresh_callback:
            t=time.perf_counter()
            try:
                updated,metadata=refresh_callback({'iteration':iteration,'visited_regions':sorted(policy.visited),'accepted_counts':dict(policy.counts),'current_scores':dict(policy.scores),'best_path_length':best if math.isfinite(best) else None})
                policy.update(updated);refresh_results.append({'success':True,**metadata})
            except Exception as exc:
                refresh_results.append({'success':False,'error':str(exc)})
            api_seconds+=time.perf_counter()-t
    path=[]
    if best_index is not None:
        index=best_index
        while index>=0:path.append(nodes[index].tolist());index=parents[index]
        path=list(reversed(path))+[list(goal)]
        assert world.path_valid(path)
    elapsed=time.perf_counter()-begin
    return {'planner':'portable_rrt_research','seed':seed,'success':bool(path),'iterations':iterations,
            'nodes_added':count-1,'rejected_proposals':rejected,'first_solution_iteration':first,
            'path_length':path_length(path) if path else None,'path':path,
            'explored_regions':sorted(i for i in accepted_regions if i is not None),
            'accepted_history':accepted_history,'planning_seconds_excluding_api':elapsed-api_seconds,
            'wall_seconds':elapsed,'api_seconds':api_seconds,'refresh_results':refresh_results,
            'adaptive_events':policy.events if policy else []}
