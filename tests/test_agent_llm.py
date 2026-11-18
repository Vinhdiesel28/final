import io,json,os,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from unittest.mock import patch
from urllib.error import HTTPError
from services.agent_llm import AgentLLM,ProviderFailure
from contracts.conversation_contracts import Critique

VALID={'action':'accept','answers_question':True,'all_claims_supported':True,'reasons':[],'revised_query':'','followup_questions':[]}

def response(value):
 return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(value)}}]}).encode())

class TransportTests(unittest.TestCase):
 def test_long_cooldown_prevents_repeated_calls_from_spending_more_quota(self):
  err=HTTPError('https://example.invalid',429,'Limit',{'retry-after':'300'},io.BytesIO(b'{}'))
  with patch.dict(os.environ,{'LLM_BASE_URL':'https://example.invalid','LLM_MODEL':'fixture','LLM_API_KEY':'fixture'}),patch('services.agent_llm.urlopen',side_effect=err) as api:
   llm=AgentLLM()
   with self.assertRaises(ProviderFailure):llm.complete('draft','test',{},Critique)
   with self.assertRaises(ProviderFailure) as second:llm.complete('coordinator','test',{'new_question':True},Critique)
   self.assertEqual(api.call_count,1);self.assertGreater(second.exception.retry_after,290)
 def test_short_provider_retry_after_waits_then_retries_same_request(self):
  err=HTTPError('https://example.invalid',429,'Limit',{'retry-after':'2'},io.BytesIO(b'{}'))
  with patch.dict(os.environ,{'LLM_BASE_URL':'https://example.invalid','LLM_MODEL':'fixture','LLM_API_KEY':'fixture','LLM_RATE_LIMIT_MAX_WAIT':'20'}),patch('services.agent_llm.urlopen',side_effect=[err,response(VALID)]) as api,patch('services.agent_llm.time.sleep') as sleep:
   result,meta=AgentLLM().complete('review','test',{},Critique)
   self.assertEqual(result.action,'accept');self.assertEqual(api.call_count,2)
   sleep.assert_called_once_with(2.5);self.assertEqual(meta['rate_retries'],1)
   self.assertEqual(api.call_args_list[0].args[0].data,api.call_args_list[1].args[0].data)
 def test_long_retry_after_is_reported_without_blocking(self):
  err=HTTPError('https://example.invalid',429,'Limit',{'retry-after':'300'},io.BytesIO(b'{}'))
  with patch.dict(os.environ,{'LLM_BASE_URL':'https://example.invalid','LLM_MODEL':'fixture','LLM_API_KEY':'fixture'}),patch('services.agent_llm.urlopen',side_effect=err),patch('services.agent_llm.time.sleep') as sleep:
   with self.assertRaises(ProviderFailure) as failure:AgentLLM().complete('review','test',{},Critique)
   self.assertEqual(failure.exception.retry_after,300);self.assertEqual(failure.exception.task,'review');sleep.assert_not_called()
 def test_provider_schema_failure_retries_once_and_locally_validates_json(self):
  err=HTTPError('https://example.invalid',400,'Bad Request',{},io.BytesIO(b'{"error":{"code":"json_validate_failed"}}'))
  with patch.dict(os.environ,{'LLM_BASE_URL':'https://example.invalid','LLM_MODEL':'fixture','LLM_API_KEY':'fixture'}),patch('services.agent_llm.urlopen',side_effect=[err,response(VALID)]) as api:
   result,_=AgentLLM().complete('test','test',{},Critique)
   self.assertEqual(result.action,'accept');self.assertEqual(api.call_count,2)
   self.assertEqual(json.loads(api.call_args_list[1].args[0].data)['response_format'],{'type':'json_object'})
 def test_json_fallback_does_not_accept_invalid_contract(self):
  err=HTTPError('https://example.invalid',400,'Bad Request',{},io.BytesIO(b'{"error":{"code":"json_validate_failed"}}'))
  with patch.dict(os.environ,{'LLM_BASE_URL':'https://example.invalid','LLM_MODEL':'fixture','LLM_API_KEY':'fixture'}),patch('services.agent_llm.urlopen',side_effect=[err,response({'unsupported':'value'})]):
   with self.assertRaises(ProviderFailure) as failure:AgentLLM().complete('test','test',{},Critique)
   self.assertEqual(failure.exception.kind,'invalid_output')
 def test_quota_failure_is_not_retried(self):
  err=HTTPError('https://example.invalid',429,'Limit',{},io.BytesIO(b'{}'))
  with patch.dict(os.environ,{'LLM_BASE_URL':'https://example.invalid','LLM_MODEL':'fixture','LLM_API_KEY':'fixture'}),patch('services.agent_llm.urlopen',side_effect=err) as api:
   with self.assertRaises(ProviderFailure) as failure:AgentLLM().complete('test','test',{},Critique)
   self.assertEqual(failure.exception.kind,'rate_limited');self.assertEqual(api.call_count,1)
