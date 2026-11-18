"""Auditable query aliases; never supplies medical answer text."""
import json,re
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def concepts():
    return json.loads((Path(__file__).resolve().parents[2]/'knowledge/retrieval_terminology.json').read_text(encoding='utf-8'))['concepts']

def canonical_text(text):
    from services.knowledge_service import normalize
    text=normalize(text)
    replacements=sorted([(normalize(alias),c['canonical']) for c in concepts() for alias in c['aliases']],key=lambda p:-len(p[0]))
    for alias,canonical in replacements:
        text=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',canonical,text)
    return text

def search_query(text):
    canonical=set(canonical_text(text).split())
    additions=[alias for c in concepts() if c['canonical'] in canonical for alias in c['aliases'][:2]]
    return text+' '+' '.join(additions) if additions else text

def search_terms(text):
    from services.knowledge_service import tokens
    return tokens(canonical_text(text))
