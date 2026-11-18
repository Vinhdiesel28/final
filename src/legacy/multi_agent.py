from __future__ import annotations
from agent_system import State, serialize, intent_of
from contracts.message_bus import MessageBus
from services.knowledge_service import normalize
from legacy.specialist_agents import Specialists, evidence_query, source_conflicts
from legacy.evidence_review import repair
import services.testing_guidance as testing_guidance
import time
import copy

class LegacyMultiAgent:
    """State-driven, bounded specialist collaboration with executable handlers."""
    def __init__(self, services: Services): self.s = services

    def run(self, question: str = "", profile: dict | None = None, testing_context: dict | None = None) -> dict:
        state=State('multi',question,profile); state.backend=self.s.knowledge.backend
        state.testing_context=testing_context
        bus=MessageBus(); state.messages=bus.messages; handlers=Specialists(self.s)
        for name,handler in {
            'ValidationAgent':lambda p:{'errors':self.s.model.validate(p['profile'])},
            'PredictionAgent':lambda p:self.s.model.predict(p['profile']),
            'RetrievalAgent':lambda p:self.s.knowledge.answer(p['question']),
            'StatisticsAgent':lambda p:self.s.statistics(p['question']),
            'ClarificationAgent':handlers.clarify,'CriticAgent':handlers.critic,
            'ReviewAgent':handlers.review,'ExplanationAgent':handlers.explain,
            'VerifierSafetyAgent':handlers.verify,
            'WorkflowRLAgent':lambda p:self.s.policy.select(**p),
        }.items(): bus.register(name,handler)

        def call(name,payload,sender='CoordinatorAgent',performative='REQUEST'):
            t=time.perf_counter(); result=bus.request(sender,name,payload,performative)
            state.trace(name,t,result.get('status',result.get('conclusion','Handler executed')),name)
            return result

        def choose(**context):
            state.workflow=call('WorkflowRLAgent',context)
            state.workflow_history.append(state.workflow)
            return state.workflow

        state.intent=intent_of(question,profile)
        personal=any(x in normalize(question) for x in ['nguy co cua toi','toi co bi tieu duong','danh gia ho so','du doan ho so'])
        if state.intent not in {'unsafe_medical_request','out_of_scope','testing_guidance'} and (profile is not None or personal):
            state.intent='risk_assessment'
        if state.intent in {'unsafe_medical_request','out_of_scope'}:
            state.status='blocked_unsafe_request' if state.intent.startswith('unsafe') else 'out_of_scope'
            state.answer='Hệ thống không kê đơn hoặc lựa chọn điều trị. Hãy trao đổi với nhân viên y tế.' if state.intent.startswith('unsafe') else 'Yêu cầu nằm ngoài phạm vi bệnh tiểu đường của hệ thống.'
            state.decision={'status':state.status,'final_label':None,'review_required':False}
        elif state.intent=='testing_guidance':
            if testing_guidance.missing_context(testing_context):
                route=choose(missing=True)
                state.clarification=call('ClarificationAgent',{'task':'testing_guidance','context':testing_context})
                route['executed_handler']='ClarificationAgent'
                state.decision=state.clarification['decision'];state.status='needs_clarification'
        elif state.intent=='risk_assessment':
            state.validation_errors=call('ValidationAgent',{'profile':profile or {}})['errors']
            if state.validation_errors:
                route=choose(missing=True)
                if route['action']!='ask_for_information': raise RuntimeError('Safety mask violated')
                state.clarification=call('ClarificationAgent',{'errors':state.validation_errors})
                route['executed_handler']='ClarificationAgent'
                state.decision=state.clarification['decision']; state.status='needs_clarification'
            else:
                state.prediction=call('PredictionAgent',{'profile':profile})
        elif state.intent=='dataset_statistics':
            state.statistics=call('StatisticsAgent',{'question':question})
            state.status='supported'; state.decision={'status':state.status,'final_label':None,'review_required':False}

        conflicts=[]
        if state.prediction or state.intent=='medical_knowledge' or (state.intent=='testing_guidance' and not state.clarification):
            query=evidence_query(question or 'yếu tố nguy cơ type 2',state.prediction) if state.prediction else (question or 'yếu tố nguy cơ type 2')
            if state.intent=='testing_guidance':query=testing_guidance.retrieval_question(question,testing_context)
            route=choose(evidence=False)
            if route['action']!='show_sources': raise RuntimeError('Retrieval mask violated')
            state.knowledge=call('RetrievalAgent',{'question':query})
            route['executed_handler']='RetrievalAgent'
            # Preserve conflicts discovered before repair so filtering a citation
            # cannot silently erase contradictory evidence.
            conflicts=source_conflicts(state.knowledge,self.s.knowledge.by_id)
            if not conflicts:
                state.knowledge,state.evidence_review,revisions=repair(query,state.knowledge,self.s.knowledge.by_id,bus)
                state.revisions.extend(revisions)
                conflicts=source_conflicts(state.knowledge,self.s.knowledge.by_id)
            # One optional policy-selected retrieval, then force progress. Evidence
            # conflicts cannot be removed by a later response dropping a source.
            route=choose(evidence=bool(state.knowledge.get('citations')),review=bool(conflicts),retrieval_remaining=bool(state.knowledge.get('citations')))
            if route['action']=='show_sources':
                from legacy.evidence_review import rewrite_query
                candidate=call('RetrievalAgent',{'question':rewrite_query(query)})
                route['executed_handler']='RetrievalAgent'
                new_conflicts=source_conflicts(candidate,self.s.knowledge.by_id)
                conflicts.extend(c for c in new_conflicts if c not in conflicts)
                if not conflicts:
                    candidate,checked,changes=repair(query,candidate,self.s.knowledge.by_id,bus)
                    state.knowledge=candidate; state.evidence_review=checked; state.revisions.extend(changes)
                    conflicts=source_conflicts(candidate,self.s.knowledge.by_id)
                else: state.knowledge=candidate
            state.decision={'status':'supported_with_limitations' if state.prediction else 'supported',
                            'final_label':state.prediction['predicted_class'] if state.prediction else None,
                            'probability':state.prediction['probability'] if state.prediction else None,
                            'review_required':False,'reason_codes':[]}
            for round_number in range(1,3):
                payload={'prediction':state.prediction,'knowledge':state.knowledge,
                         'decision':state.decision,'conflicts':conflicts}
                state.review=call('CriticAgent',payload)
                if state.review['passed']: break
                before=copy.deepcopy(state.decision)
                route=choose(evidence=bool(state.knowledge.get('citations')),review=state.review['requires_review'],retrieval_remaining=False)
                if route['action'] not in {'request_human_review','explain_score'}: raise RuntimeError('Unexpected review action')
                state.decision=call('ReviewAgent',{**payload,'critique':state.review},'CriticAgent','CHALLENGE')
                route['executed_handler']='ReviewAgent'
                state.revisions.append({'round':round_number,'action':'revise_conclusion',
                    'before':before,'after':copy.deepcopy(state.decision),'state_changed':before!=state.decision,
                    'initial_challenges':state.review['reason_codes']})
            if not state.review['passed']:
                state.review=call('CriticAgent',{'prediction':state.prediction,'knowledge':state.knowledge,'decision':state.decision,'conflicts':conflicts})
                if not state.review['passed']:
                    state.decision={**state.decision,'status':'verification_failed','final_label':None,
                        'review_required':True,'reason_codes':state.review['reason_codes']+['critic_unresolved'],
                        'source_conflicts':conflicts}
            state.status=state.decision['status']
        payload={'question':question,'intent':state.intent,'testing_context':state.testing_context,'prediction':state.prediction,'knowledge':state.knowledge,'decision':state.decision,
                 'conflicts':conflicts,'statistics':state.statistics,'clarification':state.clarification,
                 'blocked':state.intent in {'unsafe_medical_request','out_of_scope'}}
        if state.intent not in {'unsafe_medical_request','out_of_scope'}:
            state.explanation=call('ExplanationAgent',payload)
            state.answer=state.explanation['answer']
            generation=state.explanation.get('generation',{})
            if generation.get('status') in {'rejected','unavailable','configuration_required','configuration_error'}:
                final_payload={**payload,'phase':'final_response','generation':generation}
                state.review=call('CriticAgent',final_payload)
                before=copy.deepcopy(state.decision)
                state.decision=call('ReviewAgent',{**final_payload,'critique':state.review},'CriticAgent','CHALLENGE')
                state.status=state.decision['status'];payload['decision']=state.decision
                state.revisions.append({'action':'revise_response_status','before':before,'after':copy.deepcopy(state.decision),'state_changed':before!=state.decision})
                state.explanation=call('ExplanationAgent',{**payload,'generation_override':generation},'CriticAgent','CHALLENGE')
                state.answer=state.explanation['answer']
                state.review=call('CriticAgent',{**final_payload,'decision':state.decision})
            for selected in state.workflow_history:
                if 'executed_handler' not in selected: selected['executed_handler']='ExplanationAgent' if selected['action']=='explain_score' else 'ReviewAgent'
        state.verification=call('VerifierSafetyAgent',{**payload,'answer':state.answer,'explanation':state.explanation})
        if not state.verification['passed']:
            before=state.answer
            state.explanation=call('ExplanationAgent',{**payload,'verification':state.verification},'VerifierSafetyAgent','CHALLENGE')
            state.answer=state.explanation['answer']
            state.revisions.append({'action':'rewrite_final_explanation','before':before,'after':state.answer,'state_changed':before!=state.answer})
            state.verification=call('VerifierSafetyAgent',{**payload,'answer':state.answer,'explanation':state.explanation})
            if not state.verification['passed']:
                state.status='verification_failed'; state.answer='Không thể xác minh kết luận. Cần xem xét thêm.'
                state.decision={**state.decision,'status':state.status,'final_label':None,'review_required':True}
        return serialize(state)


