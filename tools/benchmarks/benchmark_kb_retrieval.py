"""Measure retrieval on fixed questions against the currently active hybrid KB."""
import argparse
import json
import re
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from services.hybrid_kb import HybridKB
from services.neo4j_store import Neo4jStore

PARAPHRASES = (
    "Chỉ số hemoglobin glyc hóa cho biết điều gì, theo NIDDK?",
    "Trước khi lấy máu đo HbA1c, có được ăn sáng không? NIDDK",
    "Chuẩn bị nhịn ăn thế nào trước xét nghiệm đường huyết lúc đói hoặc nghiệm pháp dung nạp? NIDDK",
    "Chỉ số hemoglobin glyc hóa bao nhiêu được xếp vào mức bình thường? NIDDK",
    "Một kết quả HbA1c bất thường ở người không có triệu chứng có cần kiểm tra lại? NIDDK",
    "Xét nghiệm hemoglobin glyc hóa có phù hợp để xác định đái tháo đường típ một? NIDDK",
    "IDF nói gì về việc điều chỉnh mục tiêu hemoglobin glyc hóa cho người dễ bị tụt đường?",
    "NIDDK mô tả cách kiểm tra đường huyết để phát hiện đái tháo đường khi mang thai thế nào?",
)


def evaluate(cases, documents, retrieve):
    source_ids = {row["id"] for row in documents}
    if any(not set(case["relevant"]).issubset(source_ids) for case in cases):
        raise ValueError("KB is missing benchmark reference chunks")
    trials = []
    for case, paraphrase in zip(cases, PARAPHRASES, strict=True):
        for variant, question in (("original", case["question"]), ("paraphrase", paraphrase)):
            started = perf_counter()
            rows = retrieve(question)
            elapsed = (perf_counter() - started) * 1000
            rank = next((i for i, row in enumerate(rows, 1) if row["id"] in case["relevant"]), None)
            trials.append({
                "case": case["id"], "variant": variant, "question": question,
                "first_relevant_rank": rank, "latency_ms": round(elapsed, 1),
                "retrieved": [{"id": row["id"], "methods": row["retrieval_methods"]} for row in rows],
            })
    return {"n": len(trials),
            "hit_at_5": sum(r["first_relevant_rank"] is not None for r in trials) / len(trials),
            "mrr_at_5": sum(1 / r["first_relevant_rank"] for r in trials if r["first_relevant_rank"]) / len(trials)}, trials


def offline_vectors(path, primary_only):
    import joblib
    import numpy as np

    bundle = json.loads(path.read_text(encoding="utf-8"))
    documents = bundle["chunks"]
    vectors = bundle.get("semantic_vectors")
    if vectors is None:
        artifacts = ROOT / "knowledge/vector_artifacts"
        vectorizer, svd, normalizer = (joblib.load(artifacts / name) for name in (
            "tfidf_vectorizer.joblib", "lsa_svd.joblib", "normalizer.joblib",
        ))
        vectors = [row["embedding"] for row in documents]
        def encode(text):
            return normalizer.transform(svd.transform(vectorizer.transform([text])))[0]
    else:
        from services.semantic_embedding import E5Encoder
        if bundle["embedding"] != E5Encoder.identifier:
            raise ValueError("Bundle and query encoder revisions differ")
        encode = E5Encoder().query
    matrix = np.asarray(vectors, dtype=np.float32)

    def retrieve(question):
        scores = matrix @ np.asarray(encode(question), dtype=np.float32)
        source = re.search(r"\b(niddk|idf)\b", question.lower()).group(1)
        eligible = [i for i, row in enumerate(documents)
                    if (not primary_only or row["source_type"] in {"pdf", "web"})
                    and source in " ".join(str(row.get(k, "")) for k in ("title", "url", "document_id")).lower()]
        return [{"id": documents[i]["id"], "retrieval_methods": ["vector"]}
                for i in sorted(eligible, key=lambda i: (-scores[i], documents[i]["id"]))[:5]]

    return documents, retrieve, {"kb_version": bundle["version"], "embedding_model": bundle["embedding"],
                                 "backend": "offline exact cosine ranking with requested source filter",
                                 "source_policy": "pdf_web_only" if primary_only else "all_sources"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--version", help="Benchmark a staged snapshot without activating it")
    mode.add_argument("--offline-vectors", type=Path, help="Compare only embeddings with a local bundle")
    parser.add_argument("--primary-only", action="store_true", help="Exclude summaries in offline vector mode")
    args = parser.parse_args()
    cases = json.loads((ROOT / "benchmarks/v3_cases.json").read_text(encoding="utf-8"))["retrieval"]
    if args.offline_vectors:
        documents, retrieve, metadata = offline_vectors(args.offline_vectors, args.primary_only)
        metrics, trials = evaluate(cases, documents, retrieve)
    else:
        store = Neo4jStore()
        kb = None
        try:
            kb = HybridKB(store, version=args.version)
            metrics, trials = evaluate(cases, kb.documents, lambda q: kb.retrieve(q, limit=5)[0])
            metadata = kb.metadata()
        finally:
            if kb and kb.remote_vectors:
                kb.remote_vectors.client.close()
            store.driver.close()
    result = {"kb": metadata, "metrics": metrics, "trials": trials,
              "scope": "Eight fixed relevance judgments, two question formulations each. Questions go directly to retrieval."}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
