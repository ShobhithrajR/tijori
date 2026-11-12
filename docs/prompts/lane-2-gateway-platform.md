# Lane 2 prompt — Gateway Platform

You are the Lane 2 agent for a 6-hour hackathon build. Work independently.

- Repo: `https://github.com/Shreyas-a-j/tijori.git`
- Branch: `agent/gateway-platform` (create it from `main`)
- Read first: `CONTRACT.md` (§3, §4, §5, §7, §11), `app/contracts.py`, `app/config.py`, `app/providers/base.py`, `.env.example`, `docs/PS02.md` §3.3–3.5 and §5.
- Env: Python 3.14 `.venv`, FastAPI/uvicorn/openai/httpx/pytest installed. Ollama is running at `http://127.0.0.1:11434/v1` with `qwen2.5:3b`. **Do not add dependencies.**
- You own only: `app/api/**`, `app/pipeline/**`, `app/providers/**`, `app/audit/**`, `app/main.py`, `tests/platform/**`. Do not edit `CONTRACT.md`, `app/contracts.py`, `privacy/**`, `ui/**`, `data/**`, `evaluation/**`, or root configs.

## Objective

Ship the four-stage gateway API, the pluggable OpenAI-compatible provider (Ollama default), SQLite audit, and tests proving no PII crosses the provider boundary. Timebox: **2 hours**.

Lane 1 may not be merged yet. `privacy.detection.detect`, `privacy.masking.mask`, and `privacy.reinsertion.reinsert` currently raise `NotImplementedError`. Use **monkeypatch fakes in tests**; never replace them with leaking fallbacks.

## Tasks (in order)

1. **Provider** — `app/providers/openai_compatible.py`
   - `AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key, timeout=settings.llm_timeout_s)`.
   - `complete(messages, temperature, max_tokens) -> LLMResponse` using `chat.completions.create`.
   - `name = "openai_compatible"`, `model = settings.llm_model`.
   - Never log message content. Add `get_provider()` in `app/providers/__init__.py` (factory keyed by `settings.llm_provider`).

2. **Pipeline** — `app/pipeline/pipeline.py`
   - `sanitize(req)`: detect → mask → build `MaskedEntityView` list + counts → audit (`task="sanitize"`) → return.
   - `process(req)`: same detection/masking; build messages:
     - system: "Preserve every placeholder like `<PERSON_1>` exactly. Never alter, guess, or invent placeholders."
     - user: `req.instruction or default task prompt` + `\n\n` + sanitized text.
     - `outbound_payload` = deterministic JSON of the exact message list sent.
   - Call provider, reinsert locally, verify `leakage_count` by scanning `outbound_payload` for every mapping original (also try the Aadhaar space/hyphen-stripped variant), audit, return `ProcessResponse`.
   - `request_id = "req_" + uuid4().hex`; measure `latency_ms`.

3. **Audit** — `app/audit/repository.py`
   - SQLite from `settings.db_path`, create parent dir, `PRAGMA journal_mode=WAL`, create `audit_requests` exactly as `CONTRACT.md` §5.
   - `insert(record)`, `get(request_id)`, `list(limit=50)` newest first. JSON-encode list/dict fields. **Never store originals or mappings.**

4. **API** — `app/api/routes.py` + wire in `app/main.py`
   - `GET /health`
   - `POST /v1/sanitize` → `SanitizeResponse`
   - `POST /v1/process` → `ProcessResponse`
   - `GET /v1/audit/{request_id}`, `GET /v1/audit?limit=50`
   - Initialize DB on startup/lifespan. Provider failure → audit row with `status="error"`, HTTP 502. Validation errors → 422. Never leak originals in error messages.

5. **Tests** — `tests/platform/`
   - Fake detector/masker/reinsertion via monkeypatch on the `privacy` modules.
   - Spy provider that records the messages it receives.
   - Assert: outbound JSON contains no "Rahul Sharma" and no "1234-5678-9012"; audit row exists for success and provider failure; `GET /v1/audit/{id}` returns no original; `/health` ok; `/v1/sanitize` response has no `original` field.
   - One real Ollama smoke test marked `@pytest.mark.slow`, skipped if the endpoint is down.

## Acceptance

```bash
source .venv/bin/activate
python -m pytest tests/platform -q
uvicorn app.main:app --port 8000
curl -s localhost:8000/health
```

## After lane 1 merges

Rebase on `main`, run one real `/v1/process` with the PS-02 sample against
Ollama, confirm `outbound_payload` is sanitized and an audit row is written,
then push the rebased branch. Do not merge.

## Finish

Commit on `agent/gateway-platform`, push, open a PR against `main`. **Do not merge.** Final message: files changed, test output, real vs faked paths, and any contract ambiguity. Stop at 2 hours.
