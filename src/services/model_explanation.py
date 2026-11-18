"""Local explanation of model perturbations."""
FEATURE_LABELS = {
    'age': 'Tuổi',
    'bmi': 'BMI',
    'hbA1c_level': 'HbA1c',
    'blood_glucose_level': 'Đường huyết',
    'hypertension': 'Tăng huyết áp',
    'heart_disease': 'Bệnh tim',
    'smoking_history': 'Tiền sử hút thuốc',
    'gender': 'Giới tính',
}

def model_factor_explanations(prediction, limit=4):
    """Describe one-at-a-time baseline perturbations; never claim causality."""
    factors=[]
    for item in (prediction or {}).get('feature_impacts',[])[:limit]:
        impact=float(item['impact'])
        direction='cao hơn' if impact > 0 else 'thấp hơn' if impact < 0 else 'không đổi'
        points=abs(impact)*100
        label=FEATURE_LABELS.get(item['feature'],item['feature'])
        factors.append({
            'feature':item['feature'], 'label':label,
            'value':str(item['value']), 'baseline':str(item['baseline']),
            'impact':impact, 'impact_percentage_points':round(points,2),
            'direction':direction,
            'text':(
                f"{label} = {item['value']} (giá trị tham chiếu {item['baseline']}): "
                f"score của mô hình {direction} khoảng {points:.1f} điểm phần trăm."
            ),
        })
    return factors
