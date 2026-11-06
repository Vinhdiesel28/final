"""Validation-selected referral rule; does not modify prediction scores/thresholds."""
import json,hashlib
from pathlib import Path
class ReviewPolicy:
 def __init__(self):
  self.artifact=json.loads((Path(__file__).resolve().parents[1]/'artifacts/review_policy.json').read_text(encoding='utf-8'))
  root=Path(__file__).resolve().parents[1]
  for name,key in [('pytorch_mlp.pt','model_sha256'),('diabetes_model.joblib','reference_sha256')]:
   if hashlib.sha256((root/'artifacts'/name).read_bytes()).hexdigest()!=self.artifact[key]:
    raise RuntimeError('Review policy no longer matches model checkpoint; rerun validation policy selection.')
 def assess(self,prediction):
  peer=prediction.get('second_opinion',prediction)
  gap=abs(prediction['probability']-peer['probability'])
  margin=abs(prediction['probability']-prediction['threshold'])
  mismatch=prediction['predicted_class']!=peer['predicted_class']
  rule=self.artifact['selected']; width=rule['margin_width']; minimum=rule['minimum_gap']
  needs=(mismatch and gap>=minimum) or (margin<=width and gap>=minimum/2)
  return {'disagreement':mismatch,'probability_gap':gap,'primary_margin':margin,
          'human_review_required':bool(needs),'policy_version':self.artifact['version'],
          'margin_width':width,'minimum_gap':minimum,
          'reason':'validation_selected_uncertainty' if needs else 'retain_primary_with_disagreement_disclosed' if mismatch else 'no_review_trigger'}
