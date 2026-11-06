from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_system import MultiAgent, Services, SingleAgent

app = FastAPI(title="DiaAgents Lab", version="1.0.0")
services = Services(); single = SingleAgent(services); multi = MultiAgent(services)


class Request(BaseModel):
    question: str = Field(default="", max_length=800)
    profile: dict | None = None
    mode: str = "multi"


@app.get("/health")
def health():
    return {"status":"ok","active_model":services.model.model_name,"knowledge_backend":services.knowledge.backend,"documents":len(services.knowledge.documents),"graph_edges":len(services.knowledge.graph)}


@app.get("/api/metadata")
def metadata():
    data=json.loads((ROOT / "artifacts/model_metadata.json").read_text(encoding="utf-8"))
    data['active_model']=services.model.model_name
    data['pytorch']=json.loads((ROOT/'artifacts/pytorch_metadata.json').read_text(encoding='utf-8'))
    data['knowledge_backend']=services.knowledge.backend
    data['knowledge_documents']=len(services.knowledge.documents)
    return data


@app.get("/api/graph")
def graph():
    return {"edges": services.knowledge.graph}


@app.get("/api/benchmark")
def benchmark():
    import pandas as pd
    summary_path = ROOT / "results" / "agent_benchmark_summary.json"
    rows_path = ROOT / "results" / "agent_benchmark.csv"
    if not summary_path.exists() or not rows_path.exists():
        raise HTTPException(503, "Benchmark chưa được tạo.")
    rows = pd.read_csv(rows_path)
    by_kind = (
        rows.groupby(["system", "kind"], as_index=False)
        .agg(cases=("case_id", "count"), success_rate=("success", "mean"), mean_latency_ms=("latency_ms", "mean"))
        .round(4)
        .to_dict(orient="records")
    )
    paired_path = ROOT / 'results' / 'paired_agent_evaluation.json'
    paired = json.loads(paired_path.read_text(encoding='utf-8')) if paired_path.exists() else None
    repair_path = ROOT / 'results' / 'evidence_repair_benchmark.json'
    repair_data = json.loads(repair_path.read_text(encoding='utf-8')) if repair_path.exists() else None
    repair_summary = {key: repair_data[key] for key in ('protocol', 'summary')} if repair_data else None
    return {"summary": json.loads(summary_path.read_text(encoding="utf-8")), "by_kind": by_kind,
            "paired": paired, "evidence_repair": repair_summary}


@app.post("/api/run")
def run(payload: Request):
    if not payload.question.strip() and not payload.profile:
        raise HTTPException(400, "Cần câu hỏi hoặc hồ sơ.")
    runner = multi if payload.mode == "multi" else single if payload.mode == "single" else None
    if runner is None: raise HTTPException(400, "mode chỉ nhận single hoặc multi")
    return runner.run(payload.question.strip(), payload.profile)


@app.get('/api/benchmark/diabetes')
def diabetes_benchmark():
    path = ROOT / 'results/diabetes_agent_benchmark.json'
    if not path.exists():
        raise HTTPException(503, 'Benchmark dự đoán chưa hoàn tất.')
    data=json.loads(path.read_text(encoding='utf-8'))
    before=ROOT/'results/diabetes_agent_benchmark_before_policy.json'
    data['before_policy']=json.loads(before.read_text(encoding='utf-8'))['systems']['multi'] if before.exists() else None
    return data


@app.post("/api/compare")
def compare(payload: Request):
    if not payload.question.strip() and not payload.profile:
        raise HTTPException(400, "Cần câu hỏi hoặc hồ sơ.")
    question = payload.question.strip()
    return {"single": single.run(question, payload.profile), "multi": multi.run(question, payload.profile)}


STATIC = ROOT / "app" / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get('/api/benchmark/critic')
def critic_benchmark():
    path = ROOT / 'results/critic_challenge_benchmark.json'
    if not path.exists():
        raise HTTPException(503, 'Benchmark phản biện chưa hoàn tất.')
    return json.loads(path.read_text(encoding='utf-8'))


@app.get('/api/benchmark/corpus')
def current_corpus_benchmark():
    path=ROOT/'results/current_corpus_benchmark.json'
    if not path.exists(): raise HTTPException(503,'Benchmark corpus mới chưa hoàn tất.')
    data=json.loads(path.read_text(encoding='utf-8'))
    return {key:data[key] for key in ('protocol','summary')}
