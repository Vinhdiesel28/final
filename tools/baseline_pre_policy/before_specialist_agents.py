"""Executable specialist handlers; explicit rules, not autonomous LLM agents."""
import re
from itertools import combinations
from knowledge_service import normalize
from before_evidence_review import sentences


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
    def __init__(self, services): self.s=services

    def clarify(self,p):
        errors=p['errors']
        fields=list(dict.fromkeys(e['field'] for e in errors))
        return {'status':'needs_clarification','requested_fields':fields,
                'answer':'Cần bổ sung hoặc xác nhận các trường: '+', '.join(fields)+'. Hệ thống chưa đưa ra dự đoán.',
                'decision':{'status':'needs_clarification','final_label':None,'review_required':False,'reason_codes':['incomplete_or_invalid_profile']}}

    def critic(self,p):
        prediction=p.get('prediction'); knowledge=p.get('knowledge') or {}; decision=p['decision']
        reasons=[]
        model_review=self.s.review(prediction,knowledge) if prediction else None
        if model_review:
            if model_review['disagreement']: reasons.append('model_disagreement')
            if abs(prediction['probability']-prediction['threshold'])<.05: reasons.append('near_threshold')
        if p.get('conflicts'): reasons.append('source_conflict')
        if not knowledge.get('citations'): reasons.append('missing_evidence')
        obligations=set(reasons)
        handled=set(decision.get('reason_codes',[]))
        passed=not obligations or (decision.get('review_required') and decision.get('final_label') is None and obligations<=handled)
        return {'passed':passed,'reason_codes':reasons,'requires_review':bool(reasons),
                'disagreement':bool(model_review and model_review['disagreement']),
                'challenges':reasons,'conclusion':'Đã chuyển các vấn đề chưa giải quyết sang xem xét thêm.' if passed and reasons else 'Cần cập nhật kết luận.' if reasons else 'Không phát hiện bất đồng theo các quy tắc hiện có.'}

    def review(self,p):
        # A second opinion is evidence of uncertainty, not permission to invent a score.
        return {'final_label':None,'review_required':True,
                'reason_codes':list(p['critique']['reason_codes']),
                'status':'human_review' if p.get('prediction') or p.get('conflicts') else 'insufficient_evidence',
                'source_conflicts':p.get('conflicts',[]),
                'resolution':'unresolved_referred', 'probability':(p.get('prediction') or {}).get('probability')}

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
            if prediction['predicted_class']!=ref.get('predicted_class',prediction['predicted_class']) and not decision.get('review_required'):
                issues.append('model_disagreement_not_referred')
        if p.get('clarification') and prediction: issues.append('prediction_before_clarification')
        if not p.get('blocked') and answer != compose_explanation(p)['answer']:
            issues.append('explanation_changed_outside_verified_composition')
        return {'passed':not issues,'issues':issues,'scope':'Deterministic consistency and disclosure checks'}


def compose_explanation(p):
    prediction=p.get('prediction'); decision=p['decision']; knowledge=p.get('knowledge') or {}
    if p.get('clarification'): return {'answer':p['clarification']['answer']}
    if p.get('statistics'):
        x=p['statistics']; return {'answer':f"Trong {x['group']}: {x['positive']:,}/{x['count']:,}, tương đương {x['rate']:.2f}%."}
    parts=[]
    if prediction:
        parts.append(f"Risk score {prediction['probability']*100:.1f}%. Đây là ước lượng học thuật, không phải chẩn đoán.")
    if 'source_conflict' in decision.get('reason_codes',[]):
        ids=sorted({key for c in decision['source_conflicts'] for key in c['source_ids']})
        parts.append('Các nguồn đang mâu thuẫn: '+', '.join(ids)+'. Chưa đủ cơ sở để chọn một kết luận; cần kiểm tra lại nguồn.')
    else: parts.append(knowledge.get('answer',''))
    if decision.get('review_required'): parts.append('Cần xem xét thêm; chưa kết luận có/không tiểu đường.')
    return {'answer':' '.join(parts).strip()}
