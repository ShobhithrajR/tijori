# Tijori — Frozen Contract

This file is the **only** shared surface between the three parallel work lanes.
It is frozen before lane work starts. **No lane may edit this file.** If an
interface must change, open a PR against `CONTRACT.md` and wait for the
maintainer (Shreyas) to approve before writing dependent code.

Tijori = "safe/vault". The gateway is the safe between enterprise documents and
the external LLM.

---

## 1. Invariants

1. Raw PII **never** leaves the gateway. Only `sanitized_text` may be placed in
   an outbound LLM request.
2. Placeholder assignment is **deterministic and stable within one request**:
   same entity value + same entity type → same placeholder.
3. The placeholder → original mapping lives **in memory only**, per request. It
   is never written to the audit DB, never returned by the API, never logged.
4. Reinsertion is **exact-token substitution only**. No fuzzy/contextual
   matching, ever. This prevents swapping one person's data for another's.
5. Every request produces exactly one audit row, even on failure.
6. The demo must be runnable with no internet: Ollama on `127.0.0.1:11434`.

---

## 2. Entity taxonomy

Mandatory types (PS-02 §3.1):

| `EntityType` | Placeholder example | Primary detector |
|---|---|---|
| `AADHAAR` | `<AADHAAR_1>` | Presidio custom recognizer (12 digits, optional spaces/hyphens) |
| `PAN` | `<PAN_1>` | Presidio custom recognizer (`[A-Z]{5}[0-9]{4}[A-Z]`) |
| `GSTIN` | `<GSTIN_1>` | Presidio custom recognizer (15 chars, state code + PAN + entity + Z + checksum) |
| `VOTER_ID` | `<VOTER_ID_1>` | Presidio custom recognizer (EPIC, 3 letters + 7 digits) |
| `PASSPORT` | `<PASSPORT_1>` | Presidio custom recognizer (1 letter + 7 digits) |
| `PERSON` | `<PERSON_1>` | GLiNER + spaCy NER |
| `ADDRESS` | `<ADDRESS_1>` | GLiNER + heuristic/Indian address context |

Optional but expected by Presidio (keep if it costs nothing):

`PHONE`, `EMAIL`, `DOB`, `BANK_ACCOUNT`, `CREDIT_CARD`, `OTHER`.

Entity type values are the `EntityType` enum strings in `app/contracts.py`.
Placeholder grammar:

```
^<(AADHAAR|PAN|GSTIN|VOTER_ID|PASSPORT|PERSON|ADDRESS|PHONE|EMAIL|DOB|BANK_ACCOUNT|CREDIT_CARD|OTHER)_([1-9][0-9]*)>$
```

Rules:

- Counter starts at 1 per type, per request, assigned in order of first
  occurrence in the text.
- Same normalized value + same type reuses its placeholder.
- Normalization: trim; collapse internal whitespace; `AADHAAR` drops spaces and
  hyphens; `PAN`, `GSTIN`, `VOTER_ID`, `PASSPORT` are upper-cased; `PERSON` and
  `ADDRESS` are compared case-insensitively after whitespace collapse.
- Placeholders are ASCII, contain no spaces, and are enclosed in angle brackets.
- An entity span `[start, end)` indexes the **original** string, Python slice
  semantics.

---

## 3. Shared Python surface

`app/contracts.py` is the single source of truth. Lanes import from it; they do
not redefine these types.

### Detection (lane 1)

```python
# privacy/detection/__init__.py
def detect(text: str, *, language: str = "auto") -> DetectionResult: ...
```

- Returns entities sorted by `start`, **non-overlapping**, highest-priority
  entity wins on overlap (priority: AADHAAR > PAN > GSTIN > PASSPORT >
  VOTER_ID > CREDIT_CARD > BANK_ACCOUNT > EMAIL > PHONE > DOB > PERSON >
  ADDRESS > OTHER).
- Every entity has `type`, `start`, `end`, `text`, `score` in `[0, 1]`, `source`
  (`"presidio"`, `"gliner"`, `"spacy"`, `"regex"`, `"heuristic"`).
- Must work offline after models are cached.
- Must handle Indian English and code-mixed (Hinglish) text.

### Masking / vault (lane 1)

```python
# privacy/masking/__init__.py
def mask(text: str, entities: list[DetectedEntity]) -> MaskingResult: ...

# privacy/vault.py
class PlaceholderVault:
    def add(self, entity_type: EntityType, original: str) -> str: ...
    def resolve(self, placeholder: str) -> str | None: ...
    @property
    def entries(self) -> list[PlaceholderEntry]: ...
```

`MaskingResult.sanitized_text` must contain no original PII value from any
detected entity. `MaskingResult.mapping` is the ordered list of
`PlaceholderEntry` (placeholder, type, original, occurrences).

### Reinsertion (lane 1)

```python
# privacy/reinsertion/__init__.py
def reinsert(text: str, mapping: list[PlaceholderEntry]) -> ReinsertionResult: ...
```

- Case-insensitive on the placeholder token (`<person_1>` matches
  `<PERSON_1>`); the type and number must both match.
- Do **not** repair malformed placeholders (`<PERSON 1>`, `<PERSON-1>`,
  `<PERSON_1`); leave them untouched and list them in `unknown`.
- Dropped placeholders are not an error: leave the LLM text as-is and list the
  placeholders in `missing`.
- Do not remove surrounding punctuation; substitute only the token.

### LLM provider (lane 2)

```python
# app/providers/base.py
class LLMProvider(Protocol):
    name: str
    model: str
    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse: ...
```

The default provider is OpenAI-compatible and points at Ollama:

```
TIJORI_LLM_BASE_URL=http://127.0.0.1:11434/v1
TIJORI_LLM_API_KEY=ollama
TIJORI_LLM_MODEL=qwen2.5:3b
```

Swapping to a genuinely external provider (OpenAI / OpenRouter / Groq) is a
config-only change. See §7.

### Gateway (lane 2)

```python
# app/pipeline/pipeline.py
class PrivacyPipeline:
    def sanitize(self, req: SanitizeRequest) -> SanitizeResponse: ...
    async def process(self, req: ProcessRequest) -> ProcessResponse: ...
```

---

## 4. HTTP API

Base prefix `/v1`. JSON in, JSON out. All errors use FastAPI's `{"detail": ...}`.

### `GET /health`

```json
{"status": "ok", "provider": "openai_compatible", "model": "qwen2.5:3b"}
```

### `POST /v1/sanitize`

Request:

```json
{
  "text": "My name is Rahul Sharma. My Aadhaar number is 1234-5678-9012 and my PAN is ABCDE1234F.",
  "doc_type": "kyc",
  "purpose": "general"
}
```

Response (note: **no original values are returned**):

```json
{
  "request_id": "req_01J...",
  "sanitized_text": "My name is <PERSON_1>. My Aadhaar number is <AADHAAR_1> and my PAN is <PAN_1>.",
  "entities": [
    {"type": "PERSON", "placeholder": "<PERSON_1>", "start": 11, "end": 23},
    {"type": "AADHAAR", "placeholder": "<AADHAAR_1>", "start": 47, "end": 59},
    {"type": "PAN", "placeholder": "<PAN_1>", "start": 72, "end": 82}
  ],
  "counts": {"PERSON": 1, "AADHAAR": 1, "PAN": 1},
  "duration_ms": 42
}
```

### `POST /v1/process`

Request extends the sanitize request:

```json
{
  "text": "...",
  "task": "summarize",
  "instruction": "Summarize in 3 bullet points.",
  "doc_type": "loan_application",
  "purpose": "general",
  "max_tokens": 512
}
```

`task` ∈ `"summarize" | "extract"`.

Response:

```json
{
  "request_id": "req_01J...",
  "final_text": "…original values restored locally…",
  "sanitized_text": "…exact text masked…",
  "outbound_payload": "…the exact prompt string sent to the LLM…",
  "entities": [{"type": "PERSON", "placeholder": "<PERSON_1>", "start": 11, "end": 23}],
  "provider": "openai_compatible",
  "model": "qwen2.5:3b",
  "task": "summarize",
  "latency_ms": 1830,
  "reinsertion": {"replaced": 4, "missing": [], "unknown": []}
}
```

`outbound_payload` MUST be byte-for-byte what was sent, and MUST NOT contain
any detected original value.

### `GET /v1/audit/{request_id}` and `GET /v1/audit?limit=50`

Returns `AuditRecord` rows, newest first. Never returns mappings or originals.

---

## 5. Audit record (SQLite)

Table `audit_requests`:

| Column | Type | Notes |
|---|---|---|
| `request_id` | TEXT PK | `req_` + ULID/uuid |
| `created_at` | TEXT | ISO-8601 UTC |
| `doc_type` | TEXT | from request |
| `purpose` | TEXT | from request |
| `task` | TEXT | `sanitize` / `summarize` / `extract` |
| `entity_counts` | TEXT (JSON) | `{"PERSON": 2, ...}` |
| `outbound_payload` | TEXT | exact sanitized payload |
| `provider` | TEXT | provider name |
| `model` | TEXT | model id |
| `latency_ms` | INTEGER | end-to-end |
| `status` | TEXT | `ok` / `error` |
| `error` | TEXT NULL | short error |
| `reinsertion_replaced` | INTEGER | |
| `reinsertion_missing` | TEXT (JSON) | list of placeholders |
| `reinsertion_unknown` | TEXT (JSON) | list of placeholders |
| `leakage_count` | INTEGER | raw originals found in outbound payload |

**No original PII values are stored.** The mapping is request-scoped memory.

---

## 6. Demo UI (lane 3)

`streamlit run ui/app.py`. Three columns:

1. **Original input** — editable textarea + doc type + task + sample loader.
2. **Outbound payload** — exact `outbound_payload` in a code block, entity table
   (`type`, `placeholder`, span), placeholder count, and a green/red
   **"No raw PII in outbound payload"** badge.
3. **Final response** — `final_text` with reinserted values, plus reinsertion
   stats (`replaced`, `missing`, `unknown`).

Also: audit browser tab (recent requests, entity counts, model, latency,
leakage count), and a latency display. The UI talks to
`TIJORI_API_URL` (default `http://127.0.0.1:8000`) and must never receive
original values from the gateway except inside `final_text`.

---

## 7. External LLM requirement (important)

PS-02 §3.4 requires **an external LLM API**. Ollama is local, so it does not
literally satisfy "external". The gateway must therefore keep the provider
pluggable and OpenAI-compatible:

- Development/demo default: Ollama (`qwen2.5:3b`).
- Before judging, either (a) set `TIJORI_LLM_BASE_URL` + `TIJORI_LLM_API_KEY`
  to a real external OpenAI-compatible endpoint (OpenRouter/Groq/OpenAI), or
  (b) explicitly present Ollama as the local fallback and demo an external call.
- The local model can double as the **Local SLM Fallback** bonus.

No code changes are required to switch providers.

---

## 8. Dataset contract (lane 3)

`data/dataset.jsonl`, one JSON object per line, deterministic from a seed:

```json
{
  "id": "loan_001",
  "doc_type": "loan_application",
  "language": "en",
  "text": "My name is Rahul Sharma …",
  "entities": [
    {"type": "PERSON", "text": "Rahul Sharma", "start": 11, "end": 23},
    {"type": "AADHAAR", "text": "1234-5678-9012", "start": 47, "end": 59}
  ]
}
```

- Exactly 50 documents (±0), seeded (`seed=2026`), reproducible.
- Doc types: `loan_application`, `kyc`, `support_ticket`, `insurance_claim`
  (at least 10 each).
- Languages: `en` and `hi-en` (code-mixed) — at least 15 code-mixed.
- Every entity type from §2 appears at least 10 times across the dataset.
- Spans must be exact; a `make test` check validates every span against `text`.

## 9. Metrics contract (lane 3)

`python -m evaluation.run` writes `reports/metrics.md` with:

| Metric | Definition |
|---|---|
| PII leakage count | occurrences of any gold original value in outbound payloads. Target **0**. |
| Precision per type | `TP / (TP + FP)`, exact span + type match |
| Recall per type | `TP / (TP + FN)`, exact span + type match |
| Reinsertion accuracy | correct exact-token substitutions / all placeholder occurrences in LLM output |
| Latency | gateway end-to-end, and overhead vs direct provider call; p50/p95 |

Also report macro P/R and per-document-type P/R. Include the git commit hash and
dataset seed in the report header.

---

## 10. File ownership (frozen)

Lane branches: `agent/privacy-core`, `agent/gateway-platform`,
`agent/demo-eval`. Merge order: core → platform → demo/eval.

| Path | Owner |
|---|---|
| `privacy/**` | lane 1 |
| `tests/privacy/**` | lane 1 |
| `app/api/**`, `app/pipeline/**`, `app/llm/**`, `app/audit/**` | lane 2 |
| `app/providers/**`, `app/config.py`, `app/main.py` | lane 2 |
| `tests/platform/**` | lane 2 |
| `ui/**`, `data/**`, `evaluation/**`, `tests/demo/**` | lane 3 |
| `reports/**` | lane 3 |
| `app/contracts.py`, `CONTRACT.md`, `README.md`, root config, `Makefile` | **maintainer only** |
| `docs/**`, `ghost_*.sh`, `.gitignore` | **maintainer only** |

Lane 2 may add `tests/fakes.py` for development, but must not ship fakes as the
real path.

---

## 11. Definition of done per lane

**Lane 1 (privacy core)**

- `pytest tests/privacy -q` green.
- CLI proof: raw text → sanitized text + mapping (no originals in sanitized) →
  simulated LLM reply with placeholders reordered/dropped → restored text.
- Zero raw values appear in sanitized output for the 50-doc dataset (or a
  representative subset).
- Offline: models load with Wi-Fi off.

**Lane 2 (gateway platform)**

- `uvicorn app.main:app` boots; `/health` ok.
- `/v1/sanitize` works with lane 1 merged; `/v1/process` works end-to-end with
  Ollama.
- Tests assert the outbound payload contains no original PII (spy on provider).
- Audit row exists for success and failure cases.

**Lane 3 (demo + dataset + evidence)**

- `streamlit run ui/app.py` shows all three panes against the live gateway.
- `data/dataset.jsonl` has 50 valid, seeded, span-checked docs.
- `python -m evaluation.run` emits `reports/metrics.md` with all §9 metrics and
  a zero-leakage assertion.
