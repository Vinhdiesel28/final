"""General evidence-first coordinator: analyze -> tools -> draft -> critique -> act.

This is the live v3 workflow. The earlier fixed workflow remains available only
for reproducing historical experiments. No expected benchmark answers enter here.
"""
import copy
import math
import time
from functools import partial
from datetime import datetime, timezone

from services.agent_llm import AgentLLM, ProviderFailure
from agents.coordinator_agent import analyze
from agents.data_agent import handle as handle_data
from agents.dl_agent import predict
from agents.explanation_agent import handle as handle_explanation
from agents.knowledge_agent import EvidenceReader, handle as handle_knowledge
from agents.monitoring_agent import monitor
from agents.rule_agent import rules
from services.llm_explanation import number_values
from contracts.message_bus import MessageBus
from services.review_policy import ReviewPolicy


class ConversationAgents:
    def __init__(self,services):
        self.s=services
        if not hasattr(services,'agent_llm'):services.agent_llm=AgentLLM()
        self.llm=services.agent_llm
        self.review_policy=getattr(services,'review_policy',None) or ReviewPolicy()
        documents=getattr(getattr(services.knowledge,'hybrid',None),'documents',[])
        self.evidence_reader = EvidenceReader(documents)

    def run(self,question='',profile=None,testing_context=None,conversation=None,task='auto'):
        from agent_system import State,serialize
        if task not in {'auto','assessment','knowledge'}:raise ValueError('Unknown task')
        if task=='knowledge':profile=None
        state=State('multi',question,profile);state.backend=self.s.knowledge.backend
        state.testing_context=testing_context
        state.plan=None;state.response_review=None
        history=(conversation or [])[-8:]
        user_numbers=number_values(question+' '+' '.join(m['content'] for m in history if m.get('role')=='user'))
        bus=MessageBus();state.messages=bus.messages
        state.request_id=bus.request_id
        started_at=datetime.now(timezone.utc).isoformat()
        validated_features=None
        current={'plan':None,'evidence':[],'draft':None,'critique':None,'generation':None}

        def call(name,payload,sender='CoordinatorAgent',performative='REQUEST'):
            start=time.perf_counter()
            try:
                result=bus.request(sender,name,payload,performative)
                state.trace(name,start,result.get('summary',result.get('status','executed')),payload.get('action',name))
                return result
            except Exception:
                state.trace(name,start,'handler failed',name,'error');raise

        def knowledge_for_plan(payload):
            return handle_knowledge(
                payload, knowledge=self.s.knowledge, services=self.s,
                reader=self.evidence_reader, queries=current['plan']['queries'],
                requested_sources=current['plan']['requested_sources'],
            )

        handlers = {
            'CoordinatorAgent': partial(analyze, task=task, llm=self.llm),
            'DataAgent': partial(handle_data, model=self.s.model),
            'DLAgent': partial(predict, model=self.s.model),
            'RuleAgent': partial(rules, review_policy=self.review_policy),
            'KnowledgeAgent': knowledge_for_plan,
            'ExplanationAgent': partial(handle_explanation, task=task, llm=self.llm, user_numbers=user_numbers),
            'MonitoringAgent': partial(monitor, state=state),
        }
        for name, handler in handlers.items():
            bus.register(name, handler)

        def finish():
            if state.prediction and f"{state.prediction['probability']*100:.1f}%" not in state.answer:
                score=f"Score mô hình {state.prediction['probability']*100:.1f}% (ngưỡng {state.prediction['threshold']*100:.1f}%). Đây không phải chẩn đoán."
                state.answer=score+' '+state.answer
                if state.explanation:
                    state.explanation['sections'].insert(0,{'id':'assessment','title':'Kết quả mô hình','text':score});state.explanation['answer']=state.answer
            if state.decision is None:
                rules_state=getattr(state,'rules',None) or {}
                needs_review=bool(rules_state.get('review_required'))
                state.decision={'status':state.status,'final_label':None,'review_required':needs_review,
                                'reason_codes':(rules_state.get('reason_codes') or ['validation_selected_uncertainty']) if needs_review else [],
                                'assessment':rules_state.get('assessment')}
            state.verification=call('ExplanationAgent',{'action':'verify','status':state.status,'answer':state.answer,'draft':current['draft'],
                    'review':current['critique'],'evidence':current['evidence'],'prediction':state.prediction})
            if not state.verification['passed']:
                state.status='verification_failed';state.answer='Câu trả lời chưa vượt qua kiểm chứng. Bạn có thể cung cấp thêm bối cảnh hoặc đặt câu hỏi cụ thể hơn.'
                state.explanation={'answer':state.answer,'sections':[{'id':'notice','title':'Chưa thể xác minh','text':state.answer}],'model_factors':[]}
                state.decision.update(status=state.status,final_label=None,review_required=True)
            audit=call('MonitoringAgent',{'status':state.status,'request_id':bus.request_id,
                        'started_at':started_at,'task':task})
            state.audit_record=audit['audit_record']
            for revision in state.revisions:
                if revision.pop('pending',False):
                    revision['state_changed']=revision['before']!=revision['after']
                    revision['outcome']='interrupted' if state.status in {'partial','error'} else 'repair_budget_exhausted'
            result=serialize(state);result['plan']=state.plan;result['response_review']=state.response_review
            result['rules']=getattr(state,'rules',None)
            result['architecture_version']='conversation_v3';result['task']=task
            result['request_id']=bus.request_id
            return result

        def show_clarification(questions, status='needs_clarification'):
            state.clarification=call('DataAgent',{'action':'clarify','questions':questions,'status':status})
            state.status=status;state.answer=state.clarification['answer']
            state.explanation={'answer':state.answer,'sections':[{'id':'clarification','title':'Thông tin cần làm rõ','text':state.answer}],'model_factors':[]}

        try:
            plan=call('CoordinatorAgent',{'question':question,'conversation':history,
                   'available_profile_fields':list((profile or {}).keys()),'additional_context':testing_context or {}})
            current['plan']=plan;state.plan=plan;state.intent=plan['intent']
            if plan['intent'] in {'unsafe','out_of_scope'}:
                state.status='blocked_unsafe_request' if plan['intent']=='unsafe' else 'out_of_scope'
                state.answer='Hệ thống không kê đơn hoặc thay đổi liều thuốc. Bạn có thể hỏi thông tin chung có nguồn về tiểu đường.' if plan['intent']=='unsafe' else 'Câu hỏi nằm ngoài phạm vi kiến thức tiểu đường của hệ thống.'
                return finish()
            if not plan['can_answer_general'] and plan['clarification_questions'] and plan['intent']!='prediction':
                show_clarification(plan['clarification_questions']);return finish()
            if plan['intent']=='prediction':
                validation=call('DataAgent',{'action':'validate','profile':profile or {}})
                errors=validation['errors']
                if errors:
                    state.validation_errors=errors;show_clarification(['Để chạy mô hình nguy cơ, vui lòng bổ sung hoặc xác nhận: '+', '.join(e['field'] for e in errors)+'.'], status='validation_failed');return finish()
                validated_features=validation['validated_features']
                state.prediction=call('DLAgent',{'features':validated_features})
            if plan['intent']=='statistics':
                state.statistics=call('KnowledgeAgent',{'action':'statistics','question':question});x=state.statistics
                state.answer=f"Trong {x['group']}: {x['positive']:,}/{x['count']:,}, tương đương {x['rate']:.2f}%. Đây là tỷ lệ nhãn trong dataset, không phải tỷ lệ dân số."
                state.status='supported';state.explanation={'answer':state.answer,'sections':[{'id':'statistics','title':'Thống kê dataset','text':state.answer}],'model_factors':[]};return finish()
            state.rules=call('RuleAgent',{'features':validated_features,'prediction':state.prediction})
            state.knowledge=call('KnowledgeAgent',{'action':'retrieve','queries':plan['queries']})
            prepared=call('KnowledgeAgent',{'action':'read','evidence':state.knowledge['evidence']})
            current['evidence']=prepared['evidence']
            if not current['evidence'] and plan['goal'] not in plan['queries']:
                state.knowledge=call('KnowledgeAgent',{'action':'retrieve','queries':[plan['goal']]})
                current['evidence']=call('KnowledgeAgent',{'action':'read','evidence':state.knowledge['evidence']})['evidence']
            for attempt in range(3):
                if not current['evidence']:break
                payload={'question':question,'goal':plan['goal'],'intent':plan['intent'],'conversation':history[-4:],
                         'clarification_questions':plan['clarification_questions'],'revision_round':attempt,
                         'evidence':current['evidence'],'challenge':current['critique']}
                if current['draft']:
                    payload['previous_draft']={k:current['draft'][k] for k in ('claims','followup_questions','evidence_sufficient','missing_information')}
                current['draft']=call('ExplanationAgent',payload,'ExplanationAgent' if attempt else 'CoordinatorAgent','CHALLENGE' if attempt else 'REQUEST')
                if state.revisions and state.revisions[-1].get('pending'):
                    revision=state.revisions[-1]
                    revision['after']={'answer':copy.deepcopy(current['draft']['claims']),'evidence_ids':[e['evidence_id'] for e in current['evidence']]}
                    revision['state_changed']=revision['before']!=revision['after'];revision.pop('pending')
                current['critique']=call('ExplanationAgent',{'action':'critique','question':question,'goal':plan['goal'],'conversation':history[-4:],
                            'draft':{k:current['draft'][k] for k in ('claims','followup_questions','evidence_sufficient','missing_information')},'evidence':current['evidence']})
                state.response_review=current['critique'];action=current['critique']['action']
                if action=='accept':
                    composed = call('ExplanationAgent', {
                        'action': 'compose', 'prediction': state.prediction, 'rules': state.rules,
                        'evidence': current['evidence'], 'draft': current['draft'],
                        'critique': current['critique'], 'intent': state.intent,
                        'clarification_questions': plan['clarification_questions'],
                    })
                    state.status = composed['status']
                    state.explanation = composed['explanation']
                    state.answer = state.explanation['answer']
                    state.decision = composed['decision']
                    state.knowledge.update(evidence=composed['evidence'], citations=composed['citations'])
                    return finish()
                if action=='clarify':
                    show_clarification(current['critique']['followup_questions'] or plan['clarification_questions'] or ['Bạn có thể nói rõ mục đích và bối cảnh của câu hỏi không?']);return finish()
                if action=='abstain':break
                before={'answer':copy.deepcopy(current['draft']['claims']),'evidence_ids':[e['evidence_id'] for e in current['evidence']]}
                if action=='retrieve_again' and attempt<2:
                    query=current['critique']['revised_query']
                    if not query:break
                    state.knowledge=call('KnowledgeAgent',{'action':'retrieve','queries':[query]},'ExplanationAgent','CHALLENGE')
                    current['evidence']=call('KnowledgeAgent',{'action':'read','evidence':state.knowledge['evidence']},'ExplanationAgent','CHALLENGE')['evidence']
                state.revisions.append({'round':attempt+1,'action':action,'before':before,'after':{'answer':copy.deepcopy(current['draft']['claims']),'evidence_ids':[e['evidence_id'] for e in current['evidence']]},'challenge':copy.deepcopy(current['critique']),'state_changed':False,'pending':True})
            state.status='insufficient_evidence'
            state.answer='Chưa tìm được bằng chứng đủ phù hợp để trả lời chính xác câu hỏi này. '+((current['draft'] or {}).get('missing_information') or 'Bạn có thể làm rõ mục tiêu hoặc bổ sung tài liệu liên quan.')
            state.explanation={'answer':state.answer,'sections':[{'id':'notice','title':'Bằng chứng chưa đủ','text':state.answer}],'model_factors':[]}
            return finish()
        except ProviderFailure as exc:
            state.status='partial';state.intent=state.intent or 'unresolved'
            state.answer='Dịch vụ phân tích hoặc diễn giải đang bị giới hạn lượt gọi. Vui lòng thử lại sau.' if exc.kind=='rate_limited' else 'Dịch vụ xử lý ngôn ngữ hiện chưa khả dụng; hệ thống chưa hoàn tất câu trả lời có kiểm chứng.'
            if exc.kind=='rate_limited' and exc.retry_after is not None:
                state.answer=f"Groq đang giới hạn quota tại bước {exc.task or 'xử lý ngôn ngữ'}. Nhà cung cấp yêu cầu chờ khoảng {math.ceil(exc.retry_after)} giây trước khi thử lại."
            state.explanation={'answer':state.answer,'sections':[{'id':'notice','title':'Chưa hoàn tất xử lý','text':state.answer}],'model_factors':[],
                               'generation':{'status':'unavailable','error':exc.kind,'http_status':exc.http_status,'task':exc.task,'retry_after_seconds':exc.retry_after}}
            return finish()
        except Exception as exc:
            state.status='error';state.intent=state.intent or 'unresolved'
            state.answer='Một thành phần xử lý gặp lỗi; hệ thống chưa hoàn tất câu trả lời có kiểm chứng.'
            state.explanation={'answer':state.answer,'sections':[{'id':'notice','title':'Chưa hoàn tất','text':state.answer}],'model_factors':[],
                               'generation':{'status':'unavailable','error':type(exc).__name__}}
            return finish()
