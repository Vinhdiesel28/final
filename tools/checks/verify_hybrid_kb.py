"""Live smoke checks with real Neo4j provenance; not a clinical/gold benchmark."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from agent_system import Services,MultiAgent

def main():
    services=Services();store=services.knowledge.store
    qa=store.query("""MATCH (v:KBVersion {id:$snapshot})
        MATCH (c:Chunk) WHERE c.id IN v.chunk_ids
        OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(c)
        RETURN count(c) AS chunks,count(d) AS chunks_with_document""",snapshot=services.knowledge.hybrid.snapshot)[0]
    before=store.query('MATCH (n) RETURN count(n) AS count')[0]['count']
    questions=['A1C phản ánh điều gì?','What is the A1C test?','How does physical activity help diabetes?','Thử nghiệm ZXQ9992026 chưa công bố có kết quả chính xác là gì?']
    runs=[]
    for question in questions:
        r=MultiAgent(services).run(question)
        runs.append({'question':question,'status':r['status'],'answer':r['answer'],
                     'verification':r['verification'],'citations':(r['knowledge'] or {}).get('citations',[]),
                     'retrieval':(r['knowledge'] or {}).get('retrieval',{}),
                     'generation':(r['explanation'] or {}).get('generation',{}),'latency_ms':r['total_duration_ms']})
    checks={
        'all_active_chunks_have_document':qa['chunks']==qa['chunks_with_document'],
        'pdf_chunks_have_page':all(d.get('page_start') for d in services.knowledge.hybrid.documents if d['source_type']=='pdf'),
        'web_chunks_available':any(d['source_type']=='web' for d in services.knowledge.hybrid.documents),
        'all_response_verifiers_pass':all(r['verification']['passed'] for r in runs),
    }
    report={'scope':'Live integration smoke checks; no gold accuracy claim','qa':qa,'nodes_before':before,'checks':checks,'runs':runs}
    (ROOT/'results/hybrid_kb_smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'qa':qa,'checks':checks,'status':[r['status'] for r in runs]},ensure_ascii=True))
    store.driver.close()

if __name__=='__main__':main()
