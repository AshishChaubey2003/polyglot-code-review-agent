# Polyglot AI Code Review & Repair Agent

A developer tool that reviews source code for bugs, security issues and quality problems, and can optionally propose a verified, human-approved fix.

Guiding principle: **the LLM is never the sole source of truth.** Deterministic static analysis (AST, Ruff, Bandit) and retrieved reference documentation (hybrid RAG) feed the LLM's reasoning. Every proposed fix is independently re-verified against real tools and requires explicit human approval before it is ever applied.

```
LLM proposes → Guardrail validates → Analyzer verifies → Human approves → System applies → Independent re-verification
```

## Architecture

```text
User Code
   ↓
Input Guardrails → Language Detection → Static Analysis (AST/Ruff/Bandit, Python)
   ↓
Query Transformation → Hybrid RAG (FAISS + BM25 + RRF, metadata-filtered + reranked)
   ↓
LangGraph Review Agents (Bugs / Security / Quality — parallel, fan-out/fan-in)
   ↓
Aggregate → Structured Report
   ↓
Review Mode (stop here)   |   Repair Mode: generate fix → output/code/scope guards
                              → independent verification (syntax/lint/security/behavior)
                              → human Approve/Reject → apply
```

`app.py` (Streamlit) and `api/main.py` (FastAPI) are two frontends over the exact same orchestration (`services/review_service.py` → `agents/graph.py`) — neither duplicates the other's logic.

## What's real vs. what's a fake vs. what's a stub

This matters more than usual here because this project was built in a sandboxed environment with **no outbound network access to huggingface.co** (confirmed via a 403 on CONNECT from the environment's own proxy, not a timeout fluke) and no `GROQ_API_KEY`. Rather than silently mocking everything, every module that depends on the network was built with the dependency **injectable**, so the real code path (FAISS, the reranker, the LangGraph fan-out/fan-in, every guardrail, every verification step) is exercised for real in tests — only the *model* behind the embedding/LLM calls is swapped for a fake in this environment.

| Component | Tested how here | Why |
|---|---|---|
| AST validation, Ruff, Bandit | **Real subprocess calls**, real tools | No network needed |
| BM25, Reciprocal Rank Fusion, chunking, metadata filtering | **Real, hand-verified math** (RRF has a hand-computed assertion) | Pure Python |
| Guardrails (input/output/code/secret/scope) | **Real logic**, no mocks | Pure Python |
| Behavior verification (pytest-in-subprocess) | **Real pytest runs**, off by default (`ALLOW_TEST_EXECUTION`) | Security: never executes untrusted code unless explicitly enabled |
| FAISS vector store, reranker | **Real FAISS/cosine-similarity code**, fake embedding model (`tests/fakes/fake_embeddings.py` — a real bag-of-words vectorizer, not a random stub) | huggingface.co blocked here; `VectorStore`/`rerank()` take an injectable `embeddings` param, so production code uses the real HuggingFace model and tests use the fake one |
| LangGraph routing, state merging, human-loop approval, the FastAPI endpoints | **Real graph execution, real HTTP calls (TestClient)**, fake LLM responses (`LLMService.structured_generate`/`.generate` monkeypatched) | No `GROQ_API_KEY`/network in this sandbox |
| GitHub integration, MCP tool exposure, project memory | **Explicit stubs** (`NotImplementedError`) | Deliberately deferred — not core to review/repair, not implemented as fake-functional code |

**On your own machine**, with `GROQ_API_KEY` set and normal network access, every one of the faked paths above runs against the real provider/model with no code changes — that's the entire point of the injectable-dependency design.

## Features

- [x] Static analysis: Python AST validation, Ruff, Bandit → normalized `Finding` schema
- [x] Hybrid RAG: FAISS + BM25 fused by Reciprocal Rank Fusion, metadata-filtered (with a zero-result fallback chain), reranked
- [x] Query transformation (LLM-proposed, validated queries/filters) and optional HyDE
- [x] LangGraph multi-agent review (parallel bug/security/quality agents, fan-out/fan-in)
- [x] Guardrails: input, output, generated-code, secret, and scope guards
- [x] Repair mode: fix generation → guards → independent verification → human approval → apply
- [x] Evaluation: a labeled dataset, precision/recall/F1 against the real analyzer, a 3-way retrieval-strategy benchmark
- [x] FastAPI surface (`/review`, `/repair`, `/verify`, `/approve`, `/reject`, `/apply`, `/health`) sharing all logic with the Streamlit UI
- [ ] Multi-language static analysis (JS/TS/Java/Go) — LLM review agents run on any language today; static analysis and repair mode are Python-only
- [ ] GitHub PR integration, MCP tool exposure, project memory — deliberately deferred stubs

## Tech stack

Python 3.11+, Streamlit, FastAPI, LangGraph + LangChain, Pydantic v2, FAISS, `rank-bm25`, Groq (`openai/gpt-oss-120b`) behind a swappable `LLMService` abstraction, HuggingFace `sentence-transformers/all-MiniLM-L6-v2` embeddings.

## Project layout

```text
agents/            LangGraph state, graph wiring, and one module per node
analyzers/          Python static analyzer (AST/Ruff/Bandit wrappers)
api/                FastAPI app
data/documents/     Hand-written knowledge-base source documents
evaluation/         Labeled dataset, metrics, retrieval benchmark
guardrails/         input/output/code/secret/scope guards
human_loop/         Approval state machine + apply-fix
mcp/, memory/       Deferred stubs (GitHub is under services/)
models/             Pydantic schemas shared across the whole app
rag/                Chunking, ingestion, BM25, vector store, RRF, HyDE,
                    reranker, query transform, retriever orchestrator
services/           LLM service, review orchestration, GitHub stub
verification/       Independent syntax/lint/security/behavior/diff checks
tests/              Unit tests (125 passing) + fakes (fake embeddings)
app.py              Streamlit UI
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `LLM_PROVIDER` | No | `groq` | Which provider `LLMService` builds. Only `groq` is implemented. |
| `LLM_MODEL` | No | `openai/gpt-oss-120b` | Model name passed to the provider. |
| `GROQ_API_KEY` | Yes, for any real LLM call | — | Get one free at [console.groq.com](https://console.groq.com). |
| `LOG_LEVEL` | No | `INFO` | Python logging level. |
| `ALLOW_TEST_EXECUTION` | No | `false` | Enables pytest-in-subprocess behavior verification. Only enable in an environment you trust — it runs AI-generated code. |
| `KNOWLEDGE_BASE_DIR` | No | `data/documents` | Where the RAG knowledge-base markdown files live. |
| `VECTOR_INDEX_DIR` | No | `data/indexes` | Reserved for a persisted FAISS index (not yet used — the index is built in memory per process today). |

## Running locally

```bash
streamlit run app.py          # UI
uvicorn api.main:app --reload # API
```

## Running tests

```bash
pytest tests/unit -v
```

125 tests, all passing, no network or API key required (every LLM/embedding call is either real-deterministic code or an injected fake — see the table above).

**If you're running this in a similarly network-restricted environment**: `tests/fakes/fake_embeddings.py` is why the FAISS/reranker tests don't need huggingface.co. If you see an `ImportError: sentence_transformers` or a hang/timeout reaching huggingface.co, that's the production embedding path (`rag/embeddings.py`), not the tests — the tests never touch it.

## Security notes

- Behavior verification (running AI-generated code's tests) is **off by default** and is not a real sandbox when enabled — only turn it on in a trusted, isolated environment.
- Secrets detected in input or in a proposed fix are flagged, never auto-redacted-and-continued or silently dropped — the human reviewing the finding/fix sees them called out explicitly.
- A fix is never applied without `approval_status == "approved"`, set only by an explicit human action in `human_loop/approval.py`. Nothing in the codebase sets that status any other way.
- LLM-proposed RAG metadata filters are validated against an explicit allow-list (`rag/metadata.py`) before ever reaching FAISS/BM25 — an LLM proposing a filter is not the same as the filter being trusted.

## Known limitations

- Static analysis and repair mode are Python-only. Other languages get LLM-only review (no AST/Ruff/Bandit grounding, no repair).
- The FAISS index is rebuilt in memory per process (fine for this knowledge base's size; `VECTOR_INDEX_DIR` is reserved for persisting it later).
- The reranker's optional cross-encoder path is documented but not implemented (would be a second heavy model download, unvalidatable in this sandbox).
- Evaluation numbers (`evaluation/metrics.py`, `evaluation/benchmarks.py`) are computed over a 5–6 example hand-built dataset — real regression-visibility tools, not statistically significant benchmarks. Both modules say so in their own output.
- GitHub PR integration, MCP tool exposure, and project memory are intentionally unimplemented stubs (`services/github_service.py`, `mcp/tools.py`, `memory/project_memory.py`), per the project's own phased-deferral plan — not half-built, not faked.

> **Model availability varies by Groq account.** If you see `model_not_found` (404), list the models your key can use with
> `python -c "from dotenv import load_dotenv; load_dotenv(); from groq import Groq; print('\n'.join(sorted(m.id for m in Groq().models.list().data)))"`
> and set `LLM_MODEL` in `.env` to one of the chat models it prints.
