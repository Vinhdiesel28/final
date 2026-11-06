"""Evaluate the frozen review policy on a random held-out test sample."""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, recall_score, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from train_models import FEATURES, TARGET
from model_service import DiabetesModelService

df = pd.read_csv(ROOT / 'data/diabetes_prediction_dataset.csv').drop_duplicates().reset_index(drop=True)
X, y = df[FEATURES], df[TARGET].astype(int)
_, xt, _, yt = train_test_split(X, y, test_size=.30, stratify=y, random_state=42)
_, test, _, labels = train_test_split(xt, yt, test_size=.50, stratify=yt, random_state=42)
sample = test.sample(n=1000, random_state=73)
labels = labels.loc[sample.index].to_numpy()
model = DiabetesModelService()
p = model.pipeline.predict_proba(sample)[:, 1]
r = model.reference_pipeline.predict_proba(sample)[:, 1]
pred = p >= model.threshold
flag = (pred != (r >= model.reference_threshold)) | (np.abs(p-model.threshold) < .05)
out = {'description':'Random held-out test sample; model disagreement or near threshold sends case to human review. No human outcome assumed.',
       'n':len(sample), 'single_accuracy':accuracy_score(labels,pred), 'single_recall':recall_score(labels,pred),
       'single_confusion_matrix':confusion_matrix(labels,pred,labels=[0,1]).tolist(),
       'multi_coverage':float((~flag).mean()), 'multi_review_count':int(flag.sum()),
       'multi_selective_accuracy':accuracy_score(labels[~flag],pred[~flag]),
       'multi_selective_confusion_matrix':confusion_matrix(labels[~flag],pred[~flag],labels=[0,1]).tolist(),
       'errors_flagged':int((flag & (pred != labels)).sum()), 'total_errors':int((pred != labels).sum()),
       'positive_cases_referred':int((flag & (labels == 1)).sum())}
path=ROOT/'results/review_evaluation.json'
path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
