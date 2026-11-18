"""Unified Neo4j Document/Chunk/Entity/Fact KB and bounded hybrid retrieval."""
import json
import re
import os
from pathlib import Path
import joblib

ROOT=Path(__file__).resolve().parents[2]
SCHEMA=(ROOT/'knowledge/DB_diabet.cypher')

WRITES={
 'documents':'UNWIND $rows AS row MERGE (d:Document {id:row.id}) SET d += row',
 'chunks':'''UNWIND $rows AS row MERGE (c:Chunk {id:row.id}) SET c += row
             WITH c,row MATCH (d:Document {id:row.document_id}) MERGE (d)-[:HAS_CHUNK]->(c)''',
 'entities':'UNWIND $rows AS row MERGE (e:Entity {canonical_id:row.canonical_id}) SET e += row',
 'facts':'''UNWIND $rows AS row MERGE (f:Fact {id:row.id}) SET f += row
            WITH f,row MATCH (s:Entity {canonical_id:row.subject_id}),(o:Entity {canonical_id:row.object_id}),(c:Chunk {id:row.chunk_id})
            MERGE (f)-[:SUBJECT]->(s) MERGE (f)-[:OBJECT]->(o) MERGE (f)-[:SUPPORTED_BY]->(c)''',
 'mentions':'''UNWIND $rows AS row MATCH (c:Chunk {id:row.chunk_id}),(e:Entity {canonical_id:row.entity_id}) MERGE (c)-[:MENTIONS {kb_version:row.kb_version}]->(e)''',
}

def literal(value):
    if value is None:return 'null'
    if isinstance(value,bool):return str(value).lower()
    if isinstance(value,str):return "'"+value.replace('\\','\\\\').replace("'","\\'").replace('\r','\\r').replace('\n','\\n')+"'"
    if isinstance(value,list):return '['+','.join(literal(v) for v in value)+']'
    if isinstance(value,dict):return '{'+','.join('`'+k.replace('`','``')+'`:'+literal(v) for k,v in value.items())+'}'
    return str(value)

def bundle_rows(bundle,name):
    if name=='mentions':
        return [row | {'kb_version':bundle['version']} for row in bundle[name]]
    return bundle[name]


def seed_statements(bundle):
    for name,cypher in WRITES.items():
        rows=bundle_rows(bundle,name)
        for start in range(0,len(rows),100):yield cypher.replace('$rows',literal(rows[start:start+100]))+';'
    keys=[bundle['version']] if 'semantic_vectors' in bundle else [bundle['version'],'current']
    yield ('UNWIND '+literal(keys)+' AS key MERGE (k:KBVersion {id:key}) SET k.version='
           +literal(bundle['version'])+',k.chunk_ids='+literal([c['id'] for c in bundle['chunks']])
           +',k.fact_ids='+literal([f['id'] for f in bundle['facts']])
           +',k.embedding_model='+literal(embedding_id(bundle))+" ,k.source_policy='pdf_web_only';")

def embedding_id(bundle):
    return bundle['embedding'] if 'semantic_vectors' in bundle else 'lsa-128'


def rank_graph(rows, question_terms, limit=20):
    from services.knowledge_service import tokens
    def sort_key(row):
        overlap=len(question_terms.intersection(tokens(row['doc']['text'])))
        return (-overlap, -row['matched_entities'], row['doc']['id'])
    return sorted(rows,key=sort_key)[:limit]


def ingest(bundle,store=None,*,activate=True):
    from services.neo4j_store import Neo4jStore
    owned=store is None
    if 'semantic_vectors' in bundle and (not owned or os.environ.get('HYBRID_VECTOR_BACKEND')!='qdrant'):
        raise ValueError('Semantic bundles require the configured Qdrant backend')
    store=store or Neo4jStore()
    try:
        if owned and os.environ.get('HYBRID_VECTOR_BACKEND','neo4j')=='qdrant':
            from services.qdrant_backend import sync_bundle
            sync_bundle(bundle)
        schema=SCHEMA.read_text(encoding='utf-8').split('// The Python ingestion')[0]
        schema='\n'.join(line for line in schema.splitlines() if not line.lstrip().startswith('//'))
        for query in schema.split(';'):
            if query.strip():store.query(query)
        # Populate records first; activate only once the complete version is available.
        for name,cypher in WRITES.items():
            rows=bundle_rows(bundle,name)
            for start in range(0,len(rows),100):store.query(cypher,rows=rows[start:start+100])
        store.query('CALL db.awaitIndexes(120)')
        store.query(
            "UNWIND $keys AS key MERGE (k:KBVersion {id:key}) "
            "SET k.version=$version,k.chunk_ids=$ids,k.fact_ids=$facts,k.embedding_model=$embedding,"
            "k.source_policy='pdf_web_only'",
            keys=[bundle['version'], 'current'] if activate else [bundle['version']],
            version=bundle['version'],ids=[c['id'] for c in bundle['chunks']],
            facts=[f['id'] for f in bundle['facts']],embedding=embedding_id(bundle),
        )
    finally:
        if owned:store.driver.close()

class HybridKB:
    def __init__(self,store,version=None):
        self.store=store
        self.snapshot=version or 'current'
        current=store.query("MATCH (k:KBVersion {id:$snapshot}) RETURN k.version AS version,k.embedding_model AS embedding_model,k.source_policy AS source_policy",snapshot=self.snapshot)
        if not current:raise RuntimeError('Hybrid KB has not been ingested')
        self.version=current[0]['version']
        self.remote_vectors=None
        if os.environ.get('HYBRID_VECTOR_BACKEND','neo4j')=='qdrant':
            from services.qdrant_backend import HybridQdrant
            self.remote_vectors=HybridQdrant(self.version)
        self.documents=[r['doc'] for r in store.query(
            "MATCH (k:KBVersion {id:$snapshot}) MATCH (c:Chunk) WHERE c.id IN k.chunk_ids RETURN properties(c) AS doc",
            snapshot=self.snapshot,
        )]
        self.documents_by_id={doc['id']:doc for doc in self.documents}
        self.entities=store.query('MATCH (e:Entity) RETURN e.canonical_id AS id,e.name AS name,e.aliases AS aliases')
        self.primary_sources_only=current[0].get('source_policy')=='pdf_web_only'
        self.embedding_model=current[0].get('embedding_model') or 'lsa-128'
        self.encoder=None
        if self.embedding_model!='lsa-128':
            from services.semantic_embedding import E5Encoder
            if not self.remote_vectors or self.embedding_model!=E5Encoder.identifier:
                raise RuntimeError('Unsupported active KB embedding configuration')
            self.encoder=E5Encoder()
        else:
            folder=ROOT/'knowledge/vector_artifacts'
            self.vectorizer=joblib.load(folder/'tfidf_vectorizer.joblib');self.svd=joblib.load(folder/'lsa_svd.joblib');self.normalizer=joblib.load(folder/'normalizer.joblib')
    def metadata(self):
        return {'backend':'Qdrant Cloud vector + Neo4j fulltext + graph' if self.remote_vectors else 'Neo4j vector + fulltext + graph','source_policy':'pdf_web_only' if self.primary_sources_only else 'all_sources','embedding_model':self.embedding_model,'dimensions':self.encoder.dimension if self.encoder else 128,'total_vectors':len(self.documents),'pdf_chunks':sum(d['source_type']=='pdf' for d in self.documents),'kb_version':self.version,'chunking':{'words':380,'overlap_words':60,'scope':'page/paragraph/HTML heading'}}
    def match_entities(self, question):
        from services.knowledge_service import normalize
        normalized = ' ' + normalize(question) + ' '
        return [entity['id'] for entity in self.entities
                if any(' ' + normalize(alias) + ' ' in normalized for alias in entity['aliases'])]

    def retrieve(self,question,limit=6):
        from services.knowledge_service import normalize,tokens
        # A small auditable bilingual terminology bridge for Vietnamese queries
        # over English source PDFs; it does not inject an answer or a fact.
        search_question=question
        for phrase,english in [('hoat dong the luc','physical activity exercise'),('van dong','exercise'),
                               ('do nhay insulin','insulin sensitivity'),('ha duong huyet','hypoglycaemia'),
                               ('duong huyet','blood glucose'),('muc tieu','target')]:
            if phrase in normalize(question):search_question+=' '+english
        entities=self.match_entities(question)
        vector=self.encoder.query(search_question) if self.encoder else self.normalizer.transform(self.svd.transform(self.vectorizer.transform([search_question])))[0].tolist()
        if self.remote_vectors:
            vector_rows=self.remote_vectors.search(
                vector,30,score_threshold=None if self.encoder else .55,
                primary_sources_only=self.primary_sources_only,
            )
        else:
            vector_rows=self.store.query("""CALL db.index.vector.queryNodes('kb_chunk_vector', $k, $vector) YIELD node,score
                MATCH (v:KBVersion {id:$snapshot}) WHERE node.id IN v.chunk_ids AND score >= 0.55
                  AND (NOT $primary OR node.source_type IN ['pdf','web'])
                RETURN properties(node) AS doc,score ORDER BY score DESC""",k=30,vector=vector,snapshot=self.snapshot,primary=self.primary_sources_only)
        terms=list(dict.fromkeys(tokens(search_question)))[:30]
        query=' OR '.join('"'+re.sub(r'[^a-z0-9]','',t)+'"' for t in terms)
        fulltext=self.store.query("""CALL db.index.fulltext.queryNodes('kb_chunk_fulltext',$query,{limit:$pool}) YIELD node,score
            MATCH (v:KBVersion {id:$snapshot}) WHERE node.id IN v.chunk_ids
              AND (NOT $primary OR node.source_type IN ['pdf','web'])
            RETURN properties(node) AS doc,score ORDER BY score DESC LIMIT 30""",query=query,snapshot=self.snapshot,pool=100 if self.primary_sources_only else 30,primary=self.primary_sources_only) if query else []
        graph=self.store.query("""
            MATCH (e:Entity)<-[m:MENTIONS]-(c:Chunk),(v:KBVersion {id:$snapshot})
            WHERE e.canonical_id IN $ids AND c.id IN v.chunk_ids
              AND (m.kb_version=v.version OR (m.kb_version IS NULL AND v.embedding_model IS NULL))
              AND (NOT $primary OR c.source_type IN ['pdf','web'])
            RETURN c.id AS chunk_id,count(DISTINCT e) AS matched_entities
        """,ids=entities,snapshot=self.snapshot,primary=self.primary_sources_only) if entities else []
        graph=[row | {'doc':self.documents_by_id[row['chunk_id']]} for row in graph
               if row['chunk_id'] in self.documents_by_id]
        requested_sources=re.findall(r'\b(idf|niddk|cdc|who|vinmec)\b',question.lower())
        if requested_sources:
            def source_matches(item):
                doc=item['doc'];identity=' '.join(str(doc.get(k,'')) for k in ('title','url','document_id')).lower()
                return any(source in identity for source in requested_sources)
            vector_rows=list(filter(source_matches,vector_rows))
            fulltext=list(filter(source_matches,fulltext))
            graph=list(filter(source_matches,graph))
        graph=rank_graph(graph,set(terms))
        fused={}
        for method,weight,rows in [('vector',.45,vector_rows),('fulltext',.40,fulltext),('graph',.15,graph)]:
            for rank,item in enumerate(rows,1):
                doc=item['doc'];current=fused.setdefault(doc['id'],{**doc,'score':0.,'retrieval_methods':[]})
                current['score']+=weight/(60+rank);current['retrieval_methods'].append(method)
        # Lightweight lexical tie-break; no unmeasured cross-encoder claim.
        q=set(tokens(question));ranked=sorted(fused.values(),key=lambda x:(-x['score'],-len(q & set(tokens(x['text']))),x['id']))
        for row in ranked:row.pop('embedding',None)
        return ranked[:limit],{'entities':entities,'query':question,'requested_sources':requested_sources,'methods':['vector','fulltext','graph'],'version':self.version,'reranker':'graph relevance + RRF + lexical tie-break'}

def citation(document):
    return {key:document.get(key) for key in ('id','document_id','title','url','page','page_start','page_end','section','source_file','source_type','source_version','retrieval_methods')} | {'score':document.get('score',0)}
