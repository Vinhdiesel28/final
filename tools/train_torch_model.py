"""Train a real PyTorch MLP with recorded epoch losses and held-out evaluation."""
import copy
import json
import sys
import time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.base import clone
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from torch_model import RiskMLP, TorchPipeline
from train_models import FEATURES, metric_row, choose_threshold


def main():
    torch.manual_seed(42); np.random.seed(42); torch.set_num_threads(2)
    df = pd.read_csv(ROOT/'data/diabetes_prediction_dataset.csv').drop_duplicates()
    x, y = df[FEATURES], df.diabetes.astype(int)
    xt, xv, yt, yv = train_test_split(x, y, test_size=.30, stratify=y, random_state=42)
    xv, xe, yv, ye = train_test_split(xv, yv, test_size=.5, stratify=yv, random_state=42)
    old = joblib.load(ROOT/'artifacts/diabetes_model.joblib')
    pre = clone(old['pipeline'].named_steps['preprocess'])
    a = torch.tensor(pre.fit_transform(xt), dtype=torch.float32)
    b = torch.tensor(pre.transform(xv), dtype=torch.float32)
    target = torch.tensor(yt.to_numpy(), dtype=torch.float32)
    valid = torch.tensor(yv.to_numpy(), dtype=torch.float32)
    model = RiskMLP(a.shape[1]); optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    criterion = nn.BCEWithLogitsLoss()
    best, patience, history = float('inf'), 0, []
    started = time.perf_counter()
    for epoch in range(1, 61):
        model.train(); order = torch.randperm(len(a)); total = 0.
        for ids in order.split(512):
            optimizer.zero_grad(); loss = criterion(model(a[ids]), target[ids])
            loss.backward(); optimizer.step(); total += loss.item()*len(ids)
        model.eval()
        with torch.inference_mode(): value = criterion(model(b), valid).item()
        history.append({'epoch':epoch, 'train_loss':total/len(a), 'validation_loss':value})
        if value < best-1e-5:
            best = value; state = copy.deepcopy(model.state_dict()); patience = 0
        else: patience += 1
        if epoch % 5 == 0: print(history[-1], flush=True)
        if patience >= 8: break
    checkpoint = ROOT/'artifacts/pytorch_mlp.pt'
    torch.save({'state_dict':state, 'input_dim':a.shape[1]}, checkpoint)
    joblib.dump(pre, ROOT/'artifacts/pytorch_preprocess.joblib')
    pipe = TorchPipeline(checkpoint, pre); threshold = choose_threshold(pipe, xv, yv)
    duration = time.perf_counter()-started
    report = {'architecture':[int(a.shape[1]),64,32,1], 'framework':'PyTorch',
              'seed':42, 'threshold':threshold, 'epochs':len(history),
              'splits':{'train':len(xt),'validation':len(xv),'test':len(xe)},
              'validation':metric_row('PyTorch MLP',pipe,xv,yv,threshold,duration),
              'test':metric_row('PyTorch MLP',pipe,xe,ye,threshold,duration)}
    (ROOT/'artifacts/pytorch_metadata.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    pd.DataFrame(history).to_csv(ROOT/'results/pytorch_training_history.csv',index=False)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__': main()
