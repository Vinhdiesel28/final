import os
import unittest
from unittest.mock import patch
from test_collaboration import Fixture,PROFILE
from agent_system import LegacyMultiAgent as MultiAgent,SingleAgent,intent_of
from services.llm_explanation import number_values,validate_generation
from legacy.specialist_agents import source_conflicts

QUESTION='Tôi đi xét nghiệm gì bây giờ?'
CONTEXT={'purpose':'first_screening','symptoms':'không có','prior_results':'chưa xét nghiệm'}

class TestingGuidanceTests(unittest.TestCase):
 def setUp(self):
  environment=patch.dict(os.environ,{'LLM_PROVIDER':'disabled'});environment.start();self.addCleanup(environment.stop)
 def test_question_is_clarified_with_or_without_complete_model_profile(self):
  for profile in (None,PROFILE):
   f=Fixture();r=MultiAgent(f.services).run(QUESTION,profile)
   self.assertEqual(r['intent'],'testing_guidance');self.assertEqual(r['status'],'needs_clarification')
   self.assertEqual(f.predict_calls,0);self.assertEqual(f.calls,0)
   self.assertEqual(r['clarification']['requested_fields'],['purpose','symptoms','prior_results'])
   self.assertNotIn('hbA1c_level',r['clarification']['requested_fields'])
   self.assertTrue(r['verification']['passed']);self.assertEqual(r['workflow']['action'],'ask_for_information')
 def test_partial_context_only_requests_missing_task_fields(self):
  r=MultiAgent(Fixture().services).run(QUESTION,None,{'purpose':'first_screening'})
  self.assertEqual(r['clarification']['requested_fields'],['symptoms','prior_results'])
 def test_completed_context_retrieves_without_prediction(self):
  f=Fixture();r=MultiAgent(f.services).run(QUESTION,PROFILE,CONTEXT)
  self.assertGreater(f.calls,0);self.assertEqual(f.predict_calls,0);self.assertIsNone(r['clarification'])
  self.assertEqual(r['testing_context'],CONTEXT);self.assertTrue(r['verification']['passed'])
 def test_general_lab_definition_is_not_personal_test_selection(self):
  self.assertEqual(intent_of('Xét nghiệm HbA1c là gì?',None),'medical_knowledge')
  self.assertEqual(intent_of('Tôi có cần nhịn ăn trước khi xét nghiệm HbA1c không?',None),'medical_knowledge')
  self.assertEqual(intent_of('Which test should I take?',None),'testing_guidance')
 def test_single_uses_same_clarification_safety_policy(self):
  f=Fixture();r=SingleAgent(f.services).run(QUESTION,PROFILE)
  self.assertEqual(r['status'],'needs_clarification');self.assertEqual(f.predict_calls,0)
 def test_lab_name_digit_is_not_measurement_but_numeric_value_is_checked(self):
  self.assertEqual(number_values('HbA1c và A1C'),set())
  self.assertEqual(number_values('HbA1c 7,2% glucose 140 mg/dL'),{'7.2','140'})
 def test_conditional_source_cannot_become_unconditional_personal_advice(self):
  quote='Khi kết quả xét nghiệm bất thường, có thể cần xét nghiệm xác nhận.'
  result=validate_generation({'claims':[{'text':'Bạn nên xét nghiệm xác nhận.','quote':quote,'evidence_id':'e1'}]},
                             {'evidence':[{'evidence_id':'e1','text':quote}]})
  self.assertIn('source_condition_dropped',result['issues'])
 def test_rejected_generation_changes_state_and_removes_old_medical_excerpt(self):
  f=Fixture();bad={'status':'rejected','validation':{'passed':False,'issues':['source_condition_dropped']},'claims':[]}
  with patch('services.llm_explanation.generate',return_value=bad):r=f.run()
  self.assertEqual(r['status'],'insufficient_evidence');self.assertNotIn('Mã phân loại dữ liệu là 1',r['answer'])
  self.assertIn('Chưa đủ bằng chứng',r['answer']);self.assertTrue(r['verification']['passed'])
  self.assertTrue(any(x['action']=='revise_response_status' and x['state_changed'] for x in r['revisions']))
  self.assertTrue(any(m['performative']=='CHALLENGE' and m['receiver']=='ExplanationAgent' for m in r['messages']))
 def test_provider_failure_is_partial_without_changing_model_score(self):
  f=Fixture();bad={'status':'unavailable','http_status':429}
  with patch('services.llm_explanation.generate',return_value=bad):r=f.run(PROFILE)
  self.assertEqual(r['status'],'partial');self.assertEqual(r['prediction'],f.pred)
  self.assertIn('chưa khả dụng',r['answer']);self.assertTrue(r['verification']['passed'])
 def test_page_table_and_list_numbers_are_not_medical_conflicts(self):
  f=Fixture(texts=['11 Table 2. 1. 3.','12 Table 3. 2. 4.'])
  self.assertEqual(source_conflicts(f.answer('A1C'),f.by_id),[])

if __name__=='__main__':unittest.main()
