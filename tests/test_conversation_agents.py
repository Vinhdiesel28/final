"""Behavioral tests of the DEFAULT v3 flow; synthetic evidence stays in tests."""
import copy
import unittest
from types import SimpleNamespace
from agent_system import MultiAgent
from services.agent_llm import ProviderFailure
from test_collaboration import Fixture,PROFILE

QUOTE='The documented classification code is 1 for this synthetic example.'

def plan(intent='knowledge',general=True):
 return {'intent':intent,'goal':'Explain the requested information','queries':['initial query'],
         'clarification_questions':[] if general else ['Bạn muốn tìm hiểu mục đích nào?'],'can_answer_general':general,'requested_sources':[]}
def draft(text='Mã minh họa là 1.',evidence='s1'):
 return {'claims':[{'text':text,'evidence_id':evidence,'quote':QUOTE}],
         'followup_questions':[],'evidence_sufficient':True,'missing_information':''}
def critique(action='accept',supported=True):
 return {'action':action,'answers_question':action=='accept','all_claims_supported':supported,
         'reasons':[] if action=='accept' else ['Need better evidence or wording'],
         'revised_query':'revised query' if action=='retrieve_again' else '', 'followup_questions':[]}

class Knowledge:
 backend='fixture';vector_metadata={'backend':'fixture'}
 def __init__(self):self.queries=[]
 def retrieve(self,query,limit):
  self.queries.append(query)
  key='s2' if 'revised' in query else 's1'
  return [{'id':key,'text':QUOTE,'title':'Synthetic source','url':'https://example.invalid/'+key,'source_type':'web'}]
 def graph_paths(self,query):return []

class ScriptedLLM:
 def __init__(self,plans=None,drafts=None,reviews=None,failure=False):
  self.plans=plans or [plan()];self.drafts=drafts or [draft()];self.reviews=reviews or [critique()];self.calls=[];self.failure=failure
 def complete(self,task,system,payload,output_type,max_tokens=1000):
  self.calls.append((task,copy.deepcopy(payload)))
  if self.failure:raise ProviderFailure('rate_limited',429)
  sequence=self.plans if task=='coordinator_plan' else self.drafts if task=='grounded_draft' else self.reviews
  value=sequence.pop(0) if len(sequence)>1 else sequence[0]
  return output_type.model_validate(value),{'cached':False,'task':task}

def services(llm):
 fixture=Fixture();fixture.services.knowledge=Knowledge();fixture.services.agent_llm=llm
 return fixture

class ConversationFlowTests(unittest.TestCase):
 def test_english_claim_is_rewritten_with_original_quote(self):
  llm=ScriptedLLM(drafts=[draft('The documented classification code is 1.'),draft()])
  result=MultiAgent(services(llm).services).run('Giải thích mã',task='knowledge')
  self.assertEqual(result['status'],'supported')
  repaired=[payload for task,payload in llm.calls if task=='grounded_draft'][-1]
  self.assertIn('answer_language_mismatch',repaired['challenge']['reasons'])
  self.assertEqual(result['explanation']['generation']['claims'][0]['quote'],QUOTE)
 def test_knowledge_flow_does_not_fetch_fact_paths(self):
  f=services(ScriptedLLM())
  f.services.knowledge.graph_paths=lambda q:self.fail('Fact paths should not be queried')
  result=MultiAgent(f.services).run('Giải thích mã',task='knowledge')
  self.assertEqual(result['status'],'supported')
  self.assertEqual(result['knowledge']['paths'],[])
 def test_assessment_preserves_mandatory_review_when_citation_fails(self):
  invalid=draft()
  invalid['claims'][0]['quote']='An invented quotation absent from the source.'
  f=services(ScriptedLLM(drafts=[invalid]))
  f.services.review_policy=SimpleNamespace(assess=lambda prediction:{'human_review_required':True})
  result=MultiAgent(f.services).run('Đánh giá hồ sơ',PROFILE,task='assessment')
  self.assertEqual(result['status'],'insufficient_evidence')
  self.assertTrue(result['decision']['review_required'])
  self.assertIsNone(result['decision']['final_label'])
  self.assertIn('quote_or_citation_invalid',result['response_review']['reasons'])
 def test_runtime_uses_seven_agent_contract_and_preserves_operations(self):
  allowed={'CoordinatorAgent','DataAgent','DLAgent','RuleAgent',
           'KnowledgeAgent','ExplanationAgent','MonitoringAgent'}
  f=services(ScriptedLLM())
  result=MultiAgent(f.services).run('Đánh giá hồ sơ',PROFILE,task='assessment')
  self.assertEqual({step['agent'] for step in result['traces']},allowed)
  self.assertTrue(all(m['sender'] in allowed and m['receiver'] in allowed for m in result['messages']))
  steps=[step['tool'] for step in result['traces']]
  self.assertTrue({'validate','retrieve','read','critique','compose','verify'}<=set(steps))
  from benchmark_v3 import grade
  scored=grade({'kind':'assessment','task':'assessment','expected_intents':['prediction']},
               result, {'s1':{'text':QUOTE}}, f.pred)
  self.assertTrue(scored['passed'], scored)
 def test_assessment_explanation_receives_model_rules_and_evidence(self):
  llm=ScriptedLLM()
  f=services(llm)
  f.services.review_policy=SimpleNamespace(assess=lambda prediction:{'human_review_required':True})
  runner=MultiAgent(f.services)
  result=runner.run('Đánh giá hồ sơ',PROFILE,task='assessment')
  self.assertEqual(result['status'],'human_review')
  self.assertIsNone(result['decision']['final_label'])
  messages=result['messages']
  self.assertEqual({m['request_id'] for m in messages},{result['request_id']})
  self.assertTrue(all(m['version'] for m in messages))
  compose=next(m['content'] for m in messages if m['receiver']=='ExplanationAgent'
               and m['content'].get('action')=='compose')
  self.assertEqual(compose['prediction'],result['prediction'])
  self.assertEqual(compose['rules'],result['rules'])
  self.assertEqual(compose['evidence'][0]['evidence_id'],'s1')
  self.assertIn('confidence',[section['id'] for section in result['explanation']['sections']])
  self.assertTrue(all('prediction' not in payload and 'rules' not in payload for _,payload in llm.calls))
  second=runner.run('Đánh giá hồ sơ',PROFILE,task='assessment')
  self.assertNotEqual(result['request_id'],second['request_id'])
 def test_explicit_assessment_validates_before_any_llm_or_model(self):
  f=services(ScriptedLLM());profile=copy.deepcopy(PROFILE);profile.pop('hbA1c_level')
  r=MultiAgent(f.services).run('Đánh giá hồ sơ',profile,task='assessment')
  self.assertEqual(r['status'],'validation_failed');self.assertEqual(f.predict_calls,0)
  self.assertEqual(f.services.agent_llm.calls,[])
 def test_invalid_profile_preserves_errors_guidance_and_stops_downstream_agents(self):
  for update in ({'hbA1c_level':None},{'bmi':900}):
   with self.subTest(update=update):
    f=services(ScriptedLLM());profile={**PROFILE,**update}
    if update.get('hbA1c_level','present') is None:profile.pop('hbA1c_level')
    r=MultiAgent(f.services).run('Đánh giá hồ sơ',profile,task='assessment')
    self.assertEqual(r['status'],'validation_failed')
    self.assertTrue(r['validation_errors'])
    self.assertIn(next(iter(update)),[error['field'] for error in r['validation_errors']])
    self.assertIn('bổ sung hoặc xác nhận',r['answer'])
    self.assertEqual(r['clarification']['status'],'validation_failed')
    self.assertTrue(r['clarification']['questions'])
    self.assertEqual(r['decision']['status'],'validation_failed')
    self.assertIsNone(r['decision']['final_label'])
    self.assertEqual(f.predict_calls,0)
    self.assertEqual(f.services.knowledge.queries,[])
    self.assertEqual(f.services.agent_llm.calls,[])
    agents={step['agent'] for step in r['traces']}
    self.assertTrue({'DLAgent','RuleAgent','KnowledgeAgent'}.isdisjoint(agents))
    self.assertIn('MonitoringAgent',agents)
    from benchmark_v3 import grade
    scored=grade({'kind':'validation','task':'assessment','expected_intents':['prediction']},r,{})
    self.assertTrue(scored['passed'],scored)
 def test_explicit_assessment_is_not_reclassified_as_a_knowledge_only_question(self):
  f=services(ScriptedLLM())
  r=MultiAgent(f.services).run('Giải thích HbA1c',PROFILE,task='assessment')
  self.assertEqual(f.predict_calls,1);self.assertEqual(r['intent'],'prediction');self.assertEqual(r['task'],'assessment')
  self.assertFalse(any(task=='coordinator_plan' for task,_ in f.services.agent_llm.calls))
 def test_explicit_knowledge_never_runs_model_even_if_planner_requests_prediction(self):
  f=services(ScriptedLLM(plans=[plan('prediction')]))
  r=MultiAgent(f.services).run('Tôi có nguy cơ không?',PROFILE,task='knowledge')
  self.assertEqual(f.predict_calls,0);self.assertIsNone(r['prediction']);self.assertEqual(r['status'],'needs_clarification')
  self.assertEqual(f.services.agent_llm.calls[0][1]['available_profile_fields'],[])
 def test_coordinator_retries_once_when_retrieval_is_empty(self):
  f=services(ScriptedLLM())
  retrieve=f.services.knowledge.retrieve
  queries=[]
  def empty_first(query, limit):
   queries.append(query)
   return retrieve(query, limit) if len(queries)>1 else []
  f.services.knowledge.retrieve=empty_first
  del f.services.policy
  result=MultiAgent(f.services).run('Giải thích mã',task='knowledge')
  self.assertEqual(result['status'],'supported')
  self.assertEqual(len(queries),2)
  self.assertIsNone(result['workflow'])
  self.assertNotIn('WorkflowRLAgent',[step['agent'] for step in result['traces']])

 def test_coordinator_requests_clarification_without_retrieval(self):
  f=services(ScriptedLLM(plans=[plan(general=False)]))
  del f.services.policy
  result=MultiAgent(f.services).run('Cần thông tin thiết yếu',task='knowledge')
  self.assertEqual(result['status'],'needs_clarification')
  self.assertEqual(f.services.knowledge.queries,[])
  self.assertIn('DataAgent',[step['agent'] for step in result['traces']])

 def test_user_context_number_requires_semantic_review_but_is_not_fabricated(self):
  f=services(ScriptedLLM(drafts=[draft('Bạn cho biết 30 tuổi; mã trong nguồn là 1.')]))
  r=MultiAgent(f.services).run('Tôi 30 tuổi, giải thích mã')
  self.assertEqual(r['status'],'supported')
  self.assertTrue(any(task=='response_critic' for task,_ in f.services.agent_llm.calls))
 def test_truly_unsupported_number_still_blocks_answer(self):
  f=services(ScriptedLLM(drafts=[draft('Mã trong nguồn là 999.')]))
  r=MultiAgent(f.services).run('Giải thích mã')
  self.assertEqual(r['status'],'insufficient_evidence');self.assertNotIn('999',r['answer'])
 def test_reader_does_not_let_unrelated_raw_sources_crowd_out_relevant_evidence(self):
  p=plan();p['queries']=['classification code']
  f=services(ScriptedLLM(plans=[p]))
  original=f.services.knowledge.retrieve
  f.services.knowledge.retrieve=lambda q,n:[{'id':'noise'+str(i),'text':'Unrelated topic without supporting evidence.','title':'Other source','source_type':'pdf'} for i in range(4)]+original(q,n)
  r=MultiAgent(f.services).run('Explain the classification code')
  self.assertEqual(r['status'],'supported');self.assertIn('[s1]',r['answer'])
 def test_empty_queries_are_valid_for_clarification_and_non_rag_routes(self):
  p=plan(general=False);p['queries']=[]
  f=services(ScriptedLLM(plans=[p]));r=MultiAgent(f.services).run('Câu trả lời cần bối cảnh')
  self.assertEqual(r['status'],'needs_clarification');self.assertEqual(f.services.knowledge.queries,[])
 def test_missing_queries_for_answerable_question_falls_back_to_original_question(self):
  p=plan();p['queries']=[]
  f=services(ScriptedLLM(plans=[p]));r=MultiAgent(f.services).run('Câu hỏi gốc')
  self.assertEqual(r['status'],'supported');self.assertIn(p['goal'],f.services.knowledge.queries[0])
 def test_default_flow_uses_real_retrieval_and_does_not_predict_for_knowledge_with_profile(self):
  f=services(ScriptedLLM());r=MultiAgent(f.services).run('Giải thích khái niệm',PROFILE)
  self.assertEqual(r['architecture_version'],'conversation_v3');self.assertEqual(r['status'],'supported')
  self.assertEqual(f.predict_calls,0);self.assertGreater(len(f.services.knowledge.queries),0)
  agents={t['agent'] for t in r['traces']}
  self.assertTrue({'CoordinatorAgent','KnowledgeAgent','KnowledgeAgent','RuleAgent','ExplanationAgent','ExplanationAgent','ExplanationAgent','MonitoringAgent'}<=agents)
  self.assertTrue(r['verification']['passed']);self.assertEqual(r['knowledge']['evidence'][0]['evidence_id'],'s1')
 def test_critic_retrieval_challenge_changes_sources_and_final_answer(self):
  f=services(ScriptedLLM(drafts=[draft(),draft('Nguồn truy xuất lại xác nhận mã 1.','s2')],reviews=[critique('retrieve_again'),critique()]))
  r=MultiAgent(f.services).run('Câu hỏi cần bằng chứng khác')
  self.assertIn('revised query',f.services.knowledge.queries[-1]);self.assertIn('[s2]',r['answer'])
  self.assertNotIn('[s1]',r['answer']);self.assertTrue(r['revisions'][0]['state_changed'])
  self.assertEqual(r['revisions'][0]['before']['evidence_ids'],['s1']);self.assertEqual(r['revisions'][0]['after']['evidence_ids'],['s2'])
 def test_critic_revision_changes_content_not_just_trace(self):
  f=services(ScriptedLLM(drafts=[draft('Bản giải thích ban đầu mã 1.'),draft('Bản giải thích đã sửa mã 1.')],reviews=[critique('revise'),critique()]))
  r=MultiAgent(f.services).run('Giải thích rõ hơn')
  self.assertIn('đã sửa',r['answer']);self.assertNotIn('ban đầu',r['answer'])
  self.assertTrue(r['revisions'][0]['state_changed'])
  self.assertTrue(any(m['performative']=='CHALLENGE' and m['receiver']=='ExplanationAgent' for m in r['messages']))
  repair_calls=[p for task,p in f.services.agent_llm.calls if task=='grounded_draft' and p.get('previous_draft')]
  self.assertEqual(repair_calls[0]['previous_draft']['claims'][0]['text'],'Bản giải thích ban đầu mã 1.')
 def test_invalid_citation_triggers_repair(self):
  f=services(ScriptedLLM(drafts=[draft(evidence='forged'),draft()]))
  r=MultiAgent(f.services).run('Câu hỏi')
  self.assertNotIn('forged',r['answer']);self.assertTrue(r['verification']['passed']);self.assertTrue(r['revisions'])
 def test_accept_flag_without_support_cannot_release_answer(self):
  f=services(ScriptedLLM(reviews=[critique('accept',False)]))
  r=MultiAgent(f.services).run('Câu hỏi')
  self.assertEqual(r['status'],'insufficient_evidence');self.assertNotIn('[s1]',r['answer'])
  self.assertEqual(len([x for x in f.services.agent_llm.calls if x[0]=='grounded_draft']),3)
 def test_general_personal_question_can_answer_with_rag_and_optional_followup(self):
  p=plan('personal_guidance');d=draft();d['followup_questions']=['Bạn hỏi để tìm hiểu hay đang có vấn đề cụ thể?']
  f=services(ScriptedLLM(plans=[p],drafts=[d]));r=MultiAgent(f.services).run('Tôi nên làm gì bây giờ?',PROFILE)
  self.assertEqual(r['status'],'supported_with_limitations');self.assertIsNone(r['clarification'])
  self.assertGreater(len(f.services.knowledge.queries),0);self.assertEqual(f.predict_calls,0)
 def test_essential_clarification_is_dynamic_and_context_reaches_coordinator(self):
  f=services(ScriptedLLM(plans=[plan('personal_guidance',False)]))
  history=[{'role':'user','content':'Câu hỏi trước'},{'role':'assistant','content':'Bạn muốn biết gì?'}]
  r=MultiAgent(f.services).run('Tôi cần biết điều này',conversation=history)
  self.assertEqual(r['status'],'needs_clarification');self.assertIn('mục đích',r['answer'])
  self.assertEqual(f.services.agent_llm.calls[0][1]['conversation'],history)
 def test_model_runs_only_when_plan_requests_prediction(self):
  f=services(ScriptedLLM(plans=[plan('prediction')]))
  r=MultiAgent(f.services).run('Ước lượng nguy cơ theo hồ sơ',PROFILE)
  self.assertEqual(f.predict_calls,1)
  self.assertEqual({key:r['prediction'][key] for key in f.pred},f.pred)
  self.assertIn('80.0%',r['answer']);self.assertTrue(r['verification']['passed'])
 def test_provider_failure_is_partial_not_false_success(self):
  f=services(ScriptedLLM(failure=True));r=MultiAgent(f.services).run('Câu hỏi')
  self.assertEqual(r['status'],'partial');self.assertEqual(f.services.knowledge.queries,[])
  self.assertTrue(any(m['performative']=='FAILURE' for m in r['messages']))

if __name__=='__main__':unittest.main()
