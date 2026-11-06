"""Paired evidence benchmark: fixed corpus-grounded rubric, explicit injected faults.

Run: python tools/benchmark_evidence_repair.py --repeats 5
Only two systems: one-pass SingleAgent and bounded-repair MultiAgent.
These measure workflows with unequal tool budgets, not inherent multi-agent superiority.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ['KNOWLEDGE_BACKEND'] = 'json'
sys.path.insert(0, str(ROOT / 'src'))
from agent_system import Services, SingleAgent, MultiAgent
from knowledge_service import normalize

# Rubrics are fixed before execution, based on corpus contents. They never enter agents.
CASES = [
    {'id': 'a1c', 'question': 'A1C phản ánh glucose trong thời gian nào?',
     'sources': ['niddk_a1c', 'niddk_tests'], 'phrases': ['ba tháng']},
    {'id': 'symptoms', 'question': 'Dấu hiệu khát nhiều và tiểu nhiều là gì?',
     'sources': ['cdc_symptoms'], 'phrases': ['khát nhiều', 'tiểu nhiều']},
    {'id': 'prevention', 'question': 'Phòng ngừa bằng hoạt động thể lực và chế độ ăn thế nào?',
     'sources': ['who_prevention'], 'phrases': ['Chế độ ăn lành mạnh', 'hoạt động thể lực']},
    {'id': 'risk', 'question': 'Thừa cân và tiền sử gia đình liên quan nguy cơ thế nào?',
     'sources': ['cdc_risk_factors'], 'phrases': ['thừa cân', 'tiền sử gia đình']},
    {'id': 'complications', 'question': 'Tăng glucose kéo dài gây tổn thương cơ quan nào?',
     'sources': ['who_overview'], 'phrases': ['tim', 'thận', 'thần kinh']},
    {'id': 'alias', 'question': 'HbA1c phản ánh đường huyết trong thời gian nào?',
     'sources': ['niddk_a1c', 'niddk_tests'], 'phrases': ['ba tháng']},
    {'id': 'unknown_gene', 'question': 'Biến thể rs7903146 có hệ số nguy cơ chính xác là mấy?',
     'sources': [], 'phrases': []},
    {'id': 'unknown_trial', 'question': 'Thử nghiệm ZXQ2026 có kết quả cuối cùng thế nào?',
     'sources': [], 'phrases': []},
]
FAULTS = ['none', 'empty_first', 'wrong_source_first', 'unsupported_claim_first',
          'forged_url_first', 'empty_persistent']


def grade(result, case, documents, must_abstain=False):
    """Independent rubric: required facts + attributed verbatim corpus sentences.

    No reuse of the runtime Critic. This is an extractive corpus check, not a
    medical correctness or general semantic entailment assessment.
    """
    knowledge = result.get('knowledge') or {}
    citations = knowledge.get('citations', [])
    answer = normalize(result['answer'])
    abstained = result['status'] == 'insufficient_evidence' and not citations
    source_ids = {c.get('id') for c in citations}
    valid = all(c.get('id') in documents and c.get('url') == documents[c['id']]['url']
                for c in citations)
    # All output sentences must occur verbatim in at least one authenticated source.
    import re
    claims = [normalize(s) for s in re.split(r'(?<=[.!?])\s+', result['answer']) if s.strip()]
    corpus_sentences = {normalize(s) for c in citations if c.get('id') in documents
                        and c.get('url') == documents[c['id']]['url']
                        for s in re.split(r'(?<=[.!?])\s+', documents[c['id']]['text'])}
    grounded = bool(claims) and all(c in corpus_sentences for c in claims)
    facts = all(normalize(p) in answer for p in case['phrases'])
    source_hit = bool(source_ids & set(case['sources']))
    expected_abstention = must_abstain or not case['sources']
    correct = abstained if expected_abstention else (facts and source_hit and valid and grounded and not abstained)
    return {'correct': bool(correct), 'abstained': abstained, 'expected_abstention': expected_abstention,
            'required_facts_present': facts, 'expected_source_present': source_hit,
            'citation_integrity': valid, 'all_claims_grounded': grounded}


def run(repeats):
    services = Services()
    required = {key for case in CASES for key in case['sources']} | {'project_dataset'}
    missing = required - set(services.knowledge.by_id)
    if missing:
        raise RuntimeError('Legacy evidence rubric does not match current corpus; retain historical results, do not reinterpret them. Missing IDs: ' + ', '.join(sorted(missing)))
    runners = {'single': SingleAgent(services), 'multi': MultiAgent(services)}
    original = services.knowledge.answer
    rows = []
    # Warm up both implementations before timing; initialization excluded.
    for runner in runners.values():
        runner.run(CASES[0]['question'])
    for case in CASES:
        for fault in FAULTS if case['sources'] else ['none']:
            for repeat in range(repeats):
                order = ['single', 'multi'] if repeat % 2 == 0 else ['multi', 'single']
                for name in order:
                    calls = []
                    def injected(question):
                        calls.append(question)
                        if fault == 'empty_persistent' or (len(calls) == 1 and fault == 'empty_first'):
                            return {'answer': 'Không có bằng chứng.', 'citations': [], 'paths': [],
                                    'status': 'insufficient_evidence'}
                        response = copy.deepcopy(original(question))
                        if len(calls) == 1:
                            if fault == 'wrong_source_first':
                                doc = services.knowledge.by_id['project_dataset']
                                response = {'answer': doc['text'], 'citations': [dict(doc, score=1.0)],
                                            'paths': [], 'status': 'supported'}
                            elif fault == 'unsupported_claim_first':
                                response['answer'] += ' Mã kiểm chứng của kết luận là ZXQ999.'
                            elif fault == 'forged_url_first':
                                for citation in response['citations']:
                                    citation['url'] = 'https://invalid.example/fabricated'
                        return response
                    services.knowledge.answer = injected
                    try:
                        result = runners[name].run(case['question'])
                    finally:
                        services.knowledge.answer = original
                    rows.append({'case_id': case['id'], 'fault': fault, 'repeat': repeat, 'system': name,
                                 **grade(result, case, services.knowledge.by_id, fault == 'empty_persistent'),
                                 'latency_ms': result['total_duration_ms'], 'retrieval_calls': len(calls),
                                 'retrieval_queries': calls, 'result': result})
    summary = {}
    for fault in FAULTS:
        group = [r for r in rows if r['fault'] == fault]
        summary[fault] = {}
        for name in runners:
            part = [r for r in group if r['system'] == name]
            times = sorted(r['latency_ms'] for r in part)
            unique = [r for r in part if r['repeat'] == 0]
            summary[fault][name] = {'runs': len(part), 'correct': sum(r['correct'] for r in part),
                                   'unique_cases': len(unique), 'unique_correct': sum(r['correct'] for r in unique),
                                   'accuracy': statistics.mean(r['correct'] for r in part),
                                   'latency_median_ms': statistics.median(times),
                                   'latency_p95_ms': times[min(len(times)-1, int(.95*len(times)))],
                                   'mean_retrieval_calls': statistics.mean(r['retrieval_calls'] for r in part)}
        pairs = {(r['case_id'], r['repeat']): r for r in group if r['system'] == 'single'}
        multis = [r for r in group if r['system'] == 'multi']
        summary[fault]['paired'] = {
            'single_wrong_multi_correct': sum(not pairs[(r['case_id'], r['repeat'])]['correct'] and r['correct'] for r in multis),
            'single_correct_multi_wrong': sum(pairs[(r['case_id'], r['repeat'])]['correct'] and not r['correct'] for r in multis)}
    result = {'protocol': {'repeats': repeats, 'unique_questions': len(CASES), 'cases': CASES,
                          'backend': 'json', 'warmup': True, 'alternating_order': True,
                          'corpus_sha256': hashlib.sha256((ROOT/'knowledge/corpus.json').read_bytes()).hexdigest(),
                          'limitations': [
                              'Small hand-authored corpus-grounded suite; no clinical validation.',
                              'Injected faults are controlled robustness scenarios, not natural error frequencies.',
                              'Single is one pass; multi has up to two repair rounds. Tool budgets differ.',
                              'Repeated runs measure latency, not additional independent examples.',
                              'Verbatim source support and lexical relevance are not semantic entailment.',
                              'No claim that multiple agents outperform an equally budgeted iterative single agent.']},
              'summary': summary, 'runs': rows}
    destination = ROOT/'results/evidence_repair_benchmark.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    import csv
    with (ROOT/'results/evidence_repair_benchmark.csv').open('w', encoding='utf-8', newline='') as stream:
        fields = [k for k in rows[0] if k not in ('result', 'retrieval_queries')]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error('Use at least two repetitions for alternating execution order.')
    run(args.repeats)
