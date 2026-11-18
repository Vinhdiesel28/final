from services.hybrid_kb import citation
from services.knowledge_service import normalize
from knowledge.retrieval_terms import search_query
import math
import re
from collections import Counter
from knowledge.retrieval_terms import search_terms

def retrieve(p, *, knowledge, requested_sources):
    candidates={};analysis=[]
    for query in p['queries'][:2]:
        # Source constraints are passed into each branch, not merely
        # written into the answer after unrelated sources are retrieved.
        constrained=search_query(query)+' '+' '.join(requested_sources)
        if getattr(knowledge,'hybrid',None):
            rows,details=knowledge.hybrid.retrieve(constrained,10)
        else:
            rows=knowledge.retrieve(constrained,10);details={'backend':'legacy_retriever'}
        analysis.append(details)
        for rank,row in enumerate(rows,1):
            item=candidates.setdefault(row['id'],{**row,'fusion':0.})
            item['fusion']+=1/(60+rank)
    rows=sorted(candidates.values(),key=lambda d:-d['fusion'])
    requested=requested_sources
    if requested:
        aliases={'ada':['diabetes.org','ada'],'idf':['idf'],'niddk':['niddk'],'cdc':['cdc'],
                 'bo y te':['moh.gov.vn','kcb.vn','byt'],'byt':['moh.gov.vn','kcb.vn','byt']}
        needles=[term for name in requested for term in aliases.get(normalize(name),[normalize(name)])]
        rows=[r for r in rows if any(t in normalize(' '.join(str(r.get(k,'')) for k in ('title','url','document_id'))) or t in str(r.get('url','')).lower() for t in needles)]
    evidence=[{'evidence_id':row['id'],'text':row['text'],'source':citation(row)} for row in rows[:8]]
    return {'evidence':evidence,'citations':[e['source'] for e in evidence],
            'paths':[],
            'retrieval':getattr(knowledge,'vector_metadata',{}),'query_analysis':analysis,
            'answer':'','status':'supported' if evidence else 'insufficient_evidence',
            'summary':f"Truy xuất {len(evidence)} bằng chứng từ {len(p['queries'][:2])} truy vấn"}



class EvidenceReader:
    def __init__(self, documents):
        self.document_count = max(1, len(documents))
        self.term_documents = Counter(t for doc in documents for t in set(search_terms(doc['text'])))

    def read_evidence(self, p, *, queries):
        # Keep intact sentence context, provenance and high-relevance passages.
        # This is a preparation handler, not a claim of semantic verification.
        query=set(search_terms(' '.join(queries)))-{'what','does','how','which','according','guidelines','recommendations','say','about','are','for','and','with','that','this','from','test','tests'}
        weights={t:math.log(1+(self.document_count+1)/(self.term_documents[t]+1)) for t in query}
        def relevance(text):
            return sum(weights[t] for t in query & set(search_terms(text)))
        prepared=[]
        for evidence in p['evidence']:
            text=evidence['text']
            if len(text)>800:
                # Slice original text, preserving exact whitespace for quotes.
                boundaries=[0]+[m.end() for m in re.finditer(r'(?<=[.!?])\s+',text)]
                windows=[text[start:start+800] for start in boundaries]
                text=max(windows,key=relevance)
            heading=' '.join(str(evidence['source'].get(k) or '') for k in ('title','section'))
            prepared.append({**evidence,'text':text,'reader_relevance':round(relevance(text)+.5*relevance(heading),4)})
        # Relevance first; source type breaks ties rather than promoting an
        # unrelated raw PDF above a directly relevant source.
        prepared.sort(key=lambda e:(-e['reader_relevance'],e['source'].get('source_type')=='curated_summary'))
        return {'evidence':prepared[:4],'summary':f"Xếp hạng theo độ phủ thuật ngữ và IDF, đọc {min(4,len(prepared))} đoạn, giữ nguồn và trang"}

def calculate_statistics(p, *, services):
    return services.statistics(p['question'])

def handle(payload, *, knowledge, services, reader, queries, requested_sources):
    action = payload.get('action', 'retrieve')
    if action == 'read':
        return reader.read_evidence(payload, queries=queries)
    if action == 'statistics':
        return calculate_statistics(payload, services=services)
    return retrieve(payload, knowledge=knowledge, requested_sources=requested_sources)
