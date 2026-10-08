"""Event-driven score decay and bounded refresh policy, independent of ROS."""
import math


class AdaptivePrior:
    def __init__(self,scores,decay=0.0,every=20,floor=.05,refresh='none',interval=250,cooldown=100,max_calls=2):
        if not scores or any(not math.isfinite(s) or not 0<=s<=1 for s in scores.values()) or sum(scores.values())<=0:raise ValueError('Invalid scores')
        if not 0<=decay<1 or every<1 or not 0<=floor<=1 or interval<1 or cooldown<0 or max_calls<0:raise ValueError('Invalid adaptive settings')
        if refresh not in ('none','new_region','interval'):raise ValueError('Unknown refresh policy')
        self.base=dict(scores);self.scores=dict(scores);self.counts={i:0 for i in scores}
        self.decay,self.every,self.floor=decay,every,floor
        self.refresh,self.interval,self.cooldown,self.max_calls=refresh,interval,cooldown,max_calls
        self.visited=set();self.calls=0;self.last_call=0;self.events=[];self.pending=False

    def observe(self,iteration,region=None):
        """Only accepted tree nodes increment visit counters, never proposals."""
        if region is not None:
            if region not in self.scores:raise ValueError('Unknown region')
            first=region not in self.visited;self.visited.add(region)
            self.counts[region]+=1
            if self.decay and self.counts[region]%self.every==0:
                self.scores[region]=max(min(self.floor,self.base[region]),self.scores[region]*(1-self.decay))
                self.events.append({'iteration':iteration,'type':'decay','region':region,'score':self.scores[region]})
            if first and self.refresh=='new_region':self.pending=True
        due=(self.pending if self.refresh=='new_region' else iteration-self.last_call>=self.interval if self.refresh=='interval' else False)
        if due and iteration-self.last_call>=self.cooldown and self.calls<self.max_calls:
            self.calls+=1;self.last_call=iteration;self.pending=False
            self.events.append({'iteration':iteration,'type':'refresh_due','visited':sorted(self.visited)})
            return True
        return False

    def update(self,scores):
        if set(scores)!=set(self.scores) or any(not math.isfinite(x) or not 0<=x<=1 for x in scores.values()) or sum(scores.values())<=0:raise ValueError('Invalid refresh scores')
        self.base=dict(scores)
        self.scores={rid:max(min(self.floor,s),s*(1-self.decay)**(self.counts[rid]//self.every)) for rid,s in scores.items()}
