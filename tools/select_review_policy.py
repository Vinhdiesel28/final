"""Select an uncertainty/referral policy on validation only; never change model scores."""
import hashlib,json,sys
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.model_selection import train_test_split
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from model_service import DiabetesModelService
m=DiabetesModelService(); path=ROOT/'data/diabetes_prediction_dataset.csv'
assert hashlib.sha256(path.read_bytes()).hexdigest()==m.metadata['dataset']['sha256']
df=pd.read_csv(path).drop_duplicates().reset_index(drop=True); X=df[m.metadata['features']];y=df.diabetes.astype(int)
_,tmp,_,yt=train_test_split(X,y,test_size=.30,stratify=y,random_state=42)
val,_,labels,_=train_test_split(tmp,yt,test_size=.50,stratify=yt,random_state=42)
p=m.pipeline.predict_proba(val)[:,1]; r=m.reference_pipeline.predict_proba(val)[:,1]
pred=p>=m.threshold; disagreement=pred!=(r>=m.reference_threshold); gap=np.abs(p-r); margin=np.abs(p-m.threshold); errors=pred!=labels.to_numpy()
rows=[]
# Prespecified engineering objective: cost(error accepted)=1, cost(referral)=.25,
# referral budget<=5%. This is not a clinical cost model.
for width in [.01,.025,.05,.1]:
 for min_gap in [.02,.05,.1,.2,.4]:
  mask=(disagreement&(gap>=min_gap))|((margin<=width)&(gap>=min_gap/2))
  if mask.mean()>.05: continue
  rows.append({'margin_width':width,'minimum_gap':min_gap,'referrals':int(mask.sum()),'errors_referred':int((errors&mask).sum()),'cost':float((errors&~mask).sum()+.25*mask.sum())})
best=min(rows,key=lambda a:(a['cost'],a['referrals'],a['margin_width'],-a['minimum_gap']))
out={'version':'validation-referral-v1','selected':best,'validation_rows':len(val),'validation_errors':int(errors.sum()),'no_review_cost':int(errors.sum()),'objective':'accepted error=1; referral=.25; maximum referral fraction=.05; engineering costs, not clinical','selection_split':'validation only, stratified 70/15/15 seed 42','candidates':rows,'dataset_sha256':m.metadata['dataset']['sha256'],'model_sha256':hashlib.sha256((ROOT/'artifacts/pytorch_mlp.pt').read_bytes()).hexdigest(),'reference_sha256':hashlib.sha256((ROOT/'artifacts/diabetes_model.joblib').read_bytes()).hexdigest(),'primary_threshold':m.threshold,'reference_threshold':m.reference_threshold}
(ROOT/'artifacts/review_policy.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out['selected']))
