"""Controlled contradiction benchmark, not clinical diagnostic accuracy."""
import copy,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['KNOWLEDGE_BACKEND']='json'
sys.path.insert(0,str(ROOT/'src'))
from agent_system import Services, SingleAgent, MultiAgent
from specialist_agents import Specialists
sys.path.insert(0,str(ROOT/"tools/baseline_pre_policy"))
from before_agent_system import MultiAgent as BeforeMultiAgent
from before_specialist_agents import Specialists as BeforeSpecialists
import hashlib, statistics

PROFILE={'gender':'Female','age':48,'bmi':28.4,'hbA1c_level':5.8,'blood_glucose_level':140,'hypertension':0,'heart_disease':0,'smoking_history':'never'}
CASES=[
 {'id':'small_gap_disagreement','question':'yếu tố nguy cơ type 2','profile':PROFILE,'prediction':(.499,.501),'expected':'supported_with_limitations'},
 {'id':'explanation_repair','question':'yếu tố nguy cơ type 2','explanation_fault':'once','expected':'supported'},
 {'id':'explanation_persistent','question':'yếu tố nguy cơ type 2','explanation_fault':'always','expected':'verification_failed'},
 {'id':'conflict_after_retry','texts':['Mã phân loại dữ liệu là 1.','Mã phân loại dữ liệu là 0.'],'question':'Mã phân loại dữ liệu là gì?','empty_first':True,'expected':'human_review'},
 {'id':'numeric_conflict','texts':['Mã phân loại dữ liệu là 1.','Mã phân loại dữ liệu là 0.'],'question':'Mã phân loại dữ liệu là gì?','expected':'human_review'},
 {'id':'polarity_conflict','texts':['Dữ liệu này hợp lệ.','Dữ liệu này không hợp lệ.'],'question':'Dữ liệu này hợp lệ không?','expected':'human_review'},
 {'id':'source_agreement','texts':['Mã phân loại dữ liệu là 1.','Mã phân loại dữ liệu là 1.'],'question':'Mã phân loại dữ liệu là gì?','expected':'supported'},
 {'id':'different_context','texts':['Mã phân loại nhóm A là 1.','Mã phân loại nhóm B là 0.'],'question':'Mã phân loại của nhóm A và nhóm B là gì?','expected':'supported'},
 {'id':'model_disagreement','question':'yếu tố nguy cơ type 2','profile':PROFILE,'prediction':(.2,.8),'expected':'human_review'},
 {'id':'model_agreement','question':'yếu tố nguy cơ type 2','profile':PROFILE,'prediction':(.8,.9),'expected':'supported_with_limitations'},
 {'id':'missing_profile','question':'Đánh giá hồ sơ của tôi','profile':{},'expected':'needs_clarification'},
 {'id':'partial_profile','question':'Đánh giá hồ sơ','profile':{'age':48},'expected':'needs_clarification'},
 {'id':'missing_citation','question':'yếu tố nguy cơ type 2','empty_first':True,'expected':'supported'},
]

def main():
 s=Services(); original=s.knowledge.answer; original_predict=s.model.predict; original_docs=copy.deepcopy(s.knowledge.by_id)
 protected=[ROOT/'knowledge/corpus.json',ROOT/'knowledge/graph.json',ROOT/'artifacts/pytorch_mlp.pt',ROOT/'artifacts/diabetes_model.joblib']
 original_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
 rows=[]
 for case in CASES:
  for rep in range(5):
   for name in (['single','before','multi'] if rep%2==0 else ['multi','before','single']):
    calls=[]; prediction_calls=[]
    def answer(q):
     calls.append(q)
     if case.get('empty_first') and len(calls)==1: return {'answer':'Không có bằng chứng.','citations':[],'paths':[],'status':'insufficient_evidence'}
     if name=='single' and case.get('explanation_fault'):
      draft=copy.deepcopy(original(q)); draft['answer']='Nội dung chèn lỗi giả lập ZXQ999.'
      return draft
     if 'texts' not in case: return original(q)
     docs=[{'id':f'synthetic_{i}','url':f'https://example.invalid/fixture/{i}','title':'Synthetic nonclinical test source','text':text} for i,text in enumerate(case['texts'])]
     s.knowledge.by_id.update({d['id']:d for d in docs})
     return {'answer':' '.join(case['texts']),'citations':[dict(d,score=1) for d in docs],'paths':[],'status':'supported'}
    def predict(profile):
     prediction_calls.append(1)
     if 'prediction' not in case: return original_predict(profile)
     a,b=case['prediction']
     return {'model':'controlled_primary','probability':a,'threshold':.5,'predicted_class':int(a>=.5),'risk_level':'high' if a>=.5 else 'low','feature_impacts':[],
      'second_opinion':{'model':'controlled_peer','probability':b,'threshold':.5,'predicted_class':int(b>=.5)}}
    specialist_class=BeforeSpecialists if name=='before' else Specialists
    original_explain=specialist_class.explain
    if case.get('explanation_fault'):
     def corrupted(self,p):
      if case['explanation_fault']=='always' or not p.get('verification'):
       return {'answer':'Nội dung chèn lỗi giả lập ZXQ999.'}
      return original_explain(self,p)
     specialist_class.explain=corrupted
    s.knowledge.answer=answer; s.model.predict=predict
    try:
     result=(MultiAgent(s) if name=='multi' else BeforeMultiAgent(s) if name=='before' else SingleAgent(s)).run(case['question'],case.get('profile'))
    finally:
     specialist_class.explain=original_explain
     s.knowledge.answer=original; s.model.predict=original_predict; s.knowledge.by_id=copy.deepcopy(original_docs)
    correct=result['status']==case['expected']
    if case.get('explanation_fault'): correct=correct and 'ZXQ999' not in result['answer']
    if case['expected']=='human_review':
     correct=correct and (result.get('decision') or {}).get('review_required',False) and result['decision']['final_label'] is None and 'Cần xem xét thêm' in result['answer']
     if 'texts' in case: correct=correct and len(result['decision'].get('source_conflicts',[]))>0
    if case['expected']=='needs_clarification':
     correct=correct and result['prediction'] is None and not prediction_calls and bool((result.get('clarification') or {}).get('requested_fields'))
    if case.get('empty_first'): correct=correct and bool(result['knowledge']['citations'])
    if name=='multi':
     assert result['verification']['passed'] == (case['expected']!='verification_failed'), (case['id'],result['verification'])
     if case.get('explanation_fault'):
      assert any(x['action']=='rewrite_final_explanation' for x in result['revisions'])
      correct=correct and 'ZXQ999' not in result['answer']
     receivers={m['receiver'] for m in result['messages'] if m['performative'] in ['REQUEST','CHALLENGE']}
     assert {'ExplanationAgent','VerifierSafetyAgent'}<=receivers
     if case['expected']=='human_review':
      assert any(m['performative']=='CHALLENGE' and m['receiver']=='ReviewAgent' for m in result['messages'])
      assert any(x.get('action')=='revise_conclusion' and x['state_changed'] for x in result['revisions'])
      assert result['review']['passed']
    if case.get('prediction'):
     assert result['prediction']['probability']==case['prediction'][0]
    rows.append({'case_id':case['id'],'repeat':rep,'system':name,'expected':case['expected'],'correct':bool(correct),'detected':bool(result['validation_errors'] or result['revisions'] or (result.get('review') or {}).get('challenges') or result['status']=='needs_clarification'),'retrieval_calls':len(calls),'result':result})
 assert original_hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}, 'Benchmark modified real KB or model artifacts'
 summary={name:{'unique_cases':len(CASES),'unique_correct':sum(r['correct'] for r in rows if r['system']==name and r['repeat']==0),'runs':sum(r['system']==name for r in rows),'correct':sum(r['correct'] for r in rows if r['system']==name)} for name in ['single','before','multi']}
 for name in summary:
  part=[r for r in rows if r['system']==name and r['repeat']==0]
  errors=[r for r in part if r['case_id'] not in ['small_gap_disagreement','source_agreement','different_context','model_agreement']]
  repairable=[r for r in part if r['case_id'] in ['missing_citation','explanation_repair']]
  reviews=[r for r in part if r['result']['status']=='human_review']
  expected=[r for r in part if r['expected']=='human_review']
  not_needed=[r for r in part if r['expected']!='human_review']
  times=[r['result']['total_duration_ms'] for r in rows if r['system']==name]
  summary[name].update({'error_detection_rate':sum(r['detected'] for r in errors)/len(errors),
    'repair_success_rate':sum(r['correct'] for r in repairable)/len(repairable),
    'review_precision':sum(r['expected']=='human_review' for r in reviews)/len(reviews) if reviews else None,
    'review_recall':sum(r['result']['status']=='human_review' for r in expected)/len(expected),
    'unnecessary_review_rate':sum(r['result']['status']=='human_review' for r in not_needed)/len(not_needed),
    'answer_rubric_success':sum(r['correct'] for r in part)/len(part),
    'latency_median_ms':statistics.median(times),'latency_p95_ms':sorted(times)[int(.95*(len(times)-1))]})
 out={'protocol':{'corpus_sha256':hashlib.sha256((ROOT/'knowledge/corpus.json').read_bytes()).hexdigest(),'graph_sha256':hashlib.sha256((ROOT/'knowledge/graph.json').read_bytes()).hexdigest(),'protected_files_unchanged':True,'before_snapshot':'tools/baseline_pre_policy','kind':'controlled synthetic contradiction and routing suite','draft_fault_injection':'Single receives the corrupted answer draft from its answer tool; Multi receives the identical corrupted draft from ExplanationAgent. Same text, before final verification.','repeats':5,'cases':CASES,'limitations':['Fixtures are not medical evidence and are never persisted to the KB.','Exact numeric-template and negation conflicts only; not general natural-language entailment.','Model scores mocked only in explicitly marked model-agreement/disagreement scenarios.','Single is one pass; Multi can repair/refer. No claim of equal-budget architecture superiority.','Human review is handling uncertainty, not fixing the true disease label.']},'summary':summary,'runs':rows}
 (ROOT/'results/critic_challenge_benchmark.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
