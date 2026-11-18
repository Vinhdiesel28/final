"""Execution metadata -> request-scoped audit record returned by the API."""
from dataclasses import asdict
from datetime import datetime, timezone
import time


def monitor(p, *, state):
    record = {
        'request_id': p['request_id'], 'status': p['status'],
        'started_at': p['started_at'], 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'duration_ms': round((time.perf_counter()-state.started)*1000, 3),
        'architecture_version': 'conversation_v3', 'agent_contract_version': '1.0.0',
        'message_schema_version': '2.0', 'task': p['task'],
        'steps': len(state.traces), 'message_count': len(state.messages),
        'executions': [asdict(step) for step in state.traces],
        'validation_error_count': len(state.validation_errors),
        'model_version': (state.prediction or {}).get('model_version'),
        'knowledge_backend': state.backend,
        'retrieved_evidence_ids': [item.get('evidence_id', item.get('id'))
                         for item in (state.knowledge or {}).get('evidence', [])],
        'citation_ids': list(dict.fromkeys(claim['evidence_id'] for claim in
                         (state.explanation or {}).get('generation', {}).get('claims', []))),
        'revision_count': len(state.revisions),
        'verification_passed': (state.verification or {}).get('passed'),
        'review_required': bool((state.decision or {}).get('review_required')),
        'scope': 'Snapshot before MonitoringAgent response; returned in API, not persisted to disk.',
    }
    return {'status': p['status'], 'steps': len(state.traces), 'audit_record': record,
            'summary': 'Ghi audit metadata và thời gian xử lý, không lưu giá trị hồ sơ hoặc câu hỏi'}
