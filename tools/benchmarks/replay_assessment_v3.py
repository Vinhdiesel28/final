"""Replay the six original assessment cases offline using saved public evidence."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from time import perf_counter
import sys

from benchmark_conversation_v3 import ROOT, MultiAgent, grade, heldout, runtime_fingerprint, summarize
from services.model_service import DiabetesModelService
from legacy.workflow_policy import WorkflowPolicy


class ReplayLLM:
    def complete(self, task, system, payload, output_type, max_tokens):
        if task == 'response_critic':
            result = dict(action='accept', answers_question=True, all_claims_supported=True,
                          reasons=[], revised_query='', followup_questions=[])
        elif task == 'grounded_draft':
            evidence = payload['evidence'][0]
            spans = evidence.get('quote_spans', {})
            quote = next(iter(spans), 'This deliberately paraphrased source quotation is not in the evidence.')
            result = dict(claims=[dict(text='Đây là đoạn nguồn tham khảo dùng để kiểm tra trích dẫn.',
                                       evidence_id=evidence['evidence_id'], quote=quote)],
                          followup_questions=[], evidence_sufficient=True, missing_information='')
        else:
            raise AssertionError(task)
        return output_type.model_validate(result), {'task': task, 'offline_replay': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    saved = json.loads((ROOT/'results/benchmark_v3.json').read_text(encoding='utf-8'))
    cases = {c['id']:c for c in json.loads((ROOT/'benchmarks/v3_cases.json').read_text(encoding='utf-8'))['live']}
    services = SimpleNamespace(model=DiabetesModelService(), policy=WorkflowPolicy(), agent_llm=ReplayLLM())
    test, truth = heldout(services)
    rows = []
    for trial in saved['trials']:
        if trial['kind'] != 'assessment':
            continue
        case = cases[trial['case_id']]
        i = trial['dataset_row']
        profile = test.loc[i].to_dict()
        assert int(truth.loc[i]) == trial['ground_truth_label'] and profile == trial['profile']
        evidence = trial['response']['knowledge']['evidence']
        documents = [dict(e['source'], id=e['evidence_id'], text=e['text']) for e in evidence]
        services.knowledge = SimpleNamespace(backend='offline_evidence_replay', vector_metadata={},
                                             retrieve=lambda q, n: documents[:n])
        start = perf_counter()
        response = MultiAgent(services).run(case['question'], profile, task='assessment')
        elapsed = (perf_counter()-start)*1000
        scored = grade(case, response, {d['id']:d for d in documents}, services.model.predict(profile))
        rows.append(dict(case_id=case['id'], kind='assessment', repeat=trial['repeat'],
                         elapsed_ms=elapsed, response={k:response[k] for k in ('status','traces','decision')}, grade=scored))
    assert len(rows) == 6
    result = dict(protocol=dict(scope='Offline replay, real checkpoint, historical public evidence, scripted LLM/Critic; not live Groq or semantic validation',runtime_hash=runtime_fingerprint()),trials=rows,summary=summarize(rows))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print([(r['case_id'],r['grade']['passed'],r['grade']['checks']['rules_respected']) for r in rows])


if __name__ == '__main__':
    main()
