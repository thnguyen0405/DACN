"""Opt-in real, free-router scoring with latency/token/cost provenance."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from llm_weight_provider import OpenRouterWeightProvider, graph_prompt_data, load_dotenv
from llm_region_prior import validate_region_scores
from graph_utils import prepare_planning_graph


class StudyProvider(OpenRouterWeightProvider):
    def __init__(self, graph, output_dir, env_file, model="openrouter/free", timeout=90):
        if model!='openrouter/free' and not model.endswith(':free'):raise ValueError('Study accepts only explicitly selected free models')
        load_dotenv(Path(env_file))
        os.environ.setdefault('SSL_CERT_FILE','/etc/ssl/cert.pem')
        self.graph=prepare_planning_graph(graph);self.directory=Path(output_dir);self.directory.mkdir(parents=True,exist_ok=True)
        self.call_index=0;self.raw=[]
        super().__init__(Path(__file__).parents[1]/'prompts/region_prior_prompt.txt',model=model,
                         base_url='https://openrouter.ai/api/v1',timeout=timeout,max_tokens=12288,
                         debug_response_path=self.directory/'openrouter_invalid_response.txt')

    def _request_http_json(self,request):
        import urllib.request
        body=json.loads(request.data)
        body['reasoning']={'effort':'low','exclude':True}
        request=urllib.request.Request(request.full_url,data=json.dumps(body).encode(),headers=dict(request.header_items()),method='POST')
        payload=super()._request_http_json(request)
        self.raw.append(payload)
        return payload

    def score(self,runtime=None):
        planning=self.graph['planning']
        data=graph_prompt_data(self.graph,planning['start_region'],planning['goal_region'])
        # Already present as scalar fields; don't pay twice for duplicates.
        for region in data['regions']:region.pop('descriptors',None)
        for edge in data['directed_edges']:
            for key in ['portal','safe_portal','relation','traversability']:edge.pop(key,None)
        def compact(value):
            if isinstance(value,float):return round(value,5)
            if isinstance(value,list):return [compact(v) for v in value]
            if isinstance(value,dict):return {k:compact(v) for k,v in value.items()}
            return value
        data=compact(data)
        if runtime is not None:data['runtime']=runtime
        prompt=self.prompt_path.read_text()+'\nFor this experiment return region_scores only, covering every region. Keep reasons concise with numeric evidence.\n'
        if runtime is not None:prompt+='Update priorities using accepted tree visits and progress. A frequently visited region can still be essential; do not eliminate required connections.\n'
        prompt+='INPUT GRAPH DATA:\n'+json.dumps(data,ensure_ascii=False,separators=(',',':'))
        begin=time.perf_counter();self.raw=[];index=self.call_index;self.call_index+=1
        try:
            result,model=self._get_model_json(prompt)
            scores,missing=validate_region_scores(result,self.graph)
            metadata={'source':'live_openrouter','requested_model':self.model,'resolved_model':model,
                'latency_seconds':time.perf_counter()-begin,'http_attempts_with_json':len(self.raw),
                'usage_per_attempt':[r.get('usage') for r in self.raw],
                'missing_region_ids':missing,'runtime_refresh':runtime is not None}
            costs=[(r.get('usage') or {}).get('cost') for r in self.raw]
            metadata['reported_cost_usd']=sum(costs) if costs and all(isinstance(x,(float,int)) for x in costs) else None
            safe={'metadata':metadata,'scores':scores,'response':result,'runtime':runtime}
            (self.directory/f'call-{index:02d}.json').write_text(self._redact_text(json.dumps(safe,ensure_ascii=False,indent=2)))
            return scores,metadata
        except Exception as exc:
            safe_error=self._redact_text(str(exc))
            (self.directory/f'call-{index:02d}-error.json').write_text(json.dumps({'error':safe_error,'elapsed_seconds':time.perf_counter()-begin,'usage_per_attempt':[r.get('usage') for r in self.raw]},ensure_ascii=False,indent=2))
            raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('map_directory',type=Path);p.add_argument('--env-file',type=Path,required=True)
    p.add_argument('--model',default='openrouter/free')
    a=p.parse_args();graph=json.loads((a.map_directory/'graph.json').read_text())
    provider=StudyProvider(graph,a.map_directory/('llm' if a.model=='openrouter/free' else 'llm_fixed'),a.env_file,a.model)
    scores,meta=provider.score()
    (a.map_directory/'llm_prior.json').write_text(json.dumps({'scores':scores,'metadata':meta},ensure_ascii=False,indent=2))
    print(a.map_directory.name,json.dumps(meta),flush=True)
