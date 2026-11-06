"""Evaluate deployed agents on the original held-out split, without retraining."""
import copy, csv, hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, brier_score_loss, log_loss, confusion_matrix
ROOT=Path(__file__).resolve().parents[1]
os.environ['KNOWLEDGE_BACKEND']='json'
sys.path.insert(0,str(ROOT/'src'))
from agent_system import Services, SingleAgent, MultiAgent


def metrics(y,p,pred):
    y=np.asarray(y); p=np.asarray(p); pred=np.asarray(pred)
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    bins=[]
    for i in range(10):
        mask=(p>=i/10)&((p<(i+1)/10) if i<9 else (p<=1))
        bins.append({'lower':i/10,'upper':(i+1)/10,'count':int(mask.sum()),
                     'mean_probability':float(p[mask].mean()) if mask.any() else None,
                     'observed_rate':float(y[mask].mean()) if mask.any() else None})
    return {'count':len(y),'positives':int(y.sum()),'accuracy':accuracy_score(y,pred),
            'precision':precision_score(y,pred,zero_division=0),'recall':recall_score(y,pred,zero_division=0),
            'specificity':float(tn/(tn+fp)) if tn+fp else None,'f1':f1_score(y,pred,zero_division=0),
            'roc_auc':roc_auc_score(y,p) if len(set(y))==2 else None,
            'pr_auc':average_precision_score(y,p) if y.sum() else None,
            'brier':brier_score_loss(y,p),'log_loss':log_loss(y,np.clip(p,1e-15,1-1e-15),labels=[0,1]),
            'ece':sum(b['count']*abs(b['mean_probability']-b['observed_rate']) for b in bins if b['count'])/len(y),
            'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp),'calibration_bins':bins}


def main():
    start=time.perf_counter(); s=Services(); model=s.model
    path=ROOT/'data/diabetes_prediction_dataset.csv'
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest==model.metadata['dataset']['sha256'], 'Dataset differs from training artifact'
    df=pd.read_csv(path).drop_duplicates().reset_index(drop=True)
    features=model.metadata['features']; X,y=df[features],df.diabetes.astype(int)
    train,tmp,yt,ytemp=train_test_split(X,y,test_size=.30,stratify=y,random_state=42)
    val,test,yv,labels=train_test_split(tmp,ytemp,test_size=.50,stratify=ytemp,random_state=42)
    assert len(test)==model.metadata['splits']['test']
    p=model.pipeline.predict_proba(test)[:,1]; ref=model.reference_pipeline.predict_proba(test)[:,1]
    predictions=[]
    for a,b in zip(p,ref):
        predictions.append({'model':model.model_name,'probability':round(float(a),6),
            'threshold':round(model.threshold,4),'predicted_class':int(a>=model.threshold),
            'risk_level':'low' if a<model.threshold*.6 else 'moderate' if a<model.threshold else 'high',
            'feature_impacts':[],'model_version':'2.0.0',
            'second_opinion':{'model':model.reference_name,'probability':float(b),
                'threshold':model.reference_threshold,'predicted_class':int(b>=model.reference_threshold)}})
    # Check batch scoring against normal online inference before reusing scores.
    profiles=test.to_dict('records'); checked=0
    for i in np.linspace(0,len(test)-1,12,dtype=int):
        if model.validate(profiles[i]): continue
        online=model.predict(profiles[i]); batch=predictions[i]
        assert abs(online['probability']-batch['probability'])<=2e-6
        assert online['predicted_class']==batch['predicted_class']
        checked+=1
    original=model.predict; rows=[]; runners={'single':SingleAgent(s),'multi':MultiAgent(s)}
    question='yếu tố nguy cơ type 2'
    try:
        for i,(idx,profile,prediction) in enumerate(zip(test.index,profiles,predictions)):
            # Only model inference is precomputed. Validation, Critic, repair, routing
            # and final status execute through both real Agent.run methods for every row.
            model.predict=lambda profile, value=prediction: copy.deepcopy(value)
            for name in (['single','multi'] if i%2==0 else ['multi','single']):
                result=runners[name].run(question,profile)
                out=result['prediction']
                rows.append({'row_id':int(idx),'system':name,'label':int(labels.loc[idx]),
                    'probability':out['probability'] if out else None,
                    'prediction':out['predicted_class'] if out else None,
                    'status':result['status'],'referred':result['status']=='human_review',
                    'accepted':result['status']=='supported_with_limitations',
                    'validation_errors':json.dumps(result['validation_errors'],ensure_ascii=False)})
            if (i+1)%1000==0: print(f'Processed {i+1}/{len(test)} profiles through both agents',flush=True)
    finally: model.predict=original
    summary={}
    for name in runners:
        part=[r for r in rows if r['system']==name]; scored=[r for r in part if r['prediction'] is not None]
        accepted=[r for r in scored if r['accepted']]; referred=[r for r in scored if r['referred']]
        summary[name]={'all_scored':metrics([r['label'] for r in scored],[r['probability'] for r in scored],[r['prediction'] for r in scored]),
            'accepted_only':metrics([r['label'] for r in accepted],[r['probability'] for r in accepted],[r['prediction'] for r in accepted]) if accepted else None,
            'total':len(part),'invalid':len(part)-len(scored),'referred':len(referred),
            'coverage':len(accepted)/len(part),'coverage_of_valid':len(accepted)/len(scored),
            'errors_referred':sum(r['prediction']!=r['label'] for r in referred),
            'false_negatives_referred':sum(r['label']==1 and r['prediction']==0 for r in referred),
            'referred_positives':sum(r['label']==1 for r in referred)}
    # Live latency includes uncached prediction + explanation: identical ten profiles,
    # three repeats, alternating order. Do not report cached sweep timings as latency.
    timing={'single':[],'multi':[]}
    chosen=[profile for profile in profiles if not model.validate(profile)][:10]
    for rep in range(3):
        for i,profile in enumerate(chosen):
            for name in (['single','multi'] if (rep+i)%2==0 else ['multi','single']):
                result=runners[name].run(question,profile); timing[name].append(result['total_duration_ms'])
    for name,values in timing.items():
        summary[name]['live_latency']={'runs':len(values),'median_ms':float(np.median(values)),
                                       'p95_ms':float(np.percentile(values,95)),'values_ms':values}
    single=[r for r in rows if r['system']=='single']; multi=[r for r in rows if r['system']=='multi']
    paired={'different_labels':sum(a['prediction']!=b['prediction'] for a,b in zip(single,multi)),
            'different_probabilities':sum(a['probability']!=b['probability'] for a,b in zip(single,multi)),
            'different_statuses':sum(a['status']!=b['status'] for a,b in zip(single,multi))}
    output={'protocol':{'created_at':datetime.now(timezone.utc).isoformat(),'dataset':str(path.relative_to(ROOT)),
        'corpus_sha256':hashlib.sha256((ROOT/'knowledge/corpus.json').read_bytes()).hexdigest(),
        'graph_sha256':hashlib.sha256((ROOT/'knowledge/graph.json').read_bytes()).hexdigest(),
        'review_policy':json.loads((ROOT/'artifacts/review_policy.json').read_text()),
        'sha256':digest,'raw_rows':model.metadata['dataset']['raw_rows'],'deduplicated_rows':len(df),
        'split':{'train':len(train),'validation':len(val),'test':len(test)},'seed':42,
        'threshold':model.threshold,'model':model.model_name,'backend':'json','online_parity_checks':checked,
        'batch_note':'Same checkpoints scored in batch. Both Agent.run workflows execute per held-out row. Feature impacts omitted in sweep only; no decision code uses them. Live latency measured separately without cache.',
        'limitations':['No retraining, threshold tuning or probability calibration on test.',
            'Dataset labels are the reference, not a clinical diagnosis.',
            'Same predictive model and threshold: Multi only changes review status, not probability or class.',
            'Referral is not a positive prediction; report coverage and accepted-only metrics separately.',
            'Brier/ECE evaluate probability on groups, not certainty about an individual.',
            'JSON knowledge backend; not a Neo4j performance benchmark.']},
        'model_all_test':metrics(labels,p,p>=model.threshold),'systems':summary,'paired':paired,
        'execution_seconds':time.perf_counter()-start}
    (ROOT/'results/diabetes_agent_benchmark.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(rows).to_csv(ROOT/'results/diabetes_agent_predictions.csv',index=False)
    print(json.dumps({'paired':paired,'systems':{k:{x:v for x,v in z.items() if x not in ['all_scored','accepted_only']} for k,z in summary.items()}},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
