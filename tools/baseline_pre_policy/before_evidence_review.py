"""Bounded, extractive evidence repair; not a medical entailment model.

Checks are against the project's curated corpus, not the original web pages.
No benchmark labels or expected document IDs are available to this module.
"""
import re

from knowledge_service import normalize, tokens

ABSTENTION = 'Kho tri thức không có đủ bằng chứng để trả lời câu hỏi này.'
GENERIC = set('benh tieu duong dai thao type diabetes hoi biet hay xin giai thich toi nay nhung nhu nao gi cua trong ve cho khong the va la mot duoc'.split())
ALIASES = {'hba1c': 'a1c', 'duong huyet': 'glucose',
           'trieu chung': 'dau hieu', 'beo phi': 'thua can',
           'van dong': 'hoat dong the luc'}


def rewrite_query(question):
    text = normalize(question)
    for source, target in ALIASES.items():
        text = re.sub(r'\b' + re.escape(source) + r'\b', target, text)
    return text


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def relevant(question, text):
    query = set(tokens(rewrite_query(question))) - GENERIC
    found = query & set(tokens(rewrite_query(text)))
    # Conservative lexical relevance; does not prove semantic entailment.
    return bool(found) and len(found) / max(len(query), 1) >= .25


def inspect(question, knowledge, by_id):
    citations = knowledge.get('citations', [])
    issues, valid = [], []
    for citation in citations:
        doc = by_id.get(citation.get('id'))
        if not doc or citation.get('url') != doc['url']:
            issues.append('invalid_source')
        else:
            valid.append(doc)
    if not valid:
        issues.append('missing_evidence')
    claims = sentences(knowledge.get('answer', ''))
    supported = []
    for claim in claims:
        sources = [d['id'] for d in valid
                   if normalize(claim) in [normalize(s) for s in sentences(d['text'])]]
        if not sources:
            issues.append('unsupported_claim')
        elif not relevant(question, claim):
            issues.append('irrelevant_claim')
        else:
            supported.append({'text': claim, 'source_ids': sources})
    if not claims:
        issues.append('empty_answer')
    return {'passed': not issues, 'issues': sorted(set(issues)),
            'supported_claims': supported,
            'scope': 'Exact corpus sentence support + lexical relevance, not clinical verification'}


def compose(question, knowledge, by_id):
    """Rebuild from authenticated retrieved sources; never invent a sentence."""
    candidates = []
    query = set(tokens(rewrite_query(question))) - GENERIC
    for citation in knowledge.get('citations', []):
        doc = by_id.get(citation.get('id'))
        if not doc or citation.get('url') != doc['url']:
            continue
        for sentence in sentences(doc['text']):
            if relevant(question, sentence):
                score = len(query & set(tokens(rewrite_query(sentence))))
                candidates.append((score, sentence, doc))
    candidates.sort(key=lambda row: -row[0])
    selected, seen = [], set()
    for _, sentence, doc in candidates:
        if normalize(sentence) not in seen:
            seen.add(normalize(sentence)); selected.append((sentence, doc))
        if len(selected) == 2:
            break
    citations = {d['id']: {'id': d['id'], 'title': d['title'], 'url': d['url'], 'score': 0.0}
                 for _, d in selected}
    return {'answer': ' '.join(s for s, _ in selected) if selected else ABSTENTION,
            'citations': list(citations.values()), 'paths': knowledge.get('paths', []),
            'status': 'supported' if selected else 'insufficient_evidence'}


def repair(question, initial, by_id, bus, max_rounds=2):
    """Critic -> action -> mutated knowledge -> Critic, with a hard bound."""
    current, history = initial, []
    bus.register('EvidenceCriticAgent', lambda p: inspect(question, p['knowledge'], by_id))
    bus.register('EvidenceComposerAgent', lambda p: compose(question, p['knowledge'], by_id))
    review = bus.request('CoordinatorAgent', 'EvidenceCriticAgent', {'knowledge': current})
    for round_number in range(1, max_rounds + 1):
        if review['passed']:
            break
        before, previous_review = current, review
        # First salvage verified sources; if none are useful, obtain different evidence.
        candidate = bus.request('EvidenceCriticAgent', 'EvidenceComposerAgent',
                                {'knowledge': current}, 'CHALLENGE')
        action = 'rewrite_from_verified_sources'
        query = None
        if not candidate['citations']:
            query = rewrite_query(question) if round_number == 1 else ' '.join(
                sorted(set(tokens(rewrite_query(question))) - GENERIC))
            retrieved = bus.request('EvidenceCriticAgent', 'RetrievalAgent',
                                    {'question': query}, 'CHALLENGE')
            # Do not let composition discard conflicting sources before review.
            from before_specialist_agents import source_conflicts
            if source_conflicts(retrieved, by_id):
                review = {'passed': False, 'issues': ['source_conflict'], 'supported_claims': []}
                history.append({'round': round_number, 'action': 'escalate_source_conflict',
                                'before': before, 'after': retrieved, 'state_changed': before != retrieved,
                                'remaining_challenges': ['source_conflict']})
                return retrieved, review, history
            candidate = bus.request('EvidenceCriticAgent', 'EvidenceComposerAgent',
                                    {'knowledge': retrieved}, 'CHALLENGE')
            action = 'rewrite_query_retrieve_and_recompose'
        current = candidate
        review = bus.request('CoordinatorAgent', 'EvidenceCriticAgent', {'knowledge': current})
        history.append({'round': round_number, 'action': action, 'query': query,
                        'before': before, 'after': current,
                        'initial_challenges': previous_review['issues'],
                        'remaining_challenges': review['issues'],
                        'state_changed': before != current})
    if not review['passed']:
        before = current
        current = {'answer': ABSTENTION, 'citations': [], 'paths': [], 'status': 'insufficient_evidence'}
        history.append({'action': 'abstain', 'before': before, 'after': current,
                        'remaining_challenges': review['issues'], 'state_changed': before != current})
    return current, review, history
