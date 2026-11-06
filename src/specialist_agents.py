"""Executable specialist handlers; explicit rules, not autonomous LLM agents."""
import re
from itertools import combinations
from knowledge_service import normalize
from evidence_review import sentences
from review_policy import ReviewPolicy


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

FEATURE_QUERY_TERMS = {
    'age': 'tuổi nguy cơ type 2',
    'bmi': 'BMI thừa cân nguy cơ type 2',
    'hbA1c_level': 'A1C HbA1c xét nghiệm giới hạn',
    'blood_glucose_level': 'glucose đường huyết xét nghiệm',
    'hypertension': 'tăng huyết áp nguy cơ type 2',
    'heart_disease': 'bệnh tim biến chứng tim mạch',
    'smoking_history': 'hút thuốc nguy cơ type 2',
    'gender': 'giới tính nguy cơ type 2',
}


def evidence_query(question, prediction, limit=3):
    """Expand retrieval with the strongest model features, without changing score."""
    terms=[]
    for item in (prediction or {}).get('feature_impacts',[])[:limit]:
        term=FEATURE_QUERY_TERMS.get(item.get('feature'))
        if term and term not in terms: terms.append(term)
    return ' '.join([question or 'yếu tố nguy cơ type 2', *terms]).strip()


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


def source_conflicts(knowledge, by_id):
    """Conservative exact-template conflicts: same sentence except number/negation.

    Does not detect arbitrary semantic contradictions, different contexts or units.
    Inspect authenticated cited documents, not merely the selected answer.
    """
    statements=[]
    for citation in knowledge.get('citations',[]):
        doc=by_id.get(citation.get('id'))
        if not doc or doc['url']!=citation.get('url'): continue
        for sentence in sentences(doc['text']):
            normalized=normalize(sentence)
            numbers=tuple(re.findall(r'\b\d+\b',normalized))
            skeleton=re.sub(r'\b\d+\b','NUMBER',normalized)
            negative=bool(re.search(r'\bkhong\b',normalized))
            polarity_key=' '.join(re.sub(r'\bkhong\b','',normalized).split())
            statements.append((doc['id'],sentence,skeleton,numbers,polarity_key,negative))
    found=[]
    for a,b in combinations(statements,2):
        if a[0]==b[0]: continue
        numeric=a[2]==b[2] and a[3]!=b[3] and bool(a[3]) and bool(b[3])
        polarity=a[4]==b[4] and a[5]!=b[5]
        if numeric or polarity:
            item={'type':'numeric_conflict' if numeric else 'polarity_conflict',
                  'source_ids':[a[0],b[0]],'statements':[a[1],b[1]]}
            if item not in found: found.append(item)
    return found


class Specialists:
    def __init__(self, services):
        self.s=services
        if not hasattr(services,'review_policy'): services.review_policy=ReviewPolicy()
        self.policy=services.review_policy

    def clarify(self,p):
        errors=p['errors']
        fields=list(dict.fromkeys(e['field'] for e in errors))
        return {'status':'needs_clarification','requested_fields':fields,
                'answer':'Cần bổ sung hoặc xác nhận các trường: '+', '.join(fields)+'. Hệ thống chưa đưa ra dự đoán.',
                'decision':{'status':'needs_clarification','final_label':None,'review_required':False,'reason_codes':['incomplete_or_invalid_profile']}}

    def critic(self,p):
        prediction=p.get('prediction'); knowledge=p.get('knowledge') or {}; decision=p['decision']
        reasons=[]; assessment=self.policy.assess(prediction) if prediction else None
        if assessment:
            if assessment['disagreement']: reasons.append('model_disagreement')
            if assessment['human_review_required']: reasons.append('validation_selected_uncertainty')
        if p.get('conflicts'): reasons.append('source_conflict')
        if not knowledge.get('citations'): reasons.append('missing_evidence')
        needs_human=bool(p.get('conflicts') or (assessment and assessment['human_review_required']))
        needs_hold=needs_human or 'missing_evidence' in reasons
        handled=set(decision.get('reason_codes',[]))
        resolved=set(reasons)<=handled and (not needs_hold or (decision.get('review_required') and decision.get('final_label') is None))
        passed=not reasons or resolved
        return {'passed':passed,'reason_codes':reasons,'requires_review':needs_hold,
                'human_review_required':needs_human,'assessment':assessment,
                'disagreement':bool(assessment and assessment['disagreement']),
                'challenges':reasons,'conclusion':'Đã xử lý yêu cầu phản biện; bất đồng còn lại được công khai.' if passed else 'Cần cập nhật kết luận theo phản biện.'}

    def review(self,p):
        critique=p['critique']; prediction=p.get('prediction'); reasons=critique['reason_codes']
        hold=critique['requires_review']
        return {'final_label':None if hold else prediction['predicted_class'] if prediction else None,
                'review_required':hold,'reason_codes':list(reasons),
                'status':('human_review' if prediction or p.get('conflicts') else 'insufficient_evidence') if hold else 'supported_with_limitations' if prediction else 'supported',
                'source_conflicts':p.get('conflicts',[]), 'assessment':critique.get('assessment'),
                'resolution':'unresolved_referred' if hold else 'disagreement_acknowledged_primary_retained',
                'probability':(prediction or {}).get('probability')}

    def explain(self,p):
        return compose_explanation(p)

    def verify(self,p):
        decision=p['decision']; answer=p['answer']; prediction=p.get('prediction'); issues=[]
        if decision.get('review_required'):
            if decision.get('final_label') is not None: issues.append('unresolved_final_label')
            if 'Cần xem xét thêm' not in answer: issues.append('missing_review_notice')
        if p.get('conflicts'):
            if 'mâu thuẫn' not in answer: issues.append('conflict_not_disclosed')
            if not decision.get('review_required'): issues.append('conflict_not_referred')
        if prediction:
            expected=f"{prediction['probability']*100:.1f}%"
            if expected not in answer: issues.append('score_not_preserved')
            if 'không phải chẩn đoán' not in answer: issues.append('missing_scope_notice')
            ref=prediction.get('second_opinion',{})
            assessment=self.policy.assess(prediction)
            if assessment['human_review_required'] and not decision.get('review_required'):
                issues.append('validation_review_rule_not_respected')
            if assessment['disagreement'] and 'model_disagreement' not in decision.get('reason_codes',[]):
                issues.append('model_disagreement_not_acknowledged')
            expected_explanation=compose_explanation(p)
            supplied=p.get('explanation') or {}
            if supplied.get('model_factors') != expected_explanation.get('model_factors'):
                issues.append('feature_impacts_not_preserved')
            if supplied.get('sections') != expected_explanation.get('sections'):
                issues.append('explanation_sections_not_preserved')
        if p.get('clarification') and prediction: issues.append('prediction_before_clarification')
        if not p.get('blocked') and answer != compose_explanation(p)['answer']:
            issues.append('explanation_changed_outside_verified_composition')
        return {'passed':not issues,'issues':issues,'scope':'Deterministic consistency and disclosure checks'}


def compose_explanation(p):
    prediction=p.get('prediction'); decision=p['decision']; knowledge=p.get('knowledge') or {}
    if p.get('clarification'):
        answer=p['clarification']['answer']
        return {'answer':answer,'sections':[{'id':'clarification','title':'Thông tin cần bổ sung','text':answer}],
                'model_factors':[],'method':'deterministic_template_v2'}
    if p.get('statistics'):
        x=p['statistics']; answer=f"Trong {x['group']}: {x['positive']:,}/{x['count']:,}, tương đương {x['rate']:.2f}%."
        return {'answer':answer,'sections':[{'id':'statistics','title':'Kết quả thống kê','text':answer}],
                'model_factors':[],'method':'deterministic_template_v2'}
    parts=[]; sections=[]; factors=[]
    if prediction:
        score=(f"Model đưa ra score {prediction['probability']*100:.1f}% với ngưỡng "
               f"{prediction['threshold']*100:.1f}%. Đây là score của mô hình, không phải chẩn đoán "
               "hay xác suất lâm sàng đã được kiểm chứng cho một cá nhân.")
        parts.append(score); sections.append({'id':'assessment','title':'Đánh giá hồ sơ','text':score})
        factors=model_factor_explanations(prediction)
        if factors:
            factor_text=("Các thay đổi dưới đây là độ nhạy của model khi lần lượt thay một đặc trưng "
                         "bằng giá trị tham chiếu và giữ các đặc trưng khác không đổi; chúng không chứng minh quan hệ nhân quả. "
                         +' '.join(x['text'] for x in factors))
            parts.append(factor_text)
            sections.append({'id':'model_factors','title':'Vì sao model đưa ra score này?','text':factor_text})
    if 'source_conflict' in decision.get('reason_codes',[]):
        ids=sorted({key for c in decision['source_conflicts'] for key in c['source_ids']})
        medical='Các nguồn đang mâu thuẫn: '+', '.join(ids)+'. Chưa đủ cơ sở để chọn một kết luận; cần kiểm tra lại nguồn.'
    else:
        medical=knowledge.get('answer','')
    if medical:
        parts.append(medical); sections.append({'id':'medical_evidence','title':'Thông tin y khoa liên quan','text':medical,
                                                'citation_ids':[c.get('id') for c in knowledge.get('citations',[])]})
    confidence=[]
    if 'model_disagreement' in decision.get('reason_codes',[]):
        confidence.append('Hai mô hình bất đồng nhãn; không ép đồng thuận. ' + ('Giữ nhãn mô hình chính theo chính sách validation, chưa có chỉ định chuyển người xem xét.' if not decision.get('review_required') else 'Bất đồng cần xem xét theo chính sách validation.'))
    elif prediction:
        peer=prediction.get('second_opinion',{})
        if peer:
            confidence.append(f"Model đối chiếu cho score {peer['probability']*100:.1f}% với ngưỡng {peer['threshold']*100:.1f}%.")
    if decision.get('review_required'):
        confidence.append('Cần xem xét thêm; chưa kết luận có/không tiểu đường.')
    if confidence:
        confidence_text=' '.join(confidence); parts.append(confidence_text)
        sections.append({'id':'confidence','title':'Độ tin cậy và giới hạn','text':confidence_text})
    return {'answer':' '.join(parts).strip(),'sections':sections,'model_factors':factors,
            'method':'deterministic_template_v2'}
