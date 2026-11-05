from __future__ import annotations

import json
import os
import settings
import math
import re
import unicodedata
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
            from neo4j_store import Neo4jStore
            self.store = Neo4jStore()
            self.documents, self.graph = self.store.load()
        self.by_id = {d["id"]: d for d in self.documents}
        self.doc_tokens = [tokens(d["title"] + " " + d["text"]) for d in self.documents]
        df = Counter(); [df.update(set(row)) for row in self.doc_tokens]
        n = len(self.documents)
        self.idf = {t: math.log(1 + (n - count + .5) / (count + .5)) for t, count in df.items()}
        self.alias, self.adj = {}, defaultdict(list)
        for edge in self.graph:
            s, o = normalize(edge["subject"]), normalize(edge["object"])
            self.alias[s], self.alias[o] = edge["subject"], edge["object"]
            self.adj[s].append((o, edge)); self.adj[o].append((s, edge))

    def retrieve(self, question: str, top_k: int = 3) -> list[dict]:
        query = tokens(question); scored = []
        for doc, row in zip(self.documents, self.doc_tokens):
            counts = Counter(row); dl = max(len(row), 1); score = 0.0
            for term in query:
                tf = counts[term]
                if tf: score += self.idf.get(term, 0) * tf * 2.5 / (tf + 1.5 * (.25 + .75 * dl / 70))
            if score: scored.append((score, doc))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [{**d, "score": round(s, 5)} for s, d in scored[:top_k]]

    def graph_paths(self, question: str, hops: int = 2) -> list[dict]:
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
                    "status": "insufficient_evidence"}
        q = set(tokens(question)); selected = []
        for doc in docs:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", doc["text"]) if s.strip()]
            sentence = max(sentences, key=lambda s: len(q & set(tokens(s)))) if sentences else doc["text"]
            selected.append(sentence)
        return {"answer": " ".join(selected[:2]),
                "citations": [{"id": d["id"], "title": d["title"], "url": d["url"], "score": d["score"]} for d in docs],
                "paths": paths, "status": "supported"}
