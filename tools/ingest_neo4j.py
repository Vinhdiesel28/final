import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from neo4j_store import Neo4jStore
if __name__=='__main__':
    store=Neo4jStore()
    store.ingest(json.loads((ROOT/'knowledge/corpus.json').read_text(encoding='utf-8')),
                 json.loads((ROOT/'knowledge/graph.json').read_text(encoding='utf-8')))
    documents,edges=store.load()
    print({'backend':'neo4j','documents':len(documents),'edges':len(edges)})
