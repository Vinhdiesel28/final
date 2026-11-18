from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from services.knowledge_service import KnowledgeService, normalize
from services.model_service import DiabetesModelService
from contracts.message_bus import MessageBus
from functools import cached_property
import services.testing_guidance as testing_guidance

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
    audit_record: dict | None = None
    verification: dict | None = None
    clarification: dict | None = None
    explanation: dict | None = None
    testing_context: dict | None = None
    started: float = field(default_factory=time.perf_counter)

    def trace(self, agent: str, started: float, summary: str, tool: str, status: str = "success"):
        self.traces.append(Trace(agent, status, round((time.perf_counter() - started) * 1000, 2), summary, tool))


class Services:
    def __init__(self):
        self.model = DiabetesModelService(); self.knowledge = KnowledgeService()
        self.cdc = pd.read_csv(ROOT / "data/cdc_brfss_2015.csv")

    @cached_property
    def policy(self):
        # Used by LegacyMultiAgent to replay historical experiments.
        from legacy.workflow_policy import WorkflowPolicy
        return WorkflowPolicy()

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
    if testing_guidance.is_testing_guidance(question):return 'testing_guidance'
    if profile: return "risk_assessment"
    if any(x in q for x in ["ty le", "bao nhieu nguoi", "bao nhieu ca", "trung binh", "phan tram", "percent", "thong ke"]): return "dataset_statistics"
    return "medical_knowledge"


class SingleAgent:
    """One agent owns routing, tools, composition and safety review."""
    def __init__(self, services: Services): self.s = services

    def run(self, question: str = "", profile: dict | None = None, testing_context: dict | None = None) -> dict:
        state = State("single", question, profile); started = time.perf_counter(); state.intent = intent_of(question, profile)
        state.testing_context=testing_context
        state.backend=self.s.knowledge.backend
        if state.intent == "unsafe_medical_request":
            state.status = "blocked_unsafe_request"; state.answer = "Hệ thống không kê đơn hoặc lựa chọn điều trị. Hãy trao đổi với nhân viên y tế."
        elif state.intent == "out_of_scope":
            state.status = "out_of_scope"; state.answer = "Yêu cầu nằm ngoài phạm vi bệnh tiểu đường của hệ thống."
        elif state.intent=='testing_guidance':
            if testing_guidance.missing_context(testing_context):
                state.clarification=testing_guidance.clarify(testing_context)
                state.status='needs_clarification';state.answer=state.clarification['answer'];state.decision=state.clarification['decision']
            else:
                state.knowledge=self.s.knowledge.answer(testing_guidance.retrieval_question(question,testing_context))
                state.status='supported_with_limitations' if state.knowledge['citations'] else 'insufficient_evidence'
                state.answer='Thông tin tham khảo theo nguồn; việc lựa chọn xét nghiệm cá nhân cần được đánh giá tại cơ sở y tế. '+state.knowledge['answer']
        elif profile:
            errors = self.s.model.validate(profile)
            if errors: state.status = "invalid_input"; state.validation_errors = errors; state.answer = "Hồ sơ chưa hợp lệ."
            else:
                state.prediction = self.s.model.predict(profile); state.knowledge = self.s.knowledge.answer(question or "yếu tố nguy cơ type 2")
                state.review=self.s.review(state.prediction,state.knowledge)
                state.status = "supported_with_limitations"
                state.answer = f"Risk score {state.prediction['probability']*100:.1f}%. Đây là ước lượng học thuật, không phải chẩn đoán. " + state.knowledge["answer"]
        elif state.intent == "dataset_statistics":
            state.statistics = self.s.statistics(question); state.status = "supported"
            x = state.statistics; state.answer = f"Trong {x['group']}: {x['positive']:,}/{x['count']:,}, tương đương {x['rate']:.2f}%."
        else:
            state.knowledge = self.s.knowledge.answer(question); state.status = state.knowledge["status"]; state.answer = state.knowledge["answer"]
        state.trace("SingleAgent", started, f"intent={state.intent}; status={state.status}", "all_tools", "success")
        return serialize(state)



def serialize(state: State) -> dict:
    return {"request_id":state.request_id,"mode":state.mode,"intent":state.intent,"status":state.status,"answer":state.answer,
            "prediction":state.prediction,"statistics":state.statistics,"knowledge":state.knowledge,
            "validation_errors":state.validation_errors,"safety_flags":state.safety_flags,
            "messages":state.messages,"review":state.review,"workflow":state.workflow,"revisions":state.revisions,"knowledge_backend":state.backend,
            "evidence_review":state.evidence_review,"decision":state.decision,
            "audit_record":state.audit_record,"verification":state.verification,"clarification":state.clarification,"explanation":state.explanation,"workflow_history":state.workflow_history,
            "testing_context":state.testing_context,
            "traces":[t.__dict__ for t in state.traces],"total_duration_ms":round((time.perf_counter()-state.started)*1000,2)}


class MultiAgent:
    """Default live system: general conversational evidence-first coordination."""
    def __init__(self,services):
        from conversational_agents import ConversationAgents
        self.engine=ConversationAgents(services)
    def run(self,question='',profile=None,testing_context=None,conversation=None,task='auto'):
        return self.engine.run(question,profile,testing_context,conversation,task)


def __getattr__(name):
    if name == 'LegacyMultiAgent':
        from legacy.multi_agent import LegacyMultiAgent
        return LegacyMultiAgent
    raise AttributeError(name)
