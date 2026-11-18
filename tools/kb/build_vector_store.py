"""Extract local PDFs, chunk them, build LSA embeddings and persist Qdrant.

The embedding model is deliberately lightweight: word/character TF-IDF followed
by TruncatedSVD and L2 normalization.  It runs alongside PyTorch and Neo4j on a
small deployment without downloading a second neural checkpoint.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
from pypdf import PdfReader
from qdrant_client import QdrantClient, models
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.preprocessing import Normalizer

ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "knowledge" / "pdfs"
STORE_DIR = ROOT / "knowledge" / "qdrant"
ARTIFACT_DIR = ROOT / "knowledge" / "vector_artifacts"
COLLECTION = "diabetes_chunks"
CHUNK_WORDS = 180
OVERLAP_WORDS = 40

SOURCE_URLS = {
    "DIA_Ch01.pdf": "https://www.niddk.nih.gov/-/media/Files/Strategic-Plans/Diabetes-in-America-3rd-Edition/DIA_Ch01.pdf",
    "Guiding-Principles.pdf": "https://www.niddk.nih.gov/-/media/Files/Health-Information/Health-Professionals/Diabetes/health-care-professionals/Guiding-Principles.pdf",
    "IDF_Rec_2025.pdf": "https://idf.org/media/uploads/2025/05/IDF_Rec_2025.pdf",
    "cdc_135620_DS1.pdf": "https://stacks.cdc.gov/view/cdc/135620/cdc_135620_DS1.pdf",
    "cdc_75807_DS1.pdf": "https://stacks.cdc.gov/view/cdc/75807/cdc_75807_DS1.pdf",
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sliding_chunks(text: str, size: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS):
    words = clean_text(text).split()
    if not words:
        return
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        part = words[start:start + size]
        if len(part) < 35:
            break
        yield " ".join(part)
        if start + size >= len(words):
            break


def pdf_documents() -> tuple[list[dict], list[dict]]:
    chunks, sources = [], []
    for path in sorted(PDF_DIR.glob("*.pdf")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        reader = PdfReader(path)
        source = {
            "file": path.name,
            "url": SOURCE_URLS.get(path.name, ""),
            "pages": len(reader.pages),
            "sha256": digest,
        }
        sources.append(source)
        for page_number, page in enumerate(reader.pages, start=1):
            for chunk_number, text in enumerate(sliding_chunks(page.extract_text() or ""), start=1):
                natural = f"{path.name}|{page_number}|{chunk_number}|{digest}"
                chunk_id = "pdf_" + hashlib.sha1(natural.encode()).hexdigest()[:20]
                chunks.append({
                    "id": chunk_id,
                    "title": f"{path.stem} - trang {page_number}",
                    "url": source["url"],
                    "organization": "PDF source",
                    "text": text,
                    "page": page_number,
                    "source_file": path.name,
                    "chunk_index": chunk_number,
                    "source_type": "pdf_auto_chunk",
                })
    return chunks, sources


def curated_documents() -> list[dict]:
    rows = json.loads((ROOT / "knowledge" / "corpus.json").read_text(encoding="utf-8"))
    return [{**row, "source_type": "curated_corpus", "page": None,
             "source_file": None, "chunk_index": 0} for row in rows]


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_chunks, sources = pdf_documents()
    chunks = curated_documents() + pdf_chunks
    if len(chunks) < 3:
        raise RuntimeError("Need at least three chunks to build the vector store")

    texts = [f"{row['title']} {row['text']}" for row in chunks]
    word = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=5000,
                           sublinear_tf=True, strip_accents="unicode")
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2,
                           max_features=3000, sublinear_tf=True)
    vectorizer = FeatureUnion([("word", word), ("char", char)])
    sparse = vectorizer.fit_transform(texts)
    dimensions = min(128, sparse.shape[0] - 1, sparse.shape[1] - 1)
    svd = TruncatedSVD(n_components=dimensions, random_state=42)
    normalizer = Normalizer(copy=False)
    vectors = normalizer.fit_transform(svd.fit_transform(sparse)).astype("float32")

    joblib.dump(vectorizer, ARTIFACT_DIR / "tfidf_vectorizer.joblib")
    joblib.dump(svd, ARTIFACT_DIR / "lsa_svd.joblib")
    joblib.dump(normalizer, ARTIFACT_DIR / "normalizer.joblib")
    (ARTIFACT_DIR / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    client = QdrantClient(path=str(STORE_DIR))
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
    )
    batch = []
    for row, vector in zip(chunks, vectors):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, row["id"]))
        batch.append(models.PointStruct(id=point_id, vector=vector.tolist(), payload=row))
        if len(batch) == 128:
            client.upsert(COLLECTION, batch, wait=True); batch = []
    if batch:
        client.upsert(COLLECTION, batch, wait=True)
    client.close()

    missing = sorted(set(SOURCE_URLS) - {s["file"] for s in sources})
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "collection": COLLECTION,
        "vector_database": "Qdrant local persistent",
        "embedding_model": "TF-IDF word+character n-grams + TruncatedSVD (LSA) + L2 normalization",
        "dimensions": dimensions,
        "chunking": {"unit": "page-aware sliding word window", "words": CHUNK_WORDS,
                     "overlap_words": OVERLAP_WORDS, "minimum_words": 35},
        "curated_documents": len(chunks) - len(pdf_chunks),
        "pdf_chunks": len(pdf_chunks),
        "total_vectors": len(chunks),
        "pdf_sources": sources,
        "missing_pdf_files": missing,
    }
    (ARTIFACT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    main()
