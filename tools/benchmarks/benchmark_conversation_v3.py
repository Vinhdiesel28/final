"""Current v3 only: real cloud retrieval, held-out model, live LLM workflows.

Qrels/rubrics and ground-truth labels stay in the evaluator. Synthetic faults
only alter an in-memory initial draft; never upload them to medical databases.
"""
import argparse,copy,csv,json,logging,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score,roc_auc_score,average_precision_score,brier_score_loss,confusion_matrix
from agent_system import Services,MultiAgent
from services.agent_llm import AgentLLM
from benchmark_v3 import digest_file,runtime_fingerprint,latency,rate,rank_scores,grade,summarize
from knowledge.retrieval_terms import search_query
from services.knowledge_service import normalize

CASE_FILE=ROOT/'benchmarks/v3_cases.json';OUT=ROOT/'results/benchmark_v3.json'

def now():return datetime.now(timezone.utc).isoformat()

class FaultLLM:
    def __init__(self,base,kind):self.base=base;self.kind=kind;self.injected=False;self.original=None
    def complete(self,task,system,payload,output_type,max_tokens=1100):
        result,meta=self.base.complete(task,system,payload,output_type,max_tokens)
        if task=='grounded_draft' and self.kind and not self.injected and result.claims:
            self.original=result.model_dump();data=copy.deepcopy(self.original)
            if self.kind=='invalid_citation':data['claims'][0]['evidence_id']='benchmark_injected_invalid_id'
            elif self.kind=='unsupported_number':data['claims'][0]['text']+=' Mã thử nghiệm là 999999.'
            else:raise ValueError('Unknown benchmark fault')
            result=output_type.model_validate(data);self.injected=True
        return result,meta

def heldout(services):
    df=pd.read_csv(ROOT/'data/diabetes_prediction_dataset.csv').drop_duplicates()
    features=services.model.metadata['features'];x=df[features];y=df.diabetes.astype(int)
    _,temp,_,yt=train_test_split(x,y,test_size=.30,stratify=y,random_state=42)
    _,test,_,truth=train_test_split(temp,yt,test_size=.5,stratify=yt,random_state=42)
    return test,truth

def model_component(services,x,y):
    start=time.perf_counter();prob=services.model.pipeline.predict_proba(x)[:,1];pred=(prob>=services.model.threshold).astype(int)
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {'scope':'Current deployed checkpoint on original untouched held-out split; not a full MAS score',
      'rows':len(y),'positives':int(sum(y)),'threshold':services.model.threshold,
      'accuracy':float(accuracy_score(y,pred)),'precision':float(precision_score(y,pred,zero_division=0)),
      'recall':float(recall_score(y,pred,zero_division=0)),'f1':float(f1_score(y,pred,zero_division=0)),
      'roc_auc':float(roc_auc_score(y,prob)),'pr_auc':float(average_precision_score(y,prob)),'brier':float(brier_score_loss(y,prob)),
      'confusion':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)},'batch_ms':round((time.perf_counter()-start)*1000,2)}

def summarize_retrieval(rows):
    valid=[r for r in rows if not r.get('error')]
    return {'unique_questions':len({r['case_id'] for r in rows}),'runs':len(rows),'errors':len(rows)-len(valid),
       'hit_at_5':rate(r['scores']['hit_at_5'] for r in valid),
       'recall_at_5':float(np.mean([r['scores']['recall_at_5'] for r in valid])) if valid else None,
       'mrr_at_5':float(np.mean([r['scores']['mrr_at_5'] for r in valid])) if valid else None,
       'latency':latency([r['elapsed_ms'] for r in rows])}

def persist(report, output):
    report['updated_at']=now();report['summary']=summarize(report['trials'])
    if report.get('retrieval_trials'):report['retrieval_summary']=summarize_retrieval(report['retrieval_trials'])
    temp=output.with_suffix('.json.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(output)
    with output.with_name(output.stem+'_trials.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['case_id','repeat','kind','status','passed','elapsed_ms','fault_injected']);writer.writeheader()
        for r in report['trials']:writer.writerow({k:r[k] for k in ('case_id','repeat','kind','elapsed_ms','fault_injected')}|{'status':r['response']['status'],'passed':r['grade']['passed']})

def main():
    logging.getLogger('neo4j.notifications').setLevel(logging.ERROR)
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['components','live','all'],default='all')
    parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--resume',action='store_true')
    parser.add_argument('--rescore',action='store_true')
    parser.add_argument('--assessment-only',action='store_true')
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args()
    if args.assessment_only and (args.phase!='live' or args.output.resolve()==OUT.resolve()):
        parser.error('--assessment-only requires --phase live and a separate --output')
    if args.rescore and not args.resume:parser.error('--rescore requires --resume')
    if not 1<=args.repeats<=10:parser.error('repeats must be 1..10')
    cases=json.loads(CASE_FILE.read_text(encoding='utf-8'))
    if args.assessment_only:cases['live']=[case for case in cases['live'] if case['kind']=='assessment']
    services=Services();hybrid=services.knowledge.hybrid
    if not hybrid:raise RuntimeError('Current Hybrid KB is required')
    by_id={r['id']:r for r in hybrid.documents};qrels={r['id']:r for r in cases['retrieval']}
    for case in qrels.values():
        if not case['relevant'] or any(key not in by_id or normalize(case['anchor']) not in normalize(by_id[key]['text']) for key in case['relevant']):
            raise RuntimeError('Qrel anchor no longer matches current source: '+case['id'])
    fingerprint=runtime_fingerprint();case_hash=digest_file(CASE_FILE)
    report=json.loads(args.output.read_text(encoding='utf-8')) if args.resume and args.output.exists() else {
      'protocol':{'architecture':'conversation_v3','runtime_hash':fingerprint,'case_hash':case_hash,'case_version':cases['version'],
        'created_at':now(),'kb_version':hybrid.version,'backend':hybrid.metadata()['backend'],'llm_model':os.environ.get('LLM_MODEL'),
        'model_sha256':digest_file(ROOT/'artifacts/pytorch_mlp.pt'),'dataset_sha256':digest_file(ROOT/'data/diabetes_prediction_dataset.csv'),
        'repeats':args.repeats,'planned_live_runs':args.repeats*len(cases['live']),'cache':'disabled for all live LLM calls',
        'latency_scope':'Engine wall time excluding Services/model startup and browser HTTP; includes cloud calls, retries and provider waits',
        'grading':'Frozen source qrels + keyword/number rubrics + exact quotations + state/output invariants. No independent clinical semantic adjudication.',
        'faults':'Injected once into initial draft after real LLM generation, in evaluator RAM only; real v3 Critic and repair handlers execute',
        'comparison':'No LegacyMultiAgent metrics and no claim of superiority over Single-Agent; before/after repair is not Single-vs-Multi',
        'annotation':cases['annotation']},'phase':'running','trials':[],'retrieval_trials':[],
      'limitations':['Small pilot; repeated runs are not independent patients/questions.',
        'Exact quotation and numeric checks do not prove semantic/clinical correctness.',
        'Rubrics and qrels are source-grounded but not exhaustive or clinician-reviewed.',
        'LLM and cloud availability are included; incomplete runs count as failures, not dropped.',
        'Latency uses warm application services, cache disabled; no cold-start or load test.',
        'No model retraining, threshold changes, calibration fitting or benchmark data written to KB.']}
    if report['protocol']['runtime_hash']!=fingerprint or report['protocol']['case_hash']!=case_hash or report['protocol']['kb_version']!=hybrid.version or report['protocol']['repeats']!=args.repeats or report['protocol']['planned_live_runs']!=args.repeats*len(cases['live']):
        raise RuntimeError('Cannot resume across changed runtime/cases/KB/repeat count')
    test,truth=heldout(services)
    if args.rescore:
        specs={case['id']:case for case in cases['live']};changed=0
        for row in report['trials']:
            case=copy.deepcopy(specs[row['case_id']])
            if case.get('retrieval_case'):
                reference=qrels[case['retrieval_case']];case.update(question=reference['question'],relevant=reference['relevant'])
            expected=services.model.predict(row['profile']) if row['kind']=='assessment' else None
            updated=grade(case,row['response'],by_id,expected,row['fault_injected'])
            if updated!=row['grade']:
                row.setdefault('previous_grade',row['grade']);row['grade']=updated;changed+=1
        report['protocol']['evaluator_hash']=digest_file(ROOT/'src/benchmark_v3.py')
        report.setdefault('scoring_revisions',[]).append({'at':now(),'changed_runs':changed,
            'reason':'Rule check distinguishes legitimate evidence abstention from a mandatory model-review flag. Frozen qrels/rubrics and raw responses unchanged.'})
        persist(report,args.output);print(json.dumps({'phase':'rescored','runs':len(report['trials']),'changed_runs':changed}));return 0
    if args.phase in {'components','all'}:
        report['model_component']=model_component(services,test,truth);persist(report,args.output)
        done={(r['case_id'],r['repeat']) for r in report['retrieval_trials']}
        for repeat in range(args.repeats):
            for case in cases['retrieval']:
                if (case['id'],repeat) in done:continue
                start=time.perf_counter()
                row={'case_id':case['id'],'repeat':repeat,'question':case['question'],'query':case['query'],'qrels':case['relevant']}
                try:
                    result,analysis=hybrid.retrieve(search_query(case['query']),5)
                    row.update(ids=[r['id'] for r in result],scores=rank_scores([r['id'] for r in result],case['relevant']),analysis=analysis)
                except Exception as exc:row['error']=type(exc).__name__
                row['elapsed_ms']=round((time.perf_counter()-start)*1000,2);report['retrieval_trials'].append(row);persist(report,args.output)
        print(json.dumps({'phase':'components_done','retrieval':report['retrieval_summary'],'model_rows':len(truth)},ensure_ascii=True),flush=True)
    if args.phase in {'live','all'}:
        base_llm=AgentLLM(cache_ttl=0);done={(r['case_id'],r['repeat']) for r in report['trials']}
        for repeat in range(args.repeats):
            ordered=cases['live'] if repeat%2==0 else list(reversed(cases['live']))
            for original_case in ordered:
                if (original_case['id'],repeat) in done:continue
                case=copy.deepcopy(original_case)
                if case.get('retrieval_case'):
                    reference=qrels[case['retrieval_case']];case.update(question=reference['question'],relevant=reference['relevant'])
                profile=None;expected=None;dataset_row=None;label=None
                if case.get('dataset_profile'):
                    wanted=1 if case['dataset_profile']=='first_positive_test' else 0
                    dataset_row=int(truth[truth==wanted].index[0]);profile=test.loc[dataset_row].to_dict();label=int(truth.loc[dataset_row])
                    if case.get('remove_field'):profile.pop(case['remove_field'])
                    profile.update(case.get('replace_field',{}))
                    if case['kind']=='assessment':expected=services.model.predict(profile)
                wrapper=FaultLLM(base_llm,case.get('fault'));services.agent_llm=wrapper;runner=MultiAgent(services)
                start=time.perf_counter();response=runner.run(case['question'],profile,task=case['task']);elapsed=(time.perf_counter()-start)*1000
                row={'case_id':case['id'],'repeat':repeat,'kind':case['kind'],'task':case['task'],'question':case['question'],
                     'dataset_row':dataset_row,'ground_truth_label':label,'profile':profile,'fault':case.get('fault'),
                     'fault_injected':wrapper.injected,'draft_before_injection':wrapper.original,'elapsed_ms':round(elapsed,2),'response':response,
                     'grade':grade(case,response,by_id,expected,wrapper.injected)}
                report['trials'].append(row);persist(report,args.output)
                print(json.dumps({'case':case['id'],'repeat':repeat,'status':response['status'],'passed':row['grade']['passed'],'ms':row['elapsed_ms']},ensure_ascii=True),flush=True)
                generation=(response.get('explanation') or {}).get('generation',{})
                if response['status']=='partial' and generation.get('error')=='rate_limited':
                    report['phase']='quota_limited';report['retry_after_seconds']=generation.get('retry_after_seconds');persist(report,args.output)
                    print(json.dumps({'phase':'quota_limited','completed':len(report['trials']),'planned':report['protocol']['planned_live_runs']},ensure_ascii=True));return 2
    report['phase']='complete' if len(report['trials'])==report['protocol']['planned_live_runs'] else 'components_complete'
    persist(report,args.output)
    if hybrid.remote_vectors:hybrid.remote_vectors.client.close()
    services.knowledge.store.driver.close()
    return 0

if __name__=='__main__':sys.exit(main())
