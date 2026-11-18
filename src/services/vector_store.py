"""Persistent Qdrant retrieval over lightweight LSA document embeddings."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path

import joblib
from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "knowledge" / "vector_artifacts"
STORE_DIR = ROOT / "knowledge" / "qdrant"


class VectorStore:
    def __init__(self):
        self.manifest = json.loads((ARTIFACT_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.vectorizer = joblib.load(ARTIFACT_DIR / "tfidf_vectorizer.joblib")
        self.svd = joblib.load(ARTIFACT_DIR / "lsa_svd.joblib")
        self.normalizer = joblib.load(ARTIFACT_DIR / "normalizer.joblib")
        self.documents = json.loads((ARTIFACT_DIR / "chunks.json").read_text(encoding="utf-8"))
        self.remote=bool(os.environ.get('QDRANT_URL'))
        if self.remote:
            from services.qdrant_backend import cloud_client
            self.client=cloud_client()
            self.collection=os.environ['QDRANT_LEGACY_COLLECTION']
        else:
            self.client = QdrantClient(path=str(STORE_DIR))
            self.collection = self.manifest["collection"]
        atexit.register(self.close)

    @classmethod
    def available(cls) -> bool:
        required = [ARTIFACT_DIR / "manifest.json", ARTIFACT_DIR / "tfidf_vectorizer.joblib",
                    ARTIFACT_DIR / "lsa_svd.joblib", ARTIFACT_DIR / "normalizer.joblib",
                    ARTIFACT_DIR / "chunks.json"]
        storage=bool(os.environ.get('QDRANT_URL') and os.environ.get('QDRANT_API_KEY') and os.environ.get('QDRANT_LEGACY_COLLECTION')) or STORE_DIR.exists()
        return storage and all(path.exists() for path in required)

    def embed(self, text: str) -> list[float]:
        sparse = self.vectorizer.transform([text])
        dense = self.svd.transform(sparse)
        return self.normalizer.transform(dense)[0].astype("float32").tolist()

    def search(self, question: str, limit: int = 5, minimum_score: float = 0.08) -> list[dict]:
        response = self.client.query_points(
            collection_name=self.collection,
            query=self.embed(question),
            limit=limit,
            with_payload=True,
        )
        rows = []
        for point in response.points:
            if point.score < minimum_score:
                continue
            payload = dict(point.payload or {})
            payload["vector_score"] = round(float(point.score), 6)
            rows.append(payload)
        return rows

    def metadata(self) -> dict:
        return {
            "backend": 'Qdrant Cloud' if self.remote else self.manifest["vector_database"],
            "embedding_model": self.manifest["embedding_model"],
            "dimensions": self.manifest["dimensions"],
            "total_vectors": self.manifest["total_vectors"],
            "pdf_chunks": self.manifest["pdf_chunks"],
            "chunking": self.manifest["chunking"],
        }

    def close(self) -> None:
        client = getattr(self, "client", None)
        if client is not None:
            client.close()
            self.client = None
