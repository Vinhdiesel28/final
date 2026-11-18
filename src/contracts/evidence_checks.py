import re

from services.knowledge_service import normalize
from services.llm_explanation import validate_generation, number_values

def clearly_english(text):
    # Flag clear English prose without treating technical names as foreign prose.
    words=set(re.findall(r'\b[a-z]+\b', text.lower()))
    vietnamese=set(normalize(text).split())
    if vietnamese & {'la','cua','duoc','trong','khong','nhung','phan','anh','gay','muc','lam','tang'}:
        return False
    return len(words & {'the','is','are','of','and','in','with','can','when','does','that','to','for','by'})>=2


def llm_context(p):
    # Keep full provenance in State/UI, not duplicated in every prompt.
    # Quotes remain exact spans of the original retrieved evidence.
    return {**p,'evidence':[{'evidence_id':e['evidence_id'],'text':e['text'],
        'source':{k:e['source'].get(k) for k in ('title','source_file','page_start','source_type')}} for e in p['evidence']]}


def structural_check(claims, evidence, user_numbers):
    checked=validate_generation({'claims':claims},{'evidence':evidence})
    # User-provided context (e.g. age) is not a fabricated source number.
    # It still goes through semantic review: a user number does NOT
    # justify applying a guideline threshold to that user.
    unknown=set().union(*(number_values(c['text'])-number_values(c['quote'])-user_numbers for c in claims)) if claims else set()
    if 'unsupported_number' in checked['issues'] and not unknown:
        checked['issues'].remove('unsupported_number');checked['passed']=not checked['issues']
    if any(clearly_english(c['text']) for c in claims):
        checked['issues'].append('answer_language_mismatch')
        checked['passed']=False
    checked['user_context_numbers']=sorted(user_numbers)
    return checked
