"""Build a source-versioned PDF/HTML/JSON KB, Cypher seed and Neo4j indexes."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

import joblib
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'knowledge'/'hybrid'

def digest(value):
    return hashlib.sha256(value if isinstance(value,bytes) else value.encode()).hexdigest()

class ArticleParser(HTMLParser):
    def __init__(self,content_class=None):
        super().__init__();self.content_class=content_class;self.content_depth=0;self.blocks=[];self.parts=[];self.skip=0;self.heading='';self.tag=''
    def handle_starttag(self,tag,attrs):
        if self.content_class:
            if tag=='div' and (self.content_depth or self.content_class in (dict(attrs).get('class') or '').split()):
                self.content_depth+=1
            if not self.content_depth:return
        if tag in ('script','style','nav','footer','header'):self.skip+=1
        if tag in ('p','li','h1','h2','h3','h4') and not self.skip:self.parts=[];self.tag=tag
    def handle_data(self,data):
        if not self.skip and (not self.content_class or self.content_depth):self.parts.append(data)
    def handle_endtag(self,tag):
        if self.content_class:
            if not self.content_depth:return
            if tag=='div':self.content_depth-=1
        if tag in ('script','style','nav','footer','header'):self.skip=max(0,self.skip-1)
        if tag==self.tag and not self.skip:
            text=' '.join(' '.join(self.parts).split())
            if tag.startswith('h'):self.heading=text
            elif len(text.split())>=8:self.blocks.append((self.heading,text))
            self.parts=[];self.tag=''

def chunks(text,size=380,overlap=60):
    # Word budget approximates 450-600 English tokens; preserve paragraph boundaries.
    paragraphs=[re.sub(r'\s+',' ',p).strip() for p in re.split(r'\n\s*\n',text)]
    paragraphs=[p for p in paragraphs if p]
    buffer=[]
    for p in paragraphs:
        words=p.split()
        if buffer and len(buffer)+len(words)>size:
            yield ' '.join(buffer);buffer=buffer[-overlap:]
        buffer+=words
        while len(buffer)>size:
            yield ' '.join(buffer[:size]);buffer=buffer[size-overlap:]
    if len(buffer)>=12:yield ' '.join(buffer)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fetch-web',action='store_true');parser.add_argument('--ingest',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=OUT)
    parser.add_argument('--semantic',action='store_true',help='Build multilingual E5 vectors for Qdrant')
    parser.add_argument('--web-sources',type=Path,default=ROOT/'knowledge/web_sources.json')
    parser.add_argument('--fetch-missing-web',action='store_true')
    parser.add_argument('--reuse-vectors',type=Path)
    args=parser.parse_args()
    import settings
    import os
    if args.semantic and args.ingest and os.environ.get('HYBRID_VECTOR_BACKEND')!='qdrant':
        parser.error('--semantic --ingest requires HYBRID_VECTOR_BACKEND=qdrant')
    output=args.output_dir
    output.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(exist_ok=True);raw=OUT/'web';raw.mkdir(exist_ok=True)
    now=datetime.now(timezone.utc).isoformat();documents=[];rows=[];errors=[]
    urls=json.loads((ROOT/'knowledge/vector_artifacts/manifest.json').read_text(encoding='utf-8'))['pdf_sources']
    def add_document(source_id,title,url,content,kind,blocks,organization='',local_path=''):
        sha=digest(content);docid=source_id+'_'+sha[:12]
        document={'id':docid,'source_id':source_id,'title':title,'organization':organization,'source_url':url,'sha256':sha,'version':sha[:12],'source_type':kind,'local_path':local_path,'ingested_at':now,'published_at':None,'language':'vi' if kind=='curated_summary' else 'en','ingestion_status':'parsed'}
        documents.append(document)
        for page,section,text in blocks:
            for index,part in enumerate(chunks(text)):
                cid='chunk_'+digest(f'{docid}|{page}|{section}|{index}|{part}')[:24]
                rows.append({'id':cid,'document_id':docid,'title':title,'url':url,'text':part,'page':page,'page_start':page,'page_end':page,'section':section,'source_file':Path(local_path).name if kind=='pdf' else None,'source_type':kind,'source_version':sha[:12]})
    for source in urls:
        path=ROOT/'knowledge/pdfs'/source['file'];reader=PdfReader(path)
        blocks=[(i+1,'PDF page '+str(i+1),p.extract_text() or '') for i,p in enumerate(reader.pages)]
        add_document('pdf_'+path.stem,path.stem,source['url'],path.read_bytes(),'pdf',blocks,'IDF' if 'IDF' in path.name else 'NIDDK',local_path=path.relative_to(ROOT).as_posix())
    for source in json.loads(args.web_sources.read_text(encoding='utf-8')):
        path=raw/(source['id']+'.html')
        try:
            if args.fetch_web or (args.fetch_missing_web and not path.exists()):
                req=Request(source['url'],headers={'User-Agent':'DiaAgents academic source ingestion/1.0'})
                with urlopen(req,timeout=40) as response:content=response.read(8_000_000)
                path.write_bytes(content)
            content=path.read_bytes()
            host=urlsplit(source['url']).hostname
            article=ArticleParser('detail-content' if host in {'vinmec.com','www.vinmec.com'} else None)
            article.feed(content.decode('utf-8',errors='replace'))
            if not article.blocks:raise ValueError('No article blocks extracted')
            before=len(rows)
            add_document(source['id'],source['title'],source['url'],content,'web',[(None,h,t) for h,t in article.blocks],source['organization'],path.relative_to(ROOT).as_posix())
            documents[-1]['language']=source.get('language','en')
            if len(rows)==before:raise ValueError('No searchable article chunks extracted')
        except Exception as exc:errors.append({'source':source['id'],'error':type(exc).__name__,'detail':str(exc)[:180]})
    if args.fetch_missing_web and errors:
        raise RuntimeError('Web source preparation failed: '+', '.join(e['source'] for e in errors))
    corpus=json.loads((ROOT/'knowledge/corpus.json').read_text(encoding='utf-8'))
    for d in corpus:
        add_document('summary_'+d['id'],d['title'],d['url'],d['text'],'curated_summary',[(None,d['title'],d['text'])],d.get('organization',''))
    entities={};facts=[];mentions=[]
    edges=json.loads((ROOT/'knowledge/graph.json').read_text(encoding='utf-8'))
    from services.knowledge_service import normalize
    # Use the existing concept names to link MENTIONS from source chunks.
    for edge in edges:
        for name in (edge['subject'],edge['object']):
            eid='entity_'+digest(normalize(name))[:20]
            entities[eid]={'canonical_id':eid,'name':name,'aliases':[name],'type':'Concept'}
    from knowledge.retrieval_terms import concepts
    for concept in concepts():
        aliases=concept['aliases']
        name=aliases[0]
        eid='entity_'+digest(normalize(name))[:20]
        entities[eid]={'canonical_id':eid,'name':name,'aliases':aliases,'type':'Concept'}
    for row in rows:
        norm=' '+normalize(row['text'])+' '
        for entity in entities.values():
            if any(' '+normalize(alias)+' ' in norm for alias in entity['aliases']):mentions.append({'chunk_id':row['id'],'entity_id':entity['canonical_id']})
    folder=ROOT/'knowledge/vector_artifacts'
    vectorizer=joblib.load(folder/'tfidf_vectorizer.joblib');svd=joblib.load(folder/'lsa_svd.joblib');normalizer=joblib.load(folder/'normalizer.joblib')
    vectors=normalizer.transform(svd.transform(vectorizer.transform([r['text'] for r in rows])))
    for row,vector in zip(rows,vectors):row['embedding']=vector.tolist()
    embedding_model='lsa-128'
    semantic_vectors=None
    if args.semantic:
        from services.semantic_embedding import E5Encoder
        embedding_model=E5Encoder.identifier
        cached={}
        if args.reuse_vectors:
            previous=json.loads(args.reuse_vectors.read_text(encoding='utf-8'))
            if previous['embedding']==embedding_model:
                cached={(r['id'],r['text']):v for r,v in zip(previous['chunks'],previous['semantic_vectors'],strict=True)}
        keys=[(r['id'],r['text']) for r in rows]
        missing=[key for key in keys if key not in cached]
        print(f'E5: reuse {len(keys)-len(missing)} vectors, encode {len(missing)} new chunks',flush=True)
        if missing:
            cached.update(zip(missing,E5Encoder().passages([text for _,text in missing]),strict=True))
        semantic_vectors=[cached[key] for key in keys]
    version=digest(json.dumps({
        'documents':[(d['id'],d['source_url']) for d in documents],
        'chunks':[r['id'] for r in rows], 'facts':facts,
        'entities':list(entities.values()), 'embedding_model':embedding_model,
    },sort_keys=True,ensure_ascii=False))
    bundle={'version':version,'documents':documents,'chunks':rows,'entities':list(entities.values()),'facts':facts,'mentions':mentions,'errors':errors,'embedding':embedding_model,'created_at':now}
    if semantic_vectors is not None:bundle['semantic_vectors']=semantic_vectors
    (output/'kb_bundle.json').write_text(json.dumps(bundle,ensure_ascii=False),encoding='utf-8')
    (output/'source_registry.json').write_text(json.dumps(documents,ensure_ascii=False,indent=2),encoding='utf-8')
    from services.hybrid_kb import seed_statements,ingest
    schema=(ROOT/'knowledge/DB_diabet.cypher').read_text(encoding='utf-8').split('// The Python ingestion')[0]
    seed=schema+'\n'+ '\n'.join(seed_statements(bundle))
    (output/'DB_diabet_seed.cypher').write_text(seed,encoding='utf-8')
    if args.ingest:ingest(bundle)
    print(json.dumps({'version':version,'documents':len(documents),'chunks':len(rows),'entities':len(entities),'facts':len(facts),'web_errors':errors,'ingested':args.ingest}))

if __name__=='__main__':main()
