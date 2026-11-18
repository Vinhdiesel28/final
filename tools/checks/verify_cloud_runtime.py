"""Verify active cloud config, hybrid retrieval and restarted app, without Groq."""
import json,os,sys,time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
import settings
from services.knowledge_service import KnowledgeService

def main():
    if not (urlparse(os.environ.get('NEO4J_URI','')).hostname or '').endswith('.databases.neo4j.io'):
        raise RuntimeError('App is not configured for Aura')
    knowledge=KnowledgeService();hybrid=knowledge.hybrid
    try:
        if not hybrid or not hybrid.remote_vectors:raise RuntimeError('Cloud hybrid vector branch is not active')
        sample=next(c for c in hybrid.documents if c.get('source_type')=='pdf')
        rows,analysis=hybrid.retrieve(sample['text'],6)
        matches=[r for r in rows if r['id']==sample['id'] and 'vector' in r['retrieval_methods']]
        if not matches:raise RuntimeError('Qdrant retrieval did not return the original PDF chunk')
        for attempt in range(30):
            try:
                with urlopen('http://127.0.0.1:8010/health',timeout=3) as response:health=json.load(response)
                break
            except URLError:
                if attempt==29:raise
                time.sleep(1)
        if health['vector_retrieval']['backend']!='Qdrant Cloud vector + Neo4j fulltext + graph':
            raise RuntimeError('Restarted app still uses another backend')
        report={'status':'verified','scope':'Cloud databases and hybrid retrieval; no LLM calls',
                'app_status':health['status'],'backend':health['vector_retrieval']['backend'],
                'kb_version':hybrid.version,'total_vectors':len(hybrid.documents),
                'sample':{'chunk_id':sample['id'],'source_file':sample.get('source_file'),'page':sample.get('page_start'),
                          'retrieval_methods':matches[0]['retrieval_methods']},
                'neo4j_graph_edges':health['graph_edges']}
        (ROOT/'results/cloud_runtime_check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
    finally:
        if hybrid and hybrid.remote_vectors:hybrid.remote_vectors.client.close()
        if knowledge.store:knowledge.store.driver.close()

if __name__=='__main__':main()
