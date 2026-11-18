"""Versioned Qdrant Cloud vectors for the SAME chunks used by Neo4j GraphRAG."""
import os,re,uuid
from urllib.parse import urlparse
from qdrant_client import QdrantClient,models

def cloud_client(url=None,api_key=None):
    url=url or os.environ.get('QDRANT_URL','')
    key=api_key or os.environ.get('QDRANT_API_KEY','')
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('QDRANT_URL must be an HTTPS cluster URL without embedded credentials')
    if not key:raise ValueError('QDRANT_API_KEY is required')
    return QdrantClient(url=url,api_key=key,timeout=30)

def collection_name(kind,version,prefix=None):
    prefix=prefix or os.environ.get('QDRANT_COLLECTION_PREFIX','diaguard')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',prefix):raise ValueError('Invalid collection prefix')
    if kind not in {'hybrid','legacy'} or not re.fullmatch(r'[a-f0-9]{8,64}',version):raise ValueError('Invalid collection version')
    return f'{prefix}_{kind}_{version[:20]}'

def upload(client,name,rows,vectors,version):
    """Idempotent, version-named collection; no delete/recreate operations."""
    if len(rows)!=len(vectors) or not rows:raise ValueError('Rows and vectors must be nonempty and aligned')
    dimension=len(vectors[0])
    if not client.collection_exists(name):
        client.create_collection(name,vectors_config=models.VectorParams(size=dimension,distance=models.Distance.COSINE))
    else:
        info=client.get_collection(name)
        if info.config.params.vectors.size!=dimension or info.config.params.vectors.distance!=models.Distance.COSINE:
            raise ValueError('Existing collection vector configuration differs; refusing to overwrite')
    client.create_payload_index(name,'kb_version',models.PayloadSchemaType.KEYWORD,wait=True)
    if all('source_type' in row for row in rows):
        client.create_payload_index(name,'source_type',models.PayloadSchemaType.KEYWORD,wait=True)
    for start in range(0,len(rows),64):
        points=[]
        for row,vector in zip(rows[start:start+64],vectors[start:start+64]):
            payload={k:v for k,v in row.items() if k!='embedding'}
            payload['kb_version']=version
            points.append(models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL,row['id'])),vector=list(vector),payload=payload))
        client.upsert(name,points,wait=True)
    if client.count(name,exact=True).count!=len(rows):raise RuntimeError('Remote collection count does not match source')
    # Verify every payload and vector, not only the total count.
    for start in range(0,len(rows),64):
        batch=rows[start:start+64]
        records=client.retrieve(name,ids=[str(uuid.uuid5(uuid.NAMESPACE_URL,r['id'])) for r in batch],with_payload=True,with_vectors=True)
        by_id={r.payload['id']:r for r in records}
        for row,vector in zip(batch,vectors[start:start+64]):
            record=by_id.get(row['id'])
            expected={k:v for k,v in row.items() if k!='embedding'}|{'kb_version':version}
            if not record or record.payload!=expected:raise RuntimeError('Remote payload verification failed')
            # Cosine collections normalize stored vectors; compare direction.
            import numpy as np
            a=np.asarray(record.vector);b=np.asarray(vector)
            if not np.allclose(a/max(np.linalg.norm(a),1e-12),b/max(np.linalg.norm(b),1e-12),atol=2e-5):
                raise RuntimeError('Remote vector verification failed')

class HybridQdrant:
    def __init__(self,version):
        self.client=cloud_client();self.version=version;self.collection=collection_name('hybrid',version)
        if not self.client.collection_exists(self.collection):raise RuntimeError('Hybrid cloud collection not migrated for current Neo4j KB version')
    def search(self,vector,limit=30,score_threshold=.55,primary_sources_only=False):
        filters=[models.FieldCondition(key='kb_version',match=models.MatchValue(value=self.version))]
        if primary_sources_only:
            filters.append(models.FieldCondition(key='source_type',match=models.MatchAny(any=['pdf','web'])))
        result=self.client.query_points(self.collection,query=vector,limit=limit,with_payload=True,score_threshold=score_threshold,
            query_filter=models.Filter(must=filters))
        return [{'doc':p.payload,'score':p.score} for p in result.points]

def sync_bundle(bundle):
    client=cloud_client()
    try:
        upload(client,collection_name('hybrid',bundle['version']),bundle['chunks'],
               bundle.get('semantic_vectors') or [r['embedding'] for r in bundle['chunks']],bundle['version'])
    finally:client.close()
