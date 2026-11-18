# Hybrid KB v2

## Build and run

1. Start Docker and `python tools/kb/start_neo4j.py`.
2. Run `python tools/kb/build_hybrid_kb.py --fetch-web --ingest` once.
3. Configure `.env` using `.env.example`; never put API keys in chat or git.
4. Run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`.

The builder ingests the project's three PDF sources, two NIDDK webpages in
`knowledge/web_sources.json`, and the existing 44 Vietnamese source summaries.
HTML snapshots and hashes preserve the text seen at ingestion. Web retrieval is
against this indexed source snapshot, not unrestricted live internet search.

## Schema and scripts

- `knowledge/DB_diabet.cypher`: constraints, indexes and read-only demos.
- `knowledge/hybrid/DB_diabet_seed.cypher`: standalone data seed, including vectors.
- `knowledge/hybrid/source_registry.json`: titles, URLs, hashes and versions.
- `knowledge/hybrid/kb_bundle.json`: reproducible ingestion payload.
- `Document -HAS_CHUNK-> Chunk -MENTIONS-> Entity`.
- `Fact -SUPPORTED_BY-> Chunk`, `Fact -SUBJECT/OBJECT-> Entity`.

The additive migration preserves the original Dia* schema. Active chunk/fact IDs
are stored on KBVersion; old versions remain available for audit. Imported legacy
facts have `review_status=imported_unreviewed`; they are source-linked assertions,
not independently validated clinical rules. No LLM-created fact is auto-approved.

## Retrieval and answer generation

### Groq configuration

The local `.env` is prepared for Groq at `https://api.groq.com/openai/v1`
with model `openai/gpt-oss-20b` and `LLM_RESPONSE_FORMAT=json_schema`.
Fill only `LLM_API_KEY` using a key from https://console.groq.com/keys, then
restart uvicorn. The Groq-hosted model uses strict JSON Schema and low reasoning
effort. Model availability is account-dependent; a live API call is required to
confirm access. An empty key returns `configuration_required` and uses a template.
Never copy `.env` into the repository or a report.

The online service uses the frozen 128-dimensional LSA embedder with Neo4j vector,
fulltext and graph retrieval, then reciprocal-rank fusion. This removes the need
for Qdrant in the active Neo4j path; the earlier Qdrant path remains available when
the unified KB has not been built. Entity linking currently uses canonical names;
automatic ontology classification and cross-encoder reranking are not implemented.

PDF parsing uses pypdf and page/paragraph windows (380 words, 60-word overlap).
HTML paragraphs retain headings. OCR and reliable complex-table extraction remain
limitations; this does not claim Docling or layout-aware table parsing.

ExplanationAgent supports Ollama `/api/chat` or a configured compatible
`/chat/completions` endpoint. Only the question and retrieved evidence are sent;
raw patient profiles are not sent to the LLM. Model score, model factors and review
decision stay in deterministic sections. Each generated statement includes a
source ID and an exact quote checked against indexed evidence. Fabricated IDs,
quotes and new numbers are rejected. These checks do not establish semantic
entailment; the UI shows source text so a reader can inspect it. With no provider,
an unavailable model, or invalid output, the app explicitly uses template output.

## Verification

Run `python -m unittest discover -s tests -v`. Live smoke checks should cover PDF
and HTML retrieval, empty evidence, source links, invalid citations and changed
model decisions. Earlier benchmark artifacts predate this migration and must not
be described as current hybrid/LLM evaluation. A clinically reviewed gold set and
measured reranking ablation are still needed.
