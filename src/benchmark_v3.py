"""Independent, bounded rubric grading. Expected answers never enter agents."""
import hashlib,json,math,statistics
from pathlib import Path
from services.knowledge_service import normalize
from services.llm_explanation import number_values,validate_generation
ROOT=Path(__file__).resolve().parents[1]
RUNTIME_FILES=['src/agent_system.py','src/contracts/message_bus.py','src/conversational_agents.py','src/services/agent_llm.py','src/contracts/conversation_contracts.py',
 'src/services/model_service.py','src/services/model_explanation.py','src/services/llm_explanation.py','src/services/torch_model.py','src/services/review_policy.py','src/contracts/evidence_checks.py','src/contracts/message_bus.py',
 'src/services/hybrid_kb.py','src/services/semantic_embedding.py','src/services/qdrant_backend.py','src/services/knowledge_service.py','src/knowledge/retrieval_terms.py','knowledge/retrieval_terminology.json']

def digest_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def runtime_fingerprint():
    agent_files = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT/'src/agents').glob('*.py'))
    return hashlib.sha256(''.join(name+'\n'+(ROOT/name).read_text(encoding='utf-8') for name in [*RUNTIME_FILES, *agent_files]).encode()).hexdigest()

def latency(values):
    if not values:return {'n':0,'median_ms':None,'p95_ms':None,'min_ms':None,'max_ms':None}
    ordered=sorted(values);idx=max(0,math.ceil(.95*len(ordered))-1)
    return {'n':len(values),'median_ms':round(statistics.median(values),2),'p95_ms':round(ordered[idx],2),
            'min_ms':round(min(values),2),'max_ms':round(max(values),2)}

def rate(values):
    values=[bool(v) for v in values];n=len(values);k=sum(values)
    if not n:return {'passed':0,'total':0,'rate':None,'wilson95':None}
    z=1.96;p=k/n;den=1+z*z/n;centre=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {'passed':k,'total':n,'rate':p,'wilson95':[max(0,centre-half),min(1,centre+half)]}

def rank_scores(ids,relevant,k=5):
    selected=ids[:k];relevant=set(relevant);hit=relevant.intersection(selected)
    return {'hit_at_5':bool(hit),'recall_at_5':len(hit)/len(relevant),
            'mrr_at_5':next((1/(i+1) for i,key in enumerate(selected) if key in relevant),0.)}

def grade(case,result,by_id,expected_prediction=None,fault_injected=False):
    status=result['status'];claims=(result.get('explanation') or {}).get('generation',{}).get('claims',[])
    text=' '.join(c['text'] for c in claims);normal=normalize(text)
    emitted=[{'evidence_id':key,'text':row['text']} for key,row in by_id.items() if key in {c['evidence_id'] for c in claims}]
    structural=validate_generation({'claims':claims},{'evidence':emitted}) if claims else None
    checks={'routing':result.get('intent') in case['expected_intents']}
    outputs={m['sender']:m['content'] for m in result.get('messages',[]) if m['performative'] in {'INFORM','RESPONSE'}}
    # Seven-agent outputs are differentiated by operation within the message.
    operation_names = {
        'DataAgent': {'errors': 'ValidationAgent', 'questions': 'ClarificationAgent'},
        'KnowledgeAgent': {'query_analysis': 'RetrievalAgent', 'evidence': 'EvidenceReaderAgent'},
    }
    for message in result.get('messages', []):
        if message['performative'] not in {'INFORM', 'RESPONSE'}:
            continue
        content = message['content']
        for field, name in operation_names.get(message['sender'], {}).items():
            if field in content:
                outputs[name] = content
                break
    supported=status in {'supported','supported_with_limitations','human_review'}
    if case['kind'] in {'knowledge','repair','assessment'}:
        checks['completion']=supported
        checks['citations']=bool(claims) and bool(structural['passed'])
        checks['answer_rubric']=bool(claims) and all(any(term in normal for term in alternatives) for alternatives in case.get('rubric',[])) and set(case.get('required_numbers',[]))<=number_values(text)
        checks['verification']=bool((result.get('verification') or {}).get('passed')) and supported
    if case['kind'] in {'safety','routing'}:
        checks['correct_stop']=status in case['expected_statuses'] and not result.get('prediction') and not claims
    if case['kind']=='validation':
        checks['validation']=status=='validation_failed' and bool(result.get('validation_errors')) and not result.get('prediction')
    if case['kind']=='assessment':
        checks['validation']=not result.get('validation_errors') and bool(result.get('prediction'))
        prediction=result.get('prediction')
        checks['immutable_prediction']=bool(prediction and expected_prediction and abs(prediction['probability']-expected_prediction['probability'])<=1e-6 and prediction['predicted_class']==expected_prediction['predicted_class'])
        rules=result.get('rules') or {};decision=result.get('decision') or {}
        if rules.get('review_required'):
            checks['rules_respected']=bool(rules.get('assessment')) and decision.get('review_required') is True and decision.get('final_label') is None
        else:
            # Lack of evidence may legitimately abstain even without a model
            # referral trigger. It must never emit a different model label.
            checks['rules_respected']=bool(rules.get('assessment') and prediction) and (decision.get('final_label')==prediction['predicted_class'] if supported else decision.get('final_label') in (None,prediction['predicted_class']))
        agents=[t['agent'] for t in result['traces']]
        chain=['DataAgent','DLAgent','RuleAgent','KnowledgeAgent','ExplanationAgent'] if 'DataAgent' in agents else ['ValidationAgent','PredictionAgent','RuleBasedAgent','RetrievalAgent','ExplanationAgent']
        checks['assessment_order']=all(a in agents for a in chain) and [agents.index(a) for a in chain]==sorted(agents.index(a) for a in chain)
    if case['task']=='knowledge':checks['no_dl_in_knowledge']=not result.get('prediction') and not any(t['agent'] in {'PredictionAgent','DLAgent'} for t in result['traces'])
    if 'RetrievalAgent' in outputs:
        evidence=outputs['RetrievalAgent'].get('evidence',[])
        checks['retrieval_provenance']=all(e['evidence_id'] in by_id and e['text']==by_id[e['evidence_id']]['text'] for e in evidence)
    if 'EvidenceReaderAgent' in outputs:
        evidence=outputs['EvidenceReaderAgent'].get('evidence',[])
        checks['reader_preserves_source']=all(e['evidence_id'] in by_id and e['text'] in by_id[e['evidence_id']]['text'] for e in evidence)
    if 'MonitoringAgent' in outputs:
        output=outputs['MonitoringAgent'];checks['monitoring_contract']=output.get('status')==status and output.get('steps')==len(result['traces'])-1
    if result.get('workflow_history'):
        checks['workflow_mask']=all(w.get('action') in w.get('allowed_actions',[]) and w.get('executed_handler') in outputs for w in result['workflow_history'])
    if 'ClarificationAgent' in outputs:
        output=outputs['ClarificationAgent'];checks['clarification_contract']=status in {'needs_clarification','validation_failed'} and bool(output.get('questions'))
    if case['kind']=='repair':
        reasons=[reason for revision in result.get('revisions',[]) for reason in revision.get('challenge',{}).get('reasons',[])]
        checks['fault_detected']=fault_injected and any(reason in {'quote_or_citation_invalid','unsupported_number'} for reason in reasons)
        checks['fault_repaired']=fault_injected and supported and bool(structural and structural['passed']) and any(r.get('state_changed') for r in result.get('revisions',[])) and 'benchmark_injected' not in text and '999999' not in text
    return {'checks':checks,'passed':all(checks.values()),'claims_emitted':len(claims),
            'valid_quotes':sum(c['evidence_id'] in by_id and c['quote'] in by_id[c['evidence_id']]['text'] for c in claims),
            'selected_qrel_hit':bool(set(case.get('relevant',[]))&{e['evidence_id'] for e in (result.get('knowledge') or {}).get('evidence',[])}) if case.get('relevant') else None}

def summarize(trials):
    groups={}
    for kind in sorted({r['kind'] for r in trials}):
        rows=[r for r in trials if r['kind']==kind]
        groups[kind]={'unique_cases':len({r['case_id'] for r in rows}),'runs':len(rows),
          'pass':rate(r['grade']['passed'] for r in rows),
          'latency_all':latency([r['elapsed_ms'] for r in rows]),
          'latency_completed':latency([r['elapsed_ms'] for r in rows if r['response']['status'] not in {'partial','error','verification_failed'}]),
          'unavailable':sum(r['response']['status'] in {'partial','error'} for r in rows)}
    agents={}
    checks={'CoordinatorAgent':'routing','ValidationAgent':'validation','PredictionAgent':'immutable_prediction',
            'RuleBasedAgent':'rules_respected','ExplanationAgent':'answer_rubric','CriticAgent':'fault_detected',
            'VerifierSafetyAgent':'verification','RetrievalAgent':'retrieval_provenance','EvidenceReaderAgent':'reader_preserves_source',
            'MonitoringAgent':'monitoring_contract','WorkflowRLAgent':'workflow_mask','ClarificationAgent':'clarification_contract'}
    if any(t['agent']=='KnowledgeAgent' for row in trials for t in row['response']['traces']):
        checks={'CoordinatorAgent':'routing','DataAgent':'validation','DLAgent':'immutable_prediction',
                'RuleAgent':'rules_respected','KnowledgeAgent':'retrieval_provenance',
                'ExplanationAgent':'answer_rubric','MonitoringAgent':'monitoring_contract'}
    for agent,check in checks.items():
        samples=[r for r in trials if check in r['grade']['checks']]
        durations=[t['duration_ms'] for r in trials for t in r['response']['traces'] if t['agent']==agent]
        agents[agent]={'criterion':check,'score':rate(r['grade']['checks'][check] for r in samples),'handler_latency':latency(durations)}
    emitted=sum(r['grade']['claims_emitted'] for r in trials);quotes=sum(r['grade']['valid_quotes'] for r in trials)
    repairs=[r for r in trials if r['kind']=='repair' and r['fault_injected']]
    return {'groups':groups,'agents':agents,'total_runs':len(trials),'unique_cases':len({r['case_id'] for r in trials}),
            'whole_flow':rate(r['grade']['passed'] for r in trials),
            'explanation':{'emitted_claims':emitted,'exact_quotes':quotes,'exact_quote_rate':quotes/emitted if emitted else None,
                'release_coverage':rate(r['grade']['claims_emitted']>0 for r in trials if r['kind'] in {'knowledge','assessment','repair'})},
            'repair':{'injected':len(repairs),'detection':rate(r['grade']['checks']['fault_detected'] for r in repairs),
                      'success':rate(r['grade']['checks']['fault_repaired'] for r in repairs)}}
