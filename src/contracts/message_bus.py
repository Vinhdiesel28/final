"""Request-scoped structured agent envelopes; routing aliases support existing clients."""
from dataclasses import dataclass, asdict
import copy
import time
from uuid import uuid4

MESSAGE_VERSION = "2.0"
AGENT_VERSION = "1.0.0"

@dataclass
class Message:
    sequence: int
    sender: str
    receiver: str
    performative: str
    content: dict
    request_id: str
    version: str
    agent: str
    status: str
    payload: dict
    evidence: list
    model_version: str | None = None
    schema_version: str = MESSAGE_VERSION
    duration_ms: float = 0.

class MessageBus:
    def __init__(self):
        self.request_id = f"req_{uuid4().hex}"
        self.handlers = {}; self.messages = []; self.versions = {}

    def register(self, name, handler, version=AGENT_VERSION):
        self.handlers[name] = handler
        self.versions[name] = version

    def emit(self, sender, receiver, performative, content, duration_ms=0.):
        is_request = performative in {'REQUEST', 'CHALLENGE'}
        agent = receiver if is_request else sender
        status = 'pending' if is_request else ('error' if performative == 'FAILURE' else content.get('status', 'ok'))
        if not is_request and content.get('errors'):
            status = 'validation_failed'
        evidence = content.get('evidence', [])
        if not isinstance(evidence, list):
            evidence = [evidence] if evidence else []
        # Rule rationale is evidence of the decision, not a medical source citation.
        if not evidence and not is_request and content.get('assessment'):
            evidence = [{'kind': 'rule_rationale', 'assessment': content['assessment']}]
        message = Message(
            sequence=len(self.messages)+1, sender=sender, receiver=receiver,
            performative=performative, content=content, request_id=self.request_id,
            version=self.versions.get(agent, AGENT_VERSION), agent=agent, status=status,
            payload=content, evidence=evidence, model_version=content.get('model_version'),
            duration_ms=round(duration_ms, 3),
        )
        self.messages.append(copy.deepcopy(asdict(message)))

    def request(self, sender, receiver, content, performative='REQUEST'):
        self.emit(sender, receiver, performative, content); start = time.perf_counter()
        try:
            result = self.handlers[receiver](content)
        except Exception as exc:
            self.emit(receiver, sender, 'FAILURE', {'error': type(exc).__name__}, (time.perf_counter()-start)*1000)
            raise
        self.emit(receiver, sender, 'RESPONSE' if performative=='CHALLENGE' else 'INFORM', result, (time.perf_counter()-start)*1000)
        return result
