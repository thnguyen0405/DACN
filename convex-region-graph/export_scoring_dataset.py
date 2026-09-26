#!/usr/bin/env python3
"""Export descriptor-rich labeling tasks, or JSONL examples with supplied labels.

No labels are invented. Unlabeled exports cannot be used as supervised targets.
Use --labels only for reviewed responses matching this graph.
"""
import argparse
import json
from pathlib import Path
from llm_region_planner import (compact_llm_input, prepare_safe_portal_graph,
    resolve_region, validate_model_response, PlanningError)


def make_record(raw_graph, prompt, labels=None, label_source=None):
    graph=prepare_safe_portal_graph(raw_graph)
    start=resolve_region(graph,'start',None)
    goal=resolve_region(graph,'goal',None)
    payload=compact_llm_input(graph,start,goal)
    if any(not v.get('descriptors') for v in payload['regions']):
        raise ValueError('Rebuild graph with intrinsic descriptors before exporting')
    messages=[{'role':'system','content':prompt},
              {'role':'user','content':json.dumps(payload,ensure_ascii=False,allow_nan=False)}]
    if labels is not None:
        if not label_source:
            raise ValueError('Label provenance is required')
        _,_,missing,_=validate_model_response(labels,graph)
        if missing:
            raise ValueError('Supervised labels must explicitly score every region: '+', '.join(missing))
        # The prompt contract uses these two fields; exclude provider metadata.
        answer={'region_scores':labels.get('region_scores',[]),'edge_costs':labels.get('edge_costs',[])}
        messages.append({'role':'assistant','content':json.dumps(answer,ensure_ascii=False,allow_nan=False)})
    return {'messages':messages}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph',type=Path)
    p.add_argument('--labels',type=Path)
    p.add_argument('--label-source',choices=['human-reviewed','model-generated','synthetic'])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prompt',type=Path,default=Path(__file__).parent/'prompts/region_prior_prompt.txt')
    args=p.parse_args()
    try:
        graph=json.loads(args.graph.read_text())
        labels=json.loads(args.labels.read_text()) if args.labels else None
        record=make_record(graph,args.prompt.read_text(),labels,args.label_source)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
        args.output.with_suffix('.metadata.json').write_text(json.dumps({
            'graph':str(args.graph),'labels':str(args.labels) if args.labels else None,
            'label_source':args.label_source if labels else None,
            'supervised':labels is not None,'examples':1,
            'note':'A single map is an example, not an adequate training/evaluation dataset.'},indent=2)+'\n')
        print(('Labeled example' if labels else 'Unlabeled annotation task')+': '+str(args.output))
        return 0
    except (OSError,ValueError,PlanningError) as exc:
        p.exit(1,f'Error: {exc}\n')

if __name__=='__main__':
    raise SystemExit(main())
