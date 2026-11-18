"""Behavioral contracts for envelopes, feature hand-off, referral and audit."""
import copy
import unittest
from types import SimpleNamespace
from contracts.message_bus import MessageBus
from agents.rule_agent import rules
from agent_system import MultiAgent
from test_conversation_agents import services, ScriptedLLM
from test_collaboration import PROFILE

class AgentContractTests(unittest.TestCase):
 def test_message_envelope_failure_and_immutable_snapshots(self):
  bus=MessageBus()
  bus.register('Worker',lambda p:{'model_version':'checkpoint_v1','evidence':[{'id':'source1'}]},version='3.0.0')
  request={'nested':{'value':1}}
  output=bus.request('CoordinatorAgent','Worker',request)
  request['nested']['value']=9;output['evidence'][0]['id']='changed'
  first,last=bus.messages
  self.assertEqual(first['payload']['nested']['value'],1)
  self.assertEqual(first['status'],'pending')
  self.assertEqual(last['evidence'],[{'id':'source1'}])
  self.assertEqual(last['agent'],'Worker')
  self.assertEqual(last['model_version'],'checkpoint_v1')
  self.assertEqual(last['version'],'3.0.0')
  self.assertEqual(last['schema_version'],'2.0')
  def fail(p):raise ValueError('not exposed')
  bus.register('Broken',fail)
  with self.assertRaises(ValueError):bus.request('CoordinatorAgent','Broken',{})
  self.assertEqual(bus.messages[-1]['status'],'error')
  self.assertEqual({m['request_id'] for m in bus.messages},{bus.request_id})
 def test_validated_features_reach_dl_and_rules_and_audit_is_returned(self):
  f=services(ScriptedLLM());profile={**PROFILE,'irrelevant':'omit me'}
  result=MultiAgent(f.services).run('Đánh giá hồ sơ',profile,task='assessment')
  messages=result['messages']
  validated=next(m['payload']['validated_features'] for m in messages
                 if m['sender']=='DataAgent' and 'validated_features' in m['payload'])
  self.assertEqual(validated,PROFILE)
  for name in ('DLAgent','RuleAgent'):
   payload=next(m['payload'] for m in messages if m['receiver']==name and m['performative']=='REQUEST')
   self.assertEqual(payload['features'],validated)
  self.assertTrue(all(row['passed'] for row in result['rules']['rule_results']))
  audit=result['audit_record']
  self.assertEqual(audit['request_id'],result['request_id'])
  self.assertEqual(audit['status'],result['status'])
  self.assertEqual(audit['steps'],len(result['traces'])-1)
  self.assertGreaterEqual(audit['duration_ms'],0)
  self.assertEqual(audit['verification_passed'],result['verification']['passed'])
  self.assertTrue(audit['executions'])
  self.assertNotIn('profile',audit);self.assertNotIn('question',audit)
  for m in messages:
   self.assertTrue({'request_id','agent','status','payload','evidence','version','schema_version','model_version'}<=m.keys())
   self.assertEqual(m['content'],m['payload'])
 def test_inconsistent_features_trigger_review_without_mutating_prediction(self):
  f=services(ScriptedLLM());before=copy.deepcopy(f.pred)
  policy=SimpleNamespace(assess=lambda prediction:{'human_review_required':False,'reason':'no_review_trigger'})
  good=rules({'features':PROFILE,'prediction':f.pred},review_policy=policy)
  bad=rules({'features':{**PROFILE,'bmi':30},'prediction':f.pred},review_policy=policy)
  self.assertFalse(good['review_required']);self.assertTrue(bad['review_required'])
  self.assertIn('prediction_feature_consistency',bad['reason_codes'])
  self.assertEqual(f.pred,before)
 def test_validation_failure_has_audit_and_failed_agent_message(self):
  f=services(ScriptedLLM())
  result=MultiAgent(f.services).run('Đánh giá hồ sơ',{'age':48},task='assessment')
  self.assertEqual(result['audit_record']['status'],'validation_failed')
  self.assertGreater(result['audit_record']['validation_error_count'],0)
  self.assertTrue(any(m['agent']=='DataAgent' and m['status']=='validation_failed'
                      for m in result['messages']))
  self.assertEqual(f.predict_calls,0)
