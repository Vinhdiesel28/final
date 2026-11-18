"""Validated patient features -> unchanged model output and model metadata."""
def predict(p, *, model):
    features = p.get('features', p.get('profile'))
    result = model.predict(features)
    metadata = getattr(model, 'metadata', {})
    return {**result, 'feature_names': list(metadata.get('features', features.keys())),
            'model_version': result.get('model_version'),
            'status': 'ok'}
