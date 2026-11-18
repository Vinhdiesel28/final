"""Small structured Groq/compatible transport shared by the general agent flow."""
import hashlib
import json
import os
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from pydantic import BaseModel,ConfigDict

class Object(BaseModel):
    model_config=ConfigDict(extra='forbid')

class ProviderFailure(RuntimeError):
    def __init__(self,kind,http_status=None,task=None,retry_after=None):
        self.kind=kind;self.http_status=http_status;self.task=task;self.retry_after=retry_after
        super().__init__(kind)

class AgentLLM:
    """In-memory exact-input cache; never writes keys or conversation text to disk."""
    def __init__(self,cache_ttl=600):
        self.cache_ttl=cache_ttl
        self.cache={};self.lock=threading.RLock();self.request_lock=threading.RLock();self.cooldown_until=0.
    def complete(self,task,system,payload,output_type,max_tokens=1100):
        # Share a queue across this service's agents; concurrent browser requests
        # must not send bursts that exhaust the same provider token allowance.
        with self.request_lock:
            return self._complete(task,system,payload,output_type,max_tokens)
    def _complete(self,task,system,payload,output_type,max_tokens):
        key=hashlib.sha256(json.dumps([task,system,payload,os.environ.get('LLM_MODEL')],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            cached=self.cache.get(key)
            if cached and time.monotonic()-cached[0]<self.cache_ttl:
                return output_type.model_validate(cached[1]),{'cached':True,'task':task}
        if self.cooldown_until>time.monotonic():
            raise ProviderFailure('rate_limited',429,task,self.cooldown_until-time.monotonic())
        if not all(os.environ.get(k,'').strip() for k in ('LLM_BASE_URL','LLM_MODEL','LLM_API_KEY')):
            raise ProviderFailure('configuration_required')
        url=os.environ['LLM_BASE_URL'].rstrip('/')+'/chat/completions'
        body={'model':os.environ['LLM_MODEL'],'temperature':0,'max_completion_tokens':max_tokens,
              'messages':[{'role':'system','content':system+'\nReturn exactly ONE JSON object conforming to this schema, never an array or Markdown. Keep all arrays short.\n'+json.dumps(output_type.model_json_schema(),ensure_ascii=False)}, {'role':'user','content':json.dumps(payload,ensure_ascii=False)}],
              'response_format':{'type':'json_schema','json_schema':{'name':task,'strict':True,'schema':output_type.model_json_schema()}}}
        if 'api.groq.com/' in url and body['model'].startswith('openai/gpt-oss-'):body['reasoning_effort']='low'
        format_retried=False;rate_retries=0;waited=0.
        max_wait=max(0,min(30,float(os.environ.get('LLM_RATE_LIMIT_MAX_WAIT','20'))))
        while True:
            request=Request(url,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+os.environ['LLM_API_KEY'],'Content-Type':'application/json','User-Agent':'DiaAgents/3.0','Accept':'application/json'})
            try:
                with urlopen(request,timeout=float(os.environ.get('LLM_TIMEOUT','90'))) as response:data=json.load(response)
                result=output_type.model_validate_json(data['choices'][0]['message']['content'])
                break
            except HTTPError as exc:
                try:code=json.load(exc).get('error',{}).get('code')
                except Exception:code=None
                if not format_retried and exc.code==400 and code=='json_validate_failed':
                    # Some compatible providers reject otherwise usable schema
                    # generations. Retry in JSON mode, still validate locally
                    # against the very same Pydantic contract before any use.
                    body['response_format']={'type':'json_object'}
                    body['messages'].append({'role':'user','content':'The provider rejected the prior output as invalid JSON/schema. Return a SINGLE OBJECT with all required fields, short arrays, and no prose outside JSON. Do not output the schema itself.'})
                    format_retried=True
                    continue
                try:retry_after=float(exc.headers.get('retry-after',''))
                except (ValueError,TypeError):retry_after=None
                if exc.code==429 and retry_after is not None and retry_after>=0 and rate_retries<2 and waited+retry_after+.5<=max_wait:
                    delay=retry_after+.5;time.sleep(delay);waited+=delay;rate_retries+=1
                    continue
                if exc.code==429 and retry_after is not None and retry_after>0:
                    self.cooldown_until=time.monotonic()+retry_after
                raise ProviderFailure('rate_limited' if exc.code==429 else 'provider_error',exc.code,task,retry_after) from None
            except Exception as exc:raise ProviderFailure('invalid_output' if isinstance(exc,(ValueError,KeyError,IndexError)) else 'provider_unavailable') from None
        with self.lock:
            if len(self.cache)>64:self.cache.clear()
            if self.cache_ttl>0:self.cache[key]=(time.monotonic(),result.model_dump())
        return result,{'cached':False,'task':task,'model':body['model'],'usage':data.get('usage',{}),'rate_retries':rate_retries,'waited_seconds':round(waited,2)}
