"""Diagnose two public demo questions without logging keys or raw HTTP errors."""
import argparse,json,sys,time
from pathlib import Path
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
import services.agent_llm as agent_llm
from agent_system import Services,MultiAgent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--question',action='append');args=parser.parse_args()
    original=agent_llm.urlopen;calls=[]
    def measured(request,*args,**kwargs):
        body=json.loads(request.data);task=body.get('response_format',{}).get('json_schema',{}).get('name','json_retry')
        try:
            response=original(request,*args,**kwargs);headers=response.headers
            calls.append({'task':task,'status':response.status,'limits':{k:headers.get(k) for k in (
                'x-ratelimit-limit-requests','x-ratelimit-limit-tokens','x-ratelimit-remaining-requests',
                'x-ratelimit-remaining-tokens','x-ratelimit-reset-tokens','retry-after')}})
            return response
        except HTTPError as exc:
            calls.append({'task':task,'status':exc.code,'limits':{k:exc.headers.get(k) for k in (
                'x-ratelimit-limit-tokens','x-ratelimit-remaining-tokens','x-ratelimit-reset-tokens','retry-after')}})
            raise
    agent_llm.urlopen=measured
    services=Services();runner=MultiAgent(services);results=[]
    for question in args.question or ['HbA1c là gì?','BMI là gì?']:
        before=len(calls);started=time.perf_counter();r=runner.run(question)
        item={'question':question,'status':r['status'],'answer':r['answer'],
              'seconds':round(time.perf_counter()-started,2),'calls':calls[before:],
              'traces':r['traces'],'revisions':r['revisions'],'response_review':r.get('response_review'),
              'drafts':[m['content'] for m in r['messages'] if m['sender']=='ExplanationAgent'],
              'generation':(r.get('explanation') or {}).get('generation',{})}
        results.append(item)
        print(json.dumps({k:item[k] for k in ('question','status','answer','seconds','calls')},ensure_ascii=True),flush=True)
    (ROOT/'results/llm_quota_diagnostic.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
