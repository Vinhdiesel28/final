

FEATURES = ('gender', 'age', 'hypertension', 'heart_disease', 'smoking_history',
            'bmi', 'hbA1c_level', 'blood_glucose_level')


def validate(p, *, model):
    """Raw profile -> validated feature mapping, or field-level errors."""
    errors = model.validate(p['profile'])
    names = getattr(model, 'metadata', {}).get('features', FEATURES)
    features = {name: p['profile'][name] for name in names} if not errors else None
    return {'status': 'validation_failed' if errors else 'ok',
            'validated_features': features, 'errors': errors}

def clarify(p):
    questions=p['questions'][:3]
    return {'status':p.get('status','needs_clarification'),'task':'conversation','questions':[{'field':f'context_{i}','text':q} for i,q in enumerate(questions)],
            'requested_fields':['additional_information'],'answer':' '.join(questions),
            'summary':'Yêu cầu bổ sung thông tin thiết yếu'}

def handle(payload, *, model):
    if payload.get('action') == 'clarify':
        return clarify(payload)
    return validate(payload, model=model)
