"""Chapter 6: a transductive similarity graph from the student's CDC dataset."""
import copy, json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import kneighbors_graph
from sklearn.metrics import f1_score, roc_auc_score, precision_score, recall_score
ROOT=Path(__file__).resolve().parents[1]

def main():
    torch.set_num_threads(2); np.random.seed(42)
    raw=pd.read_csv(ROOT/'data/cdc_brfss_2015.csv')
    unique=raw.drop_duplicates()
    indices,_=train_test_split(unique.index.to_numpy(),train_size=1600,
        stratify=unique.Diabetes_012.gt(0),random_state=42)
    df=raw.iloc[indices].reset_index(drop=True)
    y=df.Diabetes_012.gt(0).astype(int).to_numpy()
    tr,rest=train_test_split(np.arange(len(df)),test_size=.4,stratify=y,random_state=42)
    va,te=train_test_split(rest,test_size=.5,stratify=y[rest],random_state=42)
    scaler=StandardScaler().fit(df.drop(columns='Diabetes_012').iloc[tr])
    x=torch.tensor(scaler.transform(df.drop(columns='Diabetes_012')),dtype=torch.float32)
    # Labels are excluded from features and edge construction.
    adjacency=kneighbors_graph(x.numpy(),10,mode='connectivity',include_self=False).toarray()
    adjacency=np.maximum(adjacency,adjacency.T)
    edge_count=int(adjacency.sum()/2)
    mean=torch.tensor(adjacency/adjacency.sum(1,keepdims=True),dtype=torch.float32)
    loop=adjacency+np.eye(len(df));degree=loop.sum(1)**(-.5)
    norm=torch.tensor(degree[:,None]*loop*degree[None,:],dtype=torch.float32)
    target=torch.tensor(y,dtype=torch.float32)
    class Network(nn.Module):
        def __init__(self,kind):
            super().__init__();self.kind=kind
            self.first=nn.Linear(42 if kind=='GraphSAGE' else 21,32)
            self.last=nn.Linear(64 if kind=='GraphSAGE' else 32,1)
        def forward(self,x):
            if self.kind=='GCN':
                h=torch.relu(self.first(norm@x));return self.last(norm@h).squeeze(-1)
            if self.kind=='GraphSAGE':
                h=torch.relu(self.first(torch.cat([x,mean@x],dim=1)))
                return self.last(torch.cat([h,mean@h],dim=1)).squeeze(-1)
            return self.last(torch.relu(self.first(x))).squeeze(-1)
    out=ROOT/'results/deep_graph';out.mkdir(exist_ok=True)
    sample=df.copy();sample.insert(0,'source_row',indices);sample['split']='test'
    sample.loc[tr,'split']='train';sample.loc[va,'split']='validation'
    sample.to_csv(out/'cdc_graph_sample.csv',index=False)
    rows=[];histories=[]
    for kind in ['MLP','GCN','GraphSAGE']:
        torch.manual_seed(42);model=Network(kind)
        optimizer=torch.optim.Adam(model.parameters(),lr=.01,weight_decay=.0005)
        criterion=nn.BCEWithLogitsLoss(pos_weight=torch.tensor(float((y[tr]==0).sum()/(y[tr]==1).sum())))
        best=float('inf');started=time.perf_counter()
        for epoch in range(1,81):
            model.train();optimizer.zero_grad();loss=criterion(model(x)[tr],target[tr]);loss.backward();optimizer.step()
            model.eval()
            with torch.inference_mode():vl=criterion(model(x)[va],target[va]).item()
            histories.append({'model':kind,'epoch':epoch,'train_loss':loss.item(),'validation_loss':vl})
            if vl<best:best=vl;state=copy.deepcopy(model.state_dict());best_epoch=epoch
        model.load_state_dict(state);model.eval()
        with torch.inference_mode():p=torch.sigmoid(model(x)).numpy()
        thresholds=np.linspace(.05,.95,91)
        threshold=float(max(thresholds,key=lambda t:f1_score(y[va],p[va]>=t,zero_division=0)))
        row={'model':kind,'best_epoch':best_epoch,'threshold':threshold,
             'validation_f1':f1_score(y[va],p[va]>=threshold,zero_division=0),
             'test_f1':f1_score(y[te],p[te]>=threshold,zero_division=0),
             'test_auc':roc_auc_score(y[te],p[te]),
             'test_precision':precision_score(y[te],p[te]>=threshold,zero_division=0),
             'test_recall':recall_score(y[te],p[te]>=threshold,zero_division=0),
             'seconds':time.perf_counter()-started}
        rows.append(row);print(json.dumps(row),flush=True)
        torch.save(state,out/f'{kind.lower()}.pt')
    metadata={'source':'data/cdc_brfss_2015.csv','raw_rows':len(raw),'deduplicated_rows':len(unique),'nodes':len(df),
        'features':21,'undirected_edges_without_self_loops':edge_count,'knn':10,'seed':42,
        'split':{'train':len(tr),'validation':len(va),'test':len(te)},
        'positive_nodes':int(y.sum()),'label':'Diabetes_012 > 0 (prediabetes OR diabetes)',
        'protocol':'transductive: all node features and edges visible; only training labels in loss',
        'models':rows,'selected_by_validation':max(rows,key=lambda r:r['validation_f1'])['model']}
    (out/'metrics.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    pd.DataFrame(histories).to_csv(out/'learning.csv',index=False)
    print(json.dumps({k:v for k,v in metadata.items() if k!='models'}),flush=True)

if __name__=='__main__':main()
