# Tijori — DPDP Privacy Gateway

**PS-02, MineArena 1.0.** A local privacy gateway between enterprise documents and
an LLM. Detect Indian PII, replace it with typed placeholders, send only the
sanitized payload out, reinsert originals locally, audit every request.

> **6-hour target:** one working end-to-end demo, not bonus features.

```
document ──► detect ──► mask ──► forward sanitized ──► reinsert ──► answer
                │          │              │                │
           Presidio +   <PERSON_1>   external LLM     original values
           GLiNER       <AADHAAR_1>  (Ollama/OpenAI)  restored locally
                                      │
                                 audit row (no PII)
```

## Stack

Python 3.14 venv (already created) · FastAPI · Streamlit · SQLite · Microsoft
Presidio + custom India recognizers · GLiNER (`urchade/gliner_multi_pii-v1`) ·
spaCy `en_core_web_sm` · Ollama (`qwen2.5:3b`).

## Quickstart

```bash
source .venv/bin/activate
pip install -r requirements.txt          # only if the venv is missing packages

# local model (one-time, ~1.9 GB)
ollama pull qwen2.5:3b

cp .env.example .env
make test
make api        # http://127.0.0.1:8000/docs
make ui         # http://127.0.0.1:8501
```

## Where things live

| Path | What |
|---|---|
| `CONTRACT.md` | Frozen interfaces, placeholders, API, audit schema, ownership |
| `app/contracts.py` | Shared Pydantic types (single source of truth) |
| `privacy/` | Detection, masking, vault, reinsertion (lane 1) |
| `app/` | FastAPI, pipeline, provider, audit (lane 2) |
| `ui/`, `data/`, `evaluation/` | Streamlit demo, dataset, metrics (lane 3) |
| `docs/PS02.md` | Original problem statement |

## Branches

| Branch | Owner | Scope |
|---|---|---|
| `agent/privacy-core` | lane 1 | Presidio India recognizers, GLiNER, masking, reinsertion |
| `agent/gateway-platform` | lane 2 | FastAPI stages, Ollama adapter, SQLite audit |
| `agent/demo-eval` | lane 3 | Streamlit 3-pane UI, 50-doc dataset, metrics report |

`main` is protected by review: Shreyas merges. Team is 3 coders (one per lane)
plus 1 reviewer/merger. Merge order is 1 → 2 → 3. Do not edit `CONTRACT.md`,
`app/contracts.py`, or another lane's files. Reviewer steps:
`docs/MERGE-CHECKLIST.md`.

## 6-hour plan

| Hour | Lane 1 | Lane 2 | Lane 3 |
|---|---|---|---|
| 0–0.5 | Read contract, load models offline | Read contract, Ollama smoke test | Read contract, sample docs |
| 0.5–2.0 | Recognizers + NER + overlap resolution | `/v1/sanitize` + `/v1/process` + provider | Dataset generator (50 docs, labels) |
| 2.0–3.5 | Masking + vault + reinsertion tests | Audit SQLite + request IDs + error paths | Streamlit 3 panes wired to API |
| 3.5–4.5 | Merge, fix integration bugs | Merge, run real Ollama e2e | Evaluation metrics + `reports/metrics.md` |
| 4.5–5.5 | Leakage sweep on dataset | Latency + audit check | Demo polish, screenshots |
| 5.5–6.0 | **Demo dry run, freeze** | **Demo dry run, freeze** | **Demo dry run, freeze** |

## Out of scope for the first 6 hours

Purpose-based policies, format-preserving tokenization, local-SLM fallback,
React UI, Postgres. Add only after the core demo is green.

## External LLM note

Ollama is local, while PS-02 §3.4 asks for an external LLM API. The provider is
OpenAI-compatible, so switching to OpenRouter/Groq/OpenAI is an env change
(`TIJORI_LLM_BASE_URL`, `TIJORI_LLM_API_KEY`, `TIJORI_LLM_MODEL`). Plan to demo
one genuinely external call before judging, or present Ollama as the local
fallback.
