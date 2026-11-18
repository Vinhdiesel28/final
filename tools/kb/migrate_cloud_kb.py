"""Copy local KB + Qdrant to cloud, verify, then optionally switch .env.

No deletes. No key/password output. Source remains intact.
"""
import argparse,hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
import settings
from services.neo4j_store import Neo4jStore
from services.qdrant_backend import cloud_client,collection_name,upload
from services.hybrid_kb import ingest

REQUIRED=('NEO4J_URI','NEO4J_USER','NEO4J_PASSWORD','QDRANT_URL','QDRANT_API_KEY')

def read_config(path,require_neo4j=True):
    values={}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:continue
            key,value=line.split('=',1);values[key.strip()]=value.strip().strip('"').strip("'")
    required=REQUIRED if require_neo4j else ('QDRANT_URL','QDRANT_API_KEY')
    missing=[k for k in required if not values.get(k) or values[k].startswith('<')]
    if missing:raise ValueError('Missing cloud settings: '+', '.join(missing))
    for key,scheme in [('NEO4J_URI','neo4j+s'),('QDRANT_URL','https')]:
        if key=='NEO4J_URI' and not require_neo4j:continue
        parsed=urlparse(values[key]);host=parsed.hostname or ''
        if parsed.scheme!=scheme or not host or host in {'localhost','127.0.0.1','::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(key+' must be a TLS cloud endpoint, not localhost or an embedded credential URL')
    return values

def export_hybrid(store):
    current=store.query("MATCH (k:KBVersion {id:'current'}) RETURN k.version AS version,k.chunk_ids AS chunks,k.fact_ids AS facts,k.embedding_model AS embedding")
    if not current:raise RuntimeError('Local Hybrid KB version missing')
    version=current[0]
    if version['embedding'] not in (None,'lsa-128'):
        raise RuntimeError('Stage a semantic KB from its bundle to preserve E5 vectors')
    queries={
      'chunks':("MATCH (c:Chunk) WHERE c.id IN $ids RETURN properties(c) AS row ORDER BY c.id",version['chunks']),
      'documents':("MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE c.id IN $ids RETURN DISTINCT properties(d) AS row ORDER BY row.id",version['chunks']),
      'facts':("MATCH (f:Fact) WHERE f.id IN $ids RETURN properties(f) AS row ORDER BY f.id",version['facts']),
      'entities':("MATCH (e:Entity) RETURN properties(e) AS row ORDER BY e.canonical_id",[]),
      'mentions':("MATCH (k:KBVersion {id:'current'}),(c:Chunk)-[m:MENTIONS]->(e:Entity) WHERE c.id IN $ids AND (m.kb_version=k.version OR (m.kb_version IS NULL AND k.embedding_model IS NULL)) RETURN DISTINCT {chunk_id:c.id,entity_id:e.canonical_id} AS row ORDER BY row.chunk_id,row.entity_id",version['chunks'])}
    result={'version':version['version']}
    for name,(query,ids) in queries.items():result[name]=[r['row'] for r in store.query(query,ids=ids)]
    if len(result['chunks'])!=len(version['chunks']) or len(result['facts'])!=len(version['facts']):raise RuntimeError('Incomplete source KB')
    return result

def local_legacy_vectors():
    from qdrant_client import QdrantClient
    manifest=json.loads((ROOT/'knowledge/vector_artifacts/manifest.json').read_text(encoding='utf-8'))
    client=QdrantClient(path=str(ROOT/'knowledge/qdrant'))
    try:
        rows=[];offset=None
        while True:
            batch,offset=client.scroll(manifest['collection'],limit=128,offset=offset,with_payload=True,with_vectors=True)
            rows.extend((r.payload,r.vector) for r in batch)
            if offset is None:break
        rows.sort(key=lambda r:r[0]['id'])
        version=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return [r[0] for r in rows],[r[1] for r in rows],version
    finally:client.close()

def activate(path,values):
    existing=path.read_text(encoding='utf-8') if path.exists() else ''
    lines=[];remaining=dict(values)
    for line in existing.splitlines():
        key=line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
        if key in values:
            if key in remaining:lines.append(key+'='+remaining.pop(key))
        else:lines.append(line)
    lines.extend(k+'='+v for k,v in remaining.items())
    staged=path.with_name('.env.cloud-activation.tmp')
    staged.write_text('\n'.join(lines)+'\n',encoding='utf-8');staged.replace(path)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,default=ROOT/'.env.cloud')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--activate',action='store_true')
    parser.add_argument('--qdrant-only',action='store_true')
    parser.add_argument('--set-neo4j-uri',help='Save a user-supplied connection URI without changing existing passwords')
    args=parser.parse_args()
    if args.activate and not args.apply:parser.error('--activate requires --apply')
    if args.activate and args.qdrant_only:parser.error('Cannot activate a partial migration')
    stage='configuration';source=target=qdrant=None
    try:
        if args.set_neo4j_uri:
            uri=urlparse(args.set_neo4j_uri)
            if uri.scheme!='neo4j+s' or not uri.hostname or not uri.hostname.endswith('.databases.neo4j.io') or uri.username or uri.password or uri.query or uri.fragment:
                raise ValueError('Expected an Aura TLS connection URI')
            activate(args.config,{'NEO4J_URI':args.set_neo4j_uri})
        config=read_config(args.config,require_neo4j=not args.qdrant_only)
        stage='connect_cloud'
        if not args.qdrant_only:
            target=Neo4jStore(config['NEO4J_URI'],config['NEO4J_USER'],config['NEO4J_PASSWORD'],config.get('NEO4J_DATABASE','neo4j'))
        qdrant=cloud_client(config['QDRANT_URL'],config['QDRANT_API_KEY']);qdrant.get_collections()
        if not args.apply:
            print(json.dumps({'status':'cloud_connections_verified','next':'Run --apply --activate to copy, verify and switch'}));return
        stage='export_local'
        # Source configuration stays untouched until all remote verification passes.
        source=Neo4jStore();documents,edges=source.load();bundle=export_hybrid(source)
        if not args.qdrant_only and urlparse(os.environ.get('NEO4J_URI','')).hostname==urlparse(config['NEO4J_URI']).hostname:
            raise RuntimeError('Source and destination must differ; already migrated or incorrect source configuration')
        legacy_rows,legacy_vectors,legacy_version=local_legacy_vectors()
        prefix=config.get('QDRANT_COLLECTION_PREFIX','diaguard')
        hybrid_name=collection_name('hybrid',bundle['version'],prefix);legacy_name=collection_name('legacy',legacy_version,prefix)
        stage='upload_qdrant'
        upload(qdrant,hybrid_name,bundle['chunks'],[r['embedding'] for r in bundle['chunks']],bundle['version'])
        upload(qdrant,legacy_name,legacy_rows,legacy_vectors,legacy_version)
        if args.qdrant_only:
            receipt={'status':'verified','activated':False,'kb_version':bundle['version'],
                'created_at':datetime.now(timezone.utc).isoformat(),
                'hybrid_collection':hybrid_name,'hybrid_vectors':len(bundle['chunks']),
                'legacy_collection':legacy_name,'legacy_vectors':len(legacy_rows),'source_preserved':True}
            (ROOT/'results/qdrant_cloud_migration_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            print(json.dumps(receipt));return 0
        stage='upload_neo4j'
        target.ingest(documents,edges);ingest(bundle,store=target)
        stage='verify_neo4j'
        remote=export_hybrid(target)
        if remote!=bundle or target.load()!=(documents,edges):raise RuntimeError('Neo4j source/target verification mismatch')
        stage='verify_search'
        hit=qdrant.query_points(hybrid_name,query=bundle['chunks'][0]['embedding'],limit=1,with_payload=True)
        if not hit.points or hit.points[0].score<.99:raise RuntimeError('Qdrant search verification failed')
        values={k:config[k] for k in REQUIRED}
        values.update(NEO4J_DATABASE=config.get('NEO4J_DATABASE','neo4j'),KNOWLEDGE_BACKEND='neo4j',HYBRID_KB='enabled',
            HYBRID_VECTOR_BACKEND='qdrant',QDRANT_COLLECTION_PREFIX=prefix,QDRANT_LEGACY_COLLECTION=legacy_name)
        receipt={'status':'verified','activated':False,'created_at':datetime.now(timezone.utc).isoformat(),
            'hosts':{k:urlparse(config[k]).hostname for k in ('NEO4J_URI','QDRANT_URL')},
            'kb_version':bundle['version'],'neo4j':{k:len(bundle[k]) for k in ('documents','chunks','entities','facts','mentions')},
            'qdrant':{'hybrid_collection':hybrid_name,'hybrid_vectors':len(bundle['chunks']),'legacy_collection':legacy_name,'legacy_vectors':len(legacy_rows)},
            'source_preserved':True}
        if args.activate:stage='activate';activate(ROOT/'.env',values);receipt['activated']=True
        (ROOT/'results/cloud_migration_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(receipt,ensure_ascii=True))
    except Exception as exc:
        # Credentials may appear in vendor exception messages. Never print those.
        message=str(exc) if stage=='configuration' else 'Cloud migration did not complete; local configuration remains unless activation finished.'
        code=getattr(exc,'code',None)
        print(json.dumps({'status':'not_completed','stage':stage,'error_type':type(exc).__name__,
            'http_status':getattr(exc,'status_code',None),'database_code':code if isinstance(code,str) and code.startswith('Neo.') else None,
            'detail':message},ensure_ascii=True));return 1
    finally:
        for store in (source,target):
            if store is not None:store.driver.close()
        if qdrant is not None:qdrant.close()
    return 0

if __name__=='__main__':sys.exit(main())
