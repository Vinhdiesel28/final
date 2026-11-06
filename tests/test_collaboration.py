"""Behavioral tests: assert state/output/tool effects, not trace labels alone."""
import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from agent_system import MultiAgent
from specialist_agents import Specialists
from workflow_policy import WorkflowPolicy
from model_service import DiabetesModelService

PROFILE={'gender':'Female','age':48,'bmi':28.4,'hbA1c_level':5.8,'blood_glucose_level':140,'hypertension':0,'heart_disease':0,'smoking_history':'never'}
QUESTION='Mã phân loại dữ liệu là gì?'
class Fixture:
 def __init__(self,a=.8,b=.9,texts=None,empty_first=False):
  self.calls=0;self.predict_calls=0; self.empty_first=empty_first
  docs=[{'id':f'fixture_{i}','title':'Synthetic fixture','url':f'https://example.invalid/{i}','text':t} for i,t in enumerate(texts or ['Mã phân loại dữ liệu là 1.'])]
  self.by_id={d['id']:d for d in docs};self.docs=docs
  self.pred={'probability':a,'threshold':.5,'predicted_class':int(a>=.5),'model':'fixture','feature_impacts':[
             {'feature':'hbA1c_level','value':'5.8','baseline':'5.8','impact':.1234},
             {'feature':'bmi','value':'28.4','baseline':'27.3','impact':-.0456}],
             'second_opinion':{'probability':b,'threshold':.5,'predicted_class':int(b>=.5),'model':'fixture_peer'}}
  self.services=SimpleNamespace(model=SimpleNamespace(validate=DiabetesModelService.validate,predict=self.predict),
   knowledge=SimpleNamespace(backend='fixture',by_id=self.by_id,answer=self.answer),policy=WorkflowPolicy())
 def predict(self,profile): self.predict_calls+=1;return copy.deepcopy(self.pred)
 def answer(self,question):
  self.services.knowledge.last_query=question
  self.calls+=1
  if self.empty_first and self.calls==1: return {'answer':'Không có bằng chứng.','citations':[],'paths':[],'status':'insufficient_evidence'}
  return {'answer':' '.join(d['text'] for d in self.docs),'citations':copy.deepcopy(self.docs),'paths':[],'status':'supported'}
 def run(self,profile=None): return MultiAgent(self.services).run(QUESTION,profile)

class CollaborationTests(unittest.TestCase):
 def test_disagreement_changes_final_conclusion_not_probability(self):
  f=Fixture(.2,.8);r=f.run(PROFILE)
  self.assertEqual(r['status'],'human_review');self.assertIsNone(r['decision']['final_label'])
  self.assertEqual(r['prediction'],f.pred);self.assertTrue(r['review']['passed']);self.assertTrue(r['verification']['passed'])
  changes=[x for x in r['revisions'] if x['action']=='revise_conclusion']
  self.assertEqual(changes[0]['before']['final_label'],0);self.assertIsNone(changes[0]['after']['final_label'])
  self.assertTrue(changes[0]['state_changed'])
 def test_small_score_gap_not_automatically_human_review(self):
  r=Fixture(.499,.501).run(PROFILE)
  self.assertEqual(r['status'],'supported_with_limitations');self.assertEqual(r['decision']['final_label'],0)
  self.assertIn('model_disagreement',r['decision']['reason_codes']);self.assertIn('không ép đồng thuận',r['answer'])
 def test_missing_input_blocks_prediction_even_with_bad_q_values(self):
  f=Fixture();f.services.policy.artifact['q_table']=[[0,0,1e9,0] for _ in range(8)]
  r=f.run({});self.assertEqual(r['status'],'needs_clarification');self.assertEqual(f.predict_calls,0)
  self.assertIn('age',r['clarification']['requested_fields']);self.assertIsNone(r['prediction'])
  self.assertEqual(r['workflow']['action'],'ask_for_information')
 def test_retrieval_retry_changes_evidence_and_answer(self):
  f=Fixture(empty_first=True);r=f.run()
  self.assertGreaterEqual(f.calls,2);self.assertEqual(r['status'],'supported');self.assertTrue(r['knowledge']['citations'])
  self.assertTrue(any(x.get('state_changed') for x in r['revisions']));self.assertIn('Mã phân loại',r['answer'])
 def test_source_conflict_is_not_silently_deleted(self):
  f=Fixture(texts=['Mã phân loại dữ liệu là 1.','Mã phân loại dữ liệu là 0.']);r=f.run()
  self.assertEqual(r['status'],'human_review');self.assertTrue(r['decision']['source_conflicts']);self.assertIn('mâu thuẫn',r['answer'])
 def test_explanation_is_repaired_and_reverified(self):
  original=Specialists.explain
  def corrupt_once(self,p):
   return original(self,p) if p.get('verification') else {'answer':'Injected unsupported draft ZXQ999.'}
  with patch.object(Specialists,'explain',corrupt_once): r=Fixture().run()
  self.assertNotIn('ZXQ999',r['answer']);self.assertTrue(r['verification']['passed'])
  self.assertTrue(any(x['action']=='rewrite_final_explanation' and x['state_changed'] for x in r['revisions']))
 def test_persistent_explanation_error_fails_closed(self):
  with patch.object(Specialists,'explain',lambda self,p:{'answer':'ZXQ999'}): r=Fixture().run()
  self.assertEqual(r['status'],'verification_failed');self.assertNotIn('ZXQ999',r['answer']);self.assertIsNone(r['decision']['final_label'])
 def test_q_values_change_executed_tool_path(self):
  f=Fixture();f.services.policy.artifact['q_table'][2]=[0,1000,0,0];r=f.run();extra=f.calls
  g=Fixture();g.services.policy.artifact['q_table'][2]=[0,0,1000,0];z=g.run()
  self.assertGreater(extra,g.calls);self.assertEqual(r['answer'],z['answer'])
  self.assertTrue(any(x['action']=='show_sources' and x.get('executed_handler')=='RetrievalAgent' for x in r['workflow_history']))
 def test_q_cannot_override_required_review(self):
  f=Fixture(.2,.8);f.services.policy.artifact['q_table']=[[0,0,1e9,0] for _ in range(8)];r=f.run(PROFILE)
  self.assertEqual(r['status'],'human_review');self.assertEqual(r['workflow']['allowed_actions'],['request_human_review'])
 def test_unresponsive_review_handler_fails_closed(self):
  with patch.object(Specialists,'review',lambda self,p:copy.deepcopy(p['decision'])):
   r=Fixture(.2,.8).run(PROFILE)
  self.assertEqual(r['status'],'verification_failed');self.assertIsNone(r['decision']['final_label'])
  self.assertIn('critic_unresolved',r['decision']['reason_codes'])
 def test_partial_profile_is_not_imputed(self):
  f=Fixture();r=f.run({'age':48});self.assertEqual(f.predict_calls,0);self.assertEqual(r['status'],'needs_clarification')
 def test_feature_impacts_drive_explanation_and_are_verified(self):
  f=Fixture();r=f.run(PROFILE)
  self.assertEqual(r['explanation']['method'],'deterministic_template_v2')
  self.assertEqual(r['explanation']['model_factors'][0]['impact'],f.pred['feature_impacts'][0]['impact'])
  self.assertIn('độ nhạy của model',r['answer']);self.assertIn('không chứng minh quan hệ nhân quả',r['answer'])
  self.assertTrue(r['verification']['passed']);self.assertIn('A1C HbA1c',f.services.knowledge.last_query)

if __name__=='__main__':unittest.main()
