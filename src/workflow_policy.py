"""Q-learning for educational workflow selection, never drug/treatment choice.

The environment is a documented synthetic workflow simulator, not patient data.
Rewards express completeness and workflow cost, not health benefit.
"""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
ACTIONS=['ask_for_information','show_sources','explain_score','request_human_review']


def allowed_actions(state):
    missing, evidence, review = state
    if missing: return [0]
    if review: return [3]
    if not evidence: return [1]
    return [1,2,3]


def train_policy(seed=42, episodes=3000):
    rng=np.random.default_rng(seed); q=np.zeros((8,4)); returns=[]
    for _ in range(episodes):
        idx=int(rng.integers(8)); total=0.
        for step in range(4):
            state=(bool(idx&4),bool(idx&2),bool(idx&1)); allowed=allowed_actions(state)
            action=int(rng.choice(allowed)) if rng.random()<.15 else max(allowed,key=lambda a:q[idx,a])
            # Resolve missing information / evidence; terminate with explanation or review.
            next_idx=(idx&3) if action==0 else (idx|2) if action==1 else idx
            done=action in [2,3]
            reward=2.0 if done and (action==3)==state[2] else -.2
            if action==0 and state[0]: reward=.3
            if action==1 and not state[1]: reward=.3
            nxt=(bool(next_idx&4),bool(next_idx&2),bool(next_idx&1))
            target=reward if done else reward+.9*max(q[next_idx,a] for a in allowed_actions(nxt))
            q[idx,action]+=.2*(target-q[idx,action]); total+=reward; idx=next_idx
            if done: break
        returns.append(total)
    return {'q_table':q.tolist(),'actions':ACTIONS,'seed':seed,'episodes':episodes,
            'environment':'synthetic workflow; no clinical outcomes',
            'mean_last_100_return':float(np.mean(returns[-100:])),
            'reward_definition':'information +0.3, step -0.2, suitable terminal workflow +2',
            'returns':returns}


class WorkflowPolicy:
    def __init__(self):
        self.artifact=json.loads((ROOT/'artifacts/workflow_q_policy.json').read_text(encoding='utf-8'))

    def recommend(self, missing=False, evidence=False, review=False):
        state=(missing,evidence,review); idx=int(missing)*4+int(evidence)*2+int(review)
        allowed=allowed_actions(state); q=self.artifact['q_table'][idx]
        action=max(allowed,key=lambda a:q[a])
        return {'state':idx,'action':ACTIONS[action],'allowed_actions':[ACTIONS[a] for a in allowed],
                'q_value':q[action], 'scope':'Educational workflow only; not treatment'}
