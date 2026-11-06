from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from knowledge_service import KnowledgeService, normalize
from model_service import DiabetesModelService
from message_bus import MessageBus
from workflow_policy import WorkflowPolicy
from evidence_review import repair
from specialist_agents import Specialists, evidence_query, source_conflicts
import copy

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Trace:
    agent: str
    status: str
    duration_ms: float
    summary: str
    tool: str


@dataclass
class State:
    mode: str
    question: str = ""
    profile: dict | None = None
    request_id: str = field(default_factory=lambda: "REQ-" + uuid.uuid4().hex[:8].upper())
    intent: str = ""
    prediction: dict | None = None
    statistics: dict | None = None
    knowledge: dict | None = None
    validation_errors: list = field(default_factory=list)
    traces: list[Trace] = field(default_factory=list)
    status: str = "processing"
    answer: str = ""
    safety_flags: list[str] = field(default_factory=list)
    messages: list = field(default_factory=list)
    review: dict | None = None
    workflow: dict | None = None
    workflow_history: list = field(default_factory=list)
    backend: str = ''
    revisions: list = field(default_factory=list)
    evidence_review: dict | None = None
    decision: dict | None = None
    verification: dict | None = None
    clarification: dict | None = None
    explanation: dict | None = None
    started: float = field(default_factory=time.perf_counter)

    def trace(self, agent: str, started: float, summary: str, tool: str, status: str = "success"):
        self.traces.append(Trace(agent, status, round((time.perf_counter() - started) * 1000, 2), summary, tool))


class Services:
    def __init__(self):
        self.model = DiabetesModelService(); self.knowledge = KnowledgeService()
        self.cdc = pd.read_csv(ROOT / "data/cdc_brfss_2015.csv")
        self.policy = WorkflowPolicy()

    def statistics(self, question: str) -> dict:
        q = normalize(question); df = self.cdc.copy(); label = df.Diabetes_012.gt(0)
        group, mask = "toàn bộ mẫu", pd.Series(True, index=df.index)
        words=set(q.split())
        if words & {'nu','female'}: group, mask = "nữ", df.Sex.eq(0)
        elif words & {'nam','male'}: group, mask = "nam", df.Sex.eq(1)
        elif "tren 60" in q or "60" in q: group, mask = "nhóm tuổi mã 10–13", df.Age.ge(10)
        elif "tang huyet ap" in q: group, mask = "có tăng huyết áp", df.HighBP.eq(1)
        count, positive = int(mask.sum()), int((label & mask).sum()); rate = positive / max(count, 1) * 100
        return {"group": group, "count": count, "positive": positive, "rate": round(rate, 2),
                "formula": f"{positive} / {count} × 100", "source": "cdc_brfss_2015.csv"}

    def review(self, prediction, knowledge):
        reference=prediction.get('second_opinion',{})
        disagreement=prediction['predicted_class'] != reference.get('predicted_class',prediction['predicted_class'])
        gap=abs(prediction['probability']-reference.get('probability',prediction['probability']))
        challenges=[]
        if disagreement: challenges.append('Hai mô hình bất đồng nhãn tại threshold validation riêng.')
        if not knowledge.get('citations'): challenges.append('Chưa có nguồn giải thích phù hợp.')
        if abs(prediction['probability']-prediction['threshold']) < .05:
            challenges.append('Score gần threshold; kết quả nhạy với ngưỡng.')
        return {'disagreement':disagreement,'probability_gap':round(gap,4),
                'challenges':challenges,'requires_review':bool(challenges),
                'conclusion':'Cần xem xét thêm bằng chứng.' if challenges else 'Hai mô hình đồng thuận; vẫn chỉ là score học thuật.'}


UNSAFE = [
    "ke don", "lieu thuoc", "thuoc nao", "ngung thuoc", "chac chan",
    "tu mua thuoc", "tang lieu", "giam lieu", "don thuoc", "insulin bao nhieu",
]
OUTSIDE = ["co phieu", "bitcoin", "bong da", "doi bong", "thoi tiet", "gia vang", "ty gia", "xoso", "xo so"]


def intent_of(question: str, profile: dict | None) -> str:
    q = normalize(question)
    if any(x in q for x in UNSAFE): return "unsafe_medical_request"
    if any(x in q for x in OUTSIDE): return "out_of_scope"
    if profile: return "risk_assessment"
    if any(x in q for x in ["ty le", "bao nhieu nguoi", "bao nhieu ca", "trung binh", "phan tram", "percent", "thong ke"]): return "dataset_statistics"
    return "medical_knowledge"


class SingleAgent:
    """One agent owns routing, tools, composition and safety review."""
    def __init__(self, services: Services): self.s = services

    def run(self, question: str = "", profile: dict | None = None) -> dict:
        state = State("single", question, profile); started = time.perf_counter(); state.intent = intent_of(question, profile)
        state.backend=self.s.knowledge.backend
        if state.intent == "unsafe_medical_request":
            state.status = "blocked_unsafe_request"; state.answer = "Hệ thống không kê đơn hoặc lựa chọn điều trị. Hãy trao đổi với nhân viên y tế."
        elif state.intent == "out_of_scope":
            state.status = "out_of_scope"; state.answer = "Yêu cầu nằm ngoài phạm vi bệnh tiểu đường của hệ thống."
        elif profile:
            errors = self.s.model.validate(profile)
            if errors: state.status = "invalid_input"; state.validation_errors = errors; state.answer = "Hồ sơ chưa hợp lệ."
            else:
                state.prediction = self.s.model.predict(profile); state.knowledge = self.s.knowledge.answer(question or "yếu tố nguy cơ type 2")
                state.review=self.s.review(state.prediction,state.knowledge)
                state.workflow=self.s.policy.recommend(evidence=bool(state.knowledge['citations']),review=state.review['requires_review'])
                state.status = "supported_with_limitations"
                state.answer = f"Risk score {state.prediction['probability']*100:.1f}%. Đây là ước lượng học thuật, không phải chẩn đoán. " + state.knowledge["answer"]
        elif state.intent == "dataset_statistics":
            state.statistics = self.s.statistics(question); state.status = "supported"
            x = state.statistics; state.answer = f"Trong {x['group']}: {x['positive']:,}/{x['count']:,}, tương đương {x['rate']:.2f}%."
        else:
            state.knowledge = self.s.knowledge.answer(question); state.status = state.knowledge["status"]; state.answer = state.knowledge["answer"]
        state.trace("SingleAgent", started, f"intent={state.intent}; status={state.status}", "all_tools", "success")
        return serialize(state)


class MultiAgent:
    """State-driven, bounded specialist collaboration with executable handlers."""
    def __init__(self, services: Services): self.s = services

    def run(self, question: str = "", profile: dict | None = None) -> dict:
        state=State('multi',question,profile); state.backend=self.s.knowledge.backend
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
        if state.intent not in {'unsafe_medical_request','out_of_scope'} and (profile is not None or personal):
            state.intent='risk_assessment'
        if state.intent in {'unsafe_medical_request','out_of_scope'}:
            state.status='blocked_unsafe_request' if state.intent.startswith('unsafe') else 'out_of_scope'
            state.answer='Hệ thống không kê đơn hoặc lựa chọn điều trị. Hãy trao đổi với nhân viên y tế.' if state.intent.startswith('unsafe') else 'Yêu cầu nằm ngoài phạm vi bệnh tiểu đường của hệ thống.'
            state.decision={'status':state.status,'final_label':None,'review_required':False}
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
        if state.prediction or state.intent=='medical_knowledge':
            query=evidence_query(question or 'yếu tố nguy cơ type 2',state.prediction) if state.prediction else (question or 'yếu tố nguy cơ type 2')
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
                from evidence_review import rewrite_query
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
        payload={'prediction':state.prediction,'knowledge':state.knowledge,'decision':state.decision,
                 'conflicts':conflicts,'statistics':state.statistics,'clarification':state.clarification,
                 'blocked':state.intent in {'unsafe_medical_request','out_of_scope'}}
        if state.intent not in {'unsafe_medical_request','out_of_scope'}:
            state.explanation=call('ExplanationAgent',payload)
            state.answer=state.explanation['answer']
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


def serialize(state: State) -> dict:
    return {"request_id":state.request_id,"mode":state.mode,"intent":state.intent,"status":state.status,"answer":state.answer,
            "prediction":state.prediction,"statistics":state.statistics,"knowledge":state.knowledge,
            "validation_errors":state.validation_errors,"safety_flags":state.safety_flags,
            "messages":state.messages,"review":state.review,"workflow":state.workflow,"revisions":state.revisions,"knowledge_backend":state.backend,
            "evidence_review":state.evidence_review,"decision":state.decision,
            "verification":state.verification,"clarification":state.clarification,"explanation":state.explanation,"workflow_history":state.workflow_history,
            "traces":[t.__dict__ for t in state.traces],"total_duration_ms":round((time.perf_counter()-state.started)*1000,2)}
