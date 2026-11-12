# Lane 3 prompt — Demo, Dataset & Evidence

You are the Lane 3 agent for a 6-hour hackathon build. Work independently.

- Repo: `https://github.com/Shreyas-a-j/tijori.git`
- Branch: `agent/demo-eval` (create it from `main`)
- Read first: `CONTRACT.md` (§4, §6, §8, §9, §11), `app/contracts.py`, `.env.example`, `docs/PS02.md` §3.6–3.8 and §6.
- Env: Python 3.14 `.venv`, Streamlit/httpx/pytest installed. API may not be merged yet. **Do not add dependencies.**
- You own only: `ui/**`, `data/**`, `evaluation/**`, `tests/demo/**`, `reports/**`. Do not edit `CONTRACT.md`, `app/contracts.py`, `privacy/**`, `app/**`, or root configs.

## Objective

Ship the 3-pane Streamlit demo, the seeded 50-document labeled dataset, and the metrics report. Timebox: **2.5 hours**. Build against the frozen HTTP contract so you never wait for another lane.

## Tasks (in order)

1. **Dataset generator** — `data/generate.py`
   - `seed=2026`, deterministic, no network, stdlib only.
   - Build each document from segments: `[("text", "..."), ("entity", "PERSON", "Rahul Sharma"), ...]`, render sequentially, and compute exact `start`/`end` offsets while rendering. This guarantees valid labels.
   - 50 documents: `loan_application`, `kyc`, `support_ticket`, `insurance_claim` (≥10 each); ≥15 `hi-en` code-mixed; every entity type in `CONTRACT.md` §2 appears ≥10 times.
   - Realistic Indian formats: Aadhaar with spaces/hyphens, PAN, GSTIN with valid state code, EPIC, passport, Indian addresses, phone, email, DOB.
   - Write `data/dataset.jsonl` with the exact schema in §8.
   - `tests/demo/test_dataset.py`: exactly 50; doc-type and language minimums; every span slice equals `entities[].text`; type coverage.

2. **Streamlit UI** — `ui/app.py`
   - Sidebar: API URL (`TIJORI_API_URL`), doc type, task (`summarize`/`extract`), Run button, sample loader.
   - Three columns: **A** original editable text; **B** exact `outbound_payload` in `st.code`, entity table (type, placeholder, span), placeholder counts, and a green/red **leakage badge**; **C** `final_text` plus `reinsertion` stats.
   - Leakage badge: for every entity, slice `text[start:end]` from the original and check it is absent from `outbound_payload` (also check the Aadhaar value with spaces/hyphens removed). Zero findings → green "No raw PII in outbound payload".
   - Audit browser: `GET /v1/audit?limit=20`, dataframe of time, doc type, entity counts, provider/model, latency, leakage count.
   - Handle API errors with `st.error`; never crash.
   - If the API is down, still render the layout and show a clear "API offline" message.

3. **Evaluation** — `evaluation/run.py`
   - Load `data/dataset.jsonl`; call `POST /v1/sanitize` for all 50 via `httpx` (`TIJORI_API_URL`).
   - Per-type precision/recall using exact span + type match; macro P/R; per-doc-type P/R.
   - Leakage: check every gold original value (and Aadhaar space/hyphen-stripped form) against the returned `outbound_payload` / `sanitized_text`. Target 0.
   - Reinsertion: run `POST /v1/process` on 5 docs; for each placeholder the LLM retained, verify `final_text` contains the original value and no placeholder remains; use the API's `reinsertion` stats for dropped/unknown.
   - Latency: p50/p95 for `/v1/process` (5 docs) and gateway sanitize duration; label LLM vs gateway time clearly.
   - Write `reports/metrics.md` with a header (seed, commit hash, timestamp), tables, the zero-leakage assertion, and a short "known limitations". Exit nonzero if leakage > 0.
   - If the API is offline, exit with a clear message after dataset generation/tests still pass.

## Acceptance

```bash
source .venv/bin/activate
python -m data.generate          # add data/__init__.py
python -m pytest tests/demo -q
streamlit run ui/app.py
python -m evaluation.run         # requires API on :8000
```

Do not fabricate metrics. If the API is unavailable, mark the report "blocked on gateway" and report it.

## After lane 2 merges

Rebase on `main`, start the API and Streamlit, run `python -m evaluation.run`,
confirm the leakage count is 0 and `reports/metrics.md` is generated, then push
the rebased branch. Do not merge.

## Finish

Commit on `agent/demo-eval`, push, open a PR against `main`. **Do not merge.** Final message: files changed, dataset stats, test output, sample UI behavior, and what still needs the merged gateway. Stop at 2.5 hours.
