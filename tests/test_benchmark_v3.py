import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from benchmark_v3 import grade,rank_scores,rate,summarize
from test_conversation_agents import services,ScriptedLLM,QUOTE
from test_collaboration import PROFILE
from agent_system import MultiAgent

class BenchmarkGradingTests(unittest.TestCase):
 def assessment(self):
  f=services(ScriptedLLM());result=MultiAgent(f.services).run('Đánh giá hồ sơ',PROFILE,task='assessment')
  case={'kind':'assessment','task':'assessment','expected_intents':['prediction']}
  return f,result,case
 def test_rule_grade_allows_evidence_abstention_without_changing_model_label(self):
  f,result,case=self.assessment();result['status']='insufficient_evidence';result['decision'].update(final_label=None,review_required=False)
  result['rules']['review_required']=False
  scored=grade(case,result,{'s1':{'text':QUOTE}},f.pred)
  self.assertTrue(scored['checks']['rules_respected']);self.assertFalse(scored['checks']['completion'])
 def test_rule_grade_detects_missing_mandatory_review_flag_even_when_label_is_withheld(self):
  f,result,case=self.assessment();result['status']='insufficient_evidence';result['decision'].update(final_label=None,review_required=False)
  result['rules']['review_required']=True
  self.assertFalse(grade(case,result,{'s1':{'text':QUOTE}},f.pred)['checks']['rules_respected'])
 def result(self):return MultiAgent(services(ScriptedLLM()).services).run('Giải thích mã',task='knowledge')
 def case(self):return {'kind':'knowledge','task':'knowledge','expected_intents':['knowledge'],'rubric':[['ma']],'relevant':['s1']}
 def test_success_status_and_trace_cannot_hide_forged_citation(self):
  result=self.result();result['explanation']['generation']['claims'][0]['evidence_id']='forged'
  scored=grade(self.case(),result,{'s1':{'text':QUOTE}})
  self.assertFalse(scored['checks']['citations']);self.assertFalse(scored['passed'])
 def test_fault_repair_requires_actual_state_change(self):
  case=self.case();case['kind']='repair';result=self.result();result['revisions']=[]
  scored=grade(case,result,{'s1':{'text':QUOTE}},fault_injected=True)
  self.assertFalse(scored['checks']['fault_repaired']);self.assertFalse(scored['checks']['fault_detected'])
 def test_rank_metrics_use_frozen_relevance_labels(self):
  scored=rank_scores(['other','relevant'],['relevant','also_relevant'])
  self.assertEqual(scored,{'hit_at_5':True,'recall_at_5':.5,'mrr_at_5':.5})
 def test_rates_keep_failures_in_denominator(self):
  self.assertEqual(rate([True,False])['rate'],.5);self.assertIsNone(rate([])['rate'])
 def test_summary_preserves_provider_failures_and_all_latency(self):
  result=self.result();case=self.case();good=grade(case,result,{'s1':{'text':QUOTE}})
  failed=copy.deepcopy(result);failed['status']='partial';failed['explanation']['generation']={'status':'unavailable'}
  bad=grade(case,failed,{'s1':{'text':QUOTE}})
  rows=[{'kind':'knowledge','case_id':'K1','elapsed_ms':10,'grade':good,'response':result,'fault_injected':False},
        {'kind':'knowledge','case_id':'K2','elapsed_ms':20,'grade':bad,'response':failed,'fault_injected':False}]
  summary=summarize(rows)
  self.assertEqual(summary['total_runs'],2);self.assertEqual(summary['groups']['knowledge']['unavailable'],1)
  self.assertEqual(summary['groups']['knowledge']['latency_all']['n'],2)
  self.assertEqual(summary['whole_flow']['total'],2)
