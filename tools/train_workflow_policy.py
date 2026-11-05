import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from workflow_policy import train_policy
if __name__=='__main__':
    artifact=train_policy()
    (ROOT/'artifacts/workflow_q_policy.json').write_text(json.dumps(artifact,indent=2),encoding='utf-8')
    print({k:v for k,v in artifact.items() if k not in ['q_table','returns']})
