"""Behavioral tests: assert state/output/tool effects, not trace labels alone."""
import copy,sys,unittest,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from agent_system import LegacyMultiAgent as MultiAgent
from legacy.specialist_agents import Specialists,evidence_query
from legacy.workflow_policy import WorkflowPolicy
from services.model_service import DiabetesModelService

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
 def setUp(self):
  environment=patch.dict(os.environ,{'LLM_PROVIDER':'disabled'})
  environment.start();self.addCleanup(environment.stop)
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
  self.assertTrue(r['verification']['passed'])
 def test_specific_evidence_question_is_not_overwritten_by_model_factors(self):
  f=Fixture()
  specific=evidence_query('A1C phản ánh điều gì?',f.pred)
  self.assertTrue(specific.startswith('A1C phản ánh điều gì?'))
  self.assertIn('tổng hợp thông tin đường huyết',specific)
  self.assertNotIn('BMI',specific)
  generic=evidence_query('Đánh giá nguy cơ của tôi',f.pred)
  self.assertIn('A1C HbA1c',generic);self.assertIn('BMI',generic)
 def test_llm_explanation_passes_real_agent_verifier_without_changing_score(self):
  f=Fixture();original=f.services.knowledge.answer
  def with_evidence(question):
   knowledge=original(question)
   knowledge['evidence']=[{'evidence_id':d['id'],'text':d['text']} for d in f.docs]
   return knowledge
  f.services.knowledge.answer=with_evidence
  quote=f.docs[0]['text']
  # Use a sufficiently long real source span for source validation.
  f.docs[0]['text']='Mã phân loại dữ liệu là 1. Đây là thông tin minh họa trong bộ kiểm thử.'
  generated={'status':'generated','claims':[{'text':'Dữ liệu minh họa được phân loại mã 1.','evidence_id':f.docs[0]['id'],'quote':f.docs[0]['text']}]}
  with patch('services.llm_explanation.generate',return_value=generated):r=f.run(PROFILE)
  self.assertTrue(r['verification']['passed']);self.assertEqual(r['prediction'],f.pred)
  self.assertEqual(r['explanation']['method'],'llm_evidence_v1')

if __name__=='__main__':unittest.main()
