"""Paired end-to-end evaluation with held-out labels and injected retrieval failure."""
import json, sys, time, statistics, os
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, accuracy_score

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
os.environ['KNOWLEDGE_BACKEND']='json'
from train_models import FEATURES, TARGET
from agent_system import Services, SingleAgent, MultiAgent

df=pd.read_csv(ROOT/'data/diabetes_prediction_dataset.csv').drop_duplicates().reset_index(drop=True)
X,y=df[FEATURES],df[TARGET].astype(int)
_,tmp,_,yt=train_test_split(X,y,test_size=.30,stratify=y,random_state=42)
_,test,_,labels=train_test_split(tmp,yt,test_size=.50,stratify=yt,random_state=42)
sample=test.sample(n=100,random_state=73)
services=Services(); runners={'single':SingleAgent(services),'multi':MultiAgent(services)}
rows=[]
for i,(idx,row) in enumerate(sample.iterrows()):
    for name in (['single','multi'] if i%2==0 else ['multi','single']):
        result=runners[name].run('yếu tố nguy cơ type 2',row.to_dict())
        rows.append({'index':int(idx),'system':name,'label':int(labels.loc[idx]),'prediction':result['prediction']['predicted_class'],
                     'review':result['status']=='human_review','latency_ms':result['total_duration_ms']})
frame=pd.DataFrame(rows); summary={}
for name,part in frame.groupby('system'):
    accepted=part[~part.review]
    summary[name]={'count':len(part),'accuracy_all_raw_predictions':accuracy_score(part.label,part.prediction),
       'coverage':len(accepted)/len(part),'selective_accuracy':accuracy_score(accepted.label,accepted.prediction) if len(accepted) else None,
       'confusion_all':confusion_matrix(part.label,part.prediction,labels=[0,1]).tolist(),
       'confusion_accepted':confusion_matrix(accepted.label,accepted.prediction,labels=[0,1]).tolist(),
       'errors_referred':int(((part.label!=part.prediction)&part.review).sum()),
       'latency_median_ms':float(part.latency_ms.median()),'latency_p95_ms':float(part.latency_ms.quantile(.95))}
# Each run starts with the same injected one-shot empty retrieval response.
faults=[]
profile=sample.iloc[0].to_dict(); original=services.knowledge.answer
for kind in ['single','multi']:
    for repetition in range(5):
        calls=[0]
        def injected(question):
            calls[0]+=1
            if calls[0]==1:return {'answer':'Không có bằng chứng.','citations':[],'paths':[],'status':'insufficient_evidence'}
            return original(question)
        services.knowledge.answer=injected
        try: result=runners[kind].run('yếu tố nguy cơ type 2',profile)
        finally: services.knowledge.answer=original
        faults.append({'system':kind,'repetition':repetition,'retrieval_calls':calls[0],
            'citations_after':len(result['knowledge']['citations']),'status':result['status'],'latency_ms':result['total_duration_ms']})
latencies={'single':[],'multi':[]}
for repeat in range(20):
    for kind in (['single','multi'] if repeat%2==0 else ['multi','single']):
        latencies[kind].append(runners[kind].run('yếu tố nguy cơ type 2',profile)['total_duration_ms'])
timing={k:{'runs':len(v),'median_ms':statistics.median(v),'p95_ms':float(np.percentile(v,95))} for k,v in latencies.items()}
out={'protocol':'100 random held-out cases, alternating execution order; five repeated injected transient empty-retrieval faults per system; 20 repeated latency runs per system. Citation presence is not semantic evidence verification. JSON KB backend.',
     'summary':summary,'faults':faults,'repeated_latency':timing}
(ROOT/'results/paired_agent_evaluation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
frame.to_csv(ROOT/'results/paired_agent_evaluation.csv',index=False)
print(json.dumps(out,ensure_ascii=False,indent=2))
