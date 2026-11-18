from __future__ import annotations

import json
import os
import settings
import math
import re
import unicodedata
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STOP = {"va", "la", "cua", "co", "cho", "mot", "nhung", "the", "nao", "gi", "duoc", "trong", "toi", "ve"}


def normalize(text: str) -> str:
    text = text.lower().replace("đ", "d")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t not in STOP and len(t) > 1]


class KnowledgeService:
    def __init__(self):
        self.documents = json.loads((ROOT / "knowledge/corpus.json").read_text(encoding="utf-8"))
        self.graph = json.loads((ROOT / "knowledge/graph.json").read_text(encoding="utf-8"))
        self.backend = os.environ.get('KNOWLEDGE_BACKEND', 'json')
        self.store = None
        if self.backend == 'neo4j':
            from services.neo4j_store import Neo4jStore
            self.store = Neo4jStore()
            self.documents, self.graph = self.store.load()
        self.vector_store = None
        self.hybrid = None
        self.vector_metadata = {"backend": "disabled", "embedding_model": None,
                                "total_vectors": 0, "pdf_chunks": 0}
        if self.store and os.environ.get('HYBRID_KB','enabled') == 'enabled':
            from services.hybrid_kb import HybridKB
            snapshot=os.environ.get('HYBRID_KB_SNAPSHOT') or None
            if snapshot or self.store.query("MATCH (k:KBVersion {id:'current'}) RETURN k.version AS version"):
                self.hybrid=HybridKB(self.store,version=snapshot)
                self.vector_metadata=self.hybrid.metadata()
        if not self.hybrid and os.environ.get("VECTOR_BACKEND", "qdrant").lower() != "disabled":
            try:
                from services.vector_store import VectorStore
                if VectorStore.available():
                    self.vector_store = VectorStore()
                    self.vector_metadata = self.vector_store.metadata()
            except Exception as exc:
                self.vector_metadata = {"backend": "unavailable", "embedding_model": None,
                                        "total_vectors": 0, "pdf_chunks": 0,
                                        "error": type(exc).__name__}
        self.by_id = {d["id"]: d for d in self.documents}
        if self.hybrid:
            self.by_id.update({d['id']:d for d in self.hybrid.documents})
        if self.vector_store:
            for document in self.vector_store.documents:
                self.by_id.setdefault(document["id"], document)
        self.doc_tokens = [tokens(d["title"] + " " + d["text"]) for d in self.documents]
        df = Counter(); [df.update(set(row)) for row in self.doc_tokens]
        n = len(self.documents)
        self.idf = {t: math.log(1 + (n - count + .5) / (count + .5)) for t, count in df.items()}
        self.alias, self.adj = {}, defaultdict(list)
        for edge in self.graph:
            s, o = normalize(edge["subject"]), normalize(edge["object"])
            self.alias[s], self.alias[o] = edge["subject"], edge["object"]
            self.adj[s].append((o, edge)); self.adj[o].append((s, edge))

    def retrieve_bm25(self, question: str, top_k: int = 5) -> list[dict]:
        query = tokens(question); scored = []
        for doc, row in zip(self.documents, self.doc_tokens):
            counts = Counter(row); dl = max(len(row), 1); score = 0.0
            for term in query:
                tf = counts[term]
                if tf: score += self.idf.get(term, 0) * tf * 2.5 / (tf + 1.5 * (.25 + .75 * dl / 70))
            if score: scored.append((score, doc))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [{**d, "score": round(s, 5), "bm25_score": round(s, 5)} for s, d in scored[:top_k]]

    def retrieve(self, question: str, top_k: int = 3) -> list[dict]:
        """Reciprocal-rank fusion of BM25 documents and Qdrant vector chunks."""
        if self.hybrid:
            rows,_=self.hybrid.retrieve(question,top_k)
            return rows
        keyword = self.retrieve_bm25(question, max(top_k, 5))
        vector = self.vector_store.search(question, max(top_k, 5)) if self.vector_store else []
        if not vector:
            return keyword[:top_k]
        merged = {}
        for source, weight in ((keyword, .45), (vector, .55)):
            for rank, document in enumerate(source, start=1):
                key = document["id"]
                current = merged.setdefault(key, {**document, "hybrid_score": 0.0})
                current.update({k: v for k, v in document.items() if k not in current})
                current["hybrid_score"] += weight / (60 + rank)
        rows = sorted(merged.values(), key=lambda row: (-row["hybrid_score"], row["id"]))
        for row in rows:
            row["score"] = round(row["hybrid_score"], 7)
        return rows[:top_k]

    def graph_paths(self, question: str, hops: int = 2) -> list[dict]:
        if self.hybrid:
            return []
        nq = " " + normalize(question) + " "; seeds = [n for n in self.alias if f" {n} " in nq]
        if self.store:
            return self.store.paths([self.alias[s] for s in seeds])
        queue = deque((s, 0) for s in seeds); seen = set(seeds); paths = []
        while queue:
            node, depth = queue.popleft()
            if depth >= hops: continue
            for nxt, edge in self.adj[node]:
                paths.append({**edge, "hop": depth + 1})
                if nxt not in seen: seen.add(nxt); queue.append((nxt, depth + 1))
        return paths[:16]

    def answer(self, question: str) -> dict:
        if self.hybrid:
            from services.hybrid_kb import citation
            docs,analysis=self.hybrid.retrieve(question,6)
            identifiers=[t.lower() for t in re.findall(r'\b[a-zA-Z0-9_-]{7,}\b',question)
                         if re.search(r'[a-zA-Z]',t) and re.search(r'\d',t)]
            if identifiers:
                docs=[d for d in docs if all(t in (d['text']+' '+d['title']).lower() for t in identifiers)]
            # Preserve exact quotes for the existing evidence repair loop.
            candidates=[];q=set(tokens(question))
            for doc in docs:
                for sentence in re.split(r'(?<=[.!?])\s+',doc['text']):
                    overlap=len(q & set(tokens(sentence)))
                    if overlap:candidates.append((overlap,sentence,doc))
            candidates.sort(key=lambda x:-x[0]);selected=candidates[:2]
            return {'answer':' '.join(x[1] for x in selected) or 'Kho tri thức không có đủ bằng chứng để trả lời câu hỏi này.',
                    'citations':[citation(d) for d in docs] if selected else [],
                    'evidence':[{'evidence_id':d['id'],'text':d['text'],'source':citation(d)} for d in docs] if selected else [],
                    'paths':self.graph_paths(question),'status':'supported' if selected else 'insufficient_evidence',
                    'retrieval':self.vector_metadata,'query_analysis':analysis}
        docs = self.retrieve(question); paths = self.graph_paths(question)
        known = {d['id'] for d in docs}
        for edge in paths:
            key = edge['evidence']
            if key in self.by_id and key not in known:
                docs.append({**self.by_id[key], 'score':0.0})
                known.add(key)
        docs = docs[:5]
        if not docs:
            return {"answer": "Kho tri thức hiện tại không có đủ bằng chứng để trả lời.", "citations": [], "paths": paths,
                    "status": "insufficient_evidence", "retrieval": self.vector_metadata}
        q = set(tokens(question)); selected = []
        for doc in docs:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", doc["text"]) if s.strip()]
            sentence = max(sentences, key=lambda s: len(q & set(tokens(s)))) if sentences else doc["text"]
            selected.append(sentence)
        return {"answer": " ".join(selected[:2]),
                "citations": [{"id": d["id"], "title": d["title"], "url": d["url"], "score": d["score"],
                               "source_type": d.get("source_type", "curated_corpus"),
                               "page": d.get("page"), "vector_score": d.get("vector_score")}
                              for d in docs],
                "paths": paths, "status": "supported", "retrieval": self.vector_metadata}
