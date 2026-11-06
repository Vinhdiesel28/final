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
sys.path.insert(0,str(ROOT/"tools/baseline_pre_policy"))
from before_agent_system import MultiAgent as BeforeMultiAgent

# Rubrics are fixed before execution, based on corpus contents. They never enter agents.
CASES = [
 {'id':'a1c_fasting','question':'A1C có yêu cầu nhịn ăn trước lấy máu không?','sources':['ndep_a1c_method_001'],'phrases':['không yêu cầu nhịn ăn']},
 {'id':'symptoms','question':'Vì sao tăng glucose có thể gây tiểu nhiều và khát nhiều?','sources':['dia_hyperglycemia_symptoms_001'],'phrases':['tiểu nhiều','khát nhiều']},
 {'id':'activity','question':'Vận động đều đặn giúp cải thiện độ nhạy insulin thế nào?','sources':['ndep_activity_effect_001'],'phrases':['cải thiện độ nhạy insulin']},
 {'id':'risk_conditions','question':'Những yếu tố nguy cơ bổ sung nào gồm tăng huyết áp và ít hoạt động thể lực?','sources':['ndep_risk_conditions_001'],'phrases':['tăng huyết áp','ít hoạt động thể lực']},
 {'id':'complications','question':'Biến chứng vi mạch liên quan tới mắt thận và thần kinh là gì?','sources':['dia_complications_001'],'phrases':['mắt','thận','thần kinh']},
 {'id':'asymptomatic','question':'Type 2 có thể không nhận thấy triệu chứng không?','sources':['dia_type2_asymptomatic_001'],'phrases':['không nhận thấy triệu chứng']},
 {'id':'unknown_gene','question':'Biến thể rs7903146 có hệ số nguy cơ chính xác là mấy?','sources':[],'phrases':[]},
 {'id':'unknown_trial','question':'Thử nghiệm ZXQ2026 có kết quả cuối cùng thế nào?','sources':[],'phrases':[]},
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
    required = {key for case in CASES for key in case['sources']} | {'idf2025_masld_definition_001'}
    missing = required - set(services.knowledge.by_id)
    if missing:
        raise RuntimeError('Current corpus rubric requires these missing IDs: ' + ', '.join(sorted(missing)))
    runners = {'single': SingleAgent(services), 'before': BeforeMultiAgent(services), 'multi': MultiAgent(services)}
    original = services.knowledge.answer
    rows = []
    # Warm up both implementations before timing; initialization excluded.
    for runner in runners.values():
        runner.run(CASES[0]['question'])
    for case in CASES:
        for fault in FAULTS if case['sources'] else ['none']:
            for repeat in range(repeats):
                order = ['single', 'before', 'multi'] if repeat % 2 == 0 else ['multi', 'before', 'single']
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
                                doc = services.knowledge.by_id['idf2025_masld_definition_001']
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
                          'backend': 'json', 'documents':len(services.knowledge.documents), 'graph_sha256':hashlib.sha256((ROOT/'knowledge/graph.json').read_bytes()).hexdigest(), 'warmup': True, 'alternating_order': True,
                          'corpus_sha256': hashlib.sha256((ROOT/'knowledge/corpus.json').read_bytes()).hexdigest(),
                          'limitations': [
                              'Small development rubric for the new 44-document corpus; source summaries not independently clinically verified. Before/after both use this same new corpus.',
                              'Injected faults are controlled robustness scenarios, not natural error frequencies.',
                              'Single is one pass; multi has up to two repair rounds. Tool budgets differ.',
                              'Repeated runs measure latency, not additional independent examples.',
                              'Verbatim source support and lexical relevance are not semantic entailment.',
                              'No claim that multiple agents outperform an equally budgeted iterative single agent.']},
              'summary': summary, 'runs': rows}
    destination = ROOT/'results/current_corpus_benchmark.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    import csv
    with (ROOT/'results/current_corpus_benchmark.csv').open('w', encoding='utf-8', newline='') as stream:
        fields = [k for k in rows[0] if k not in ('result', 'retrieval_queries')]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error('Use at least two repetitions for alternating execution order.')
    run(args.repeats)
