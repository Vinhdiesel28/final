"""Validated features + prediction -> consistency rules and referral flags.

Rules do not diagnose disease or overwrite the checkpoint score/threshold.
"""
from agents.data_agent import FEATURES


def rules(p, *, review_policy):
    prediction = p.get('prediction')
    features = p.get('features') or {}
    assessment = review_policy.assess(prediction) if prediction else None
    results = []
    if prediction:
        names = prediction.get('feature_names', FEATURES)
        missing = [name for name in names if name not in features]
        results.append({'rule': 'validated_features_present', 'passed': not missing,
                        'missing_fields': missing})
        mismatched = []
        for impact in prediction.get('feature_impacts', []):
            name = impact['feature']
            if name not in features:
                mismatched.append(name)
                continue
            try:
                equal = float(features[name]) == float(impact['value'])
            except (TypeError, ValueError):
                equal = str(features[name]) == str(impact['value'])
            if not equal: mismatched.append(name)
        results.append({'rule': 'prediction_feature_consistency', 'passed': not mismatched,
                        'mismatched_fields': mismatched,
                        'scope': 'Only features exposed by feature_impacts can be cross-checked.'})
    failed = any(not row['passed'] for row in results)
    return {'status': 'ok', 'assessment': assessment, 'rule_results': results,
            'review_required': bool(failed or (assessment and assessment['human_review_required'])),
            'reason_codes': ([row['rule'] for row in results if not row['passed']] +
                             ([assessment['reason']] if assessment and assessment.get('reason') else [])),
            'summary': 'Kiểm tra tính nhất quán hồ sơ, bất đồng model và quy tắc chuyển review'}
