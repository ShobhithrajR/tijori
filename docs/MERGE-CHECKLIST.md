# Reviewer / merger checklist

You are the only person who merges. Coders push branches and open PRs; they do
not merge. Work in this order: lane 1 → lane 2 → lane 3. Never merge a PR that
edits `CONTRACT.md` or `app/contracts.py` without explicitly deciding to accept
the contract change first.

## 0. One-time setup

```bash
cd tijori
source .venv/bin/activate
python -m pytest -q          # main must be green before any merge
```

## 1. Verify a lane PR

```bash
git fetch origin
gh pr checkout <PR-number>    # or: git checkout <branch> && git pull
source .venv/bin/activate
python -m pytest -q
git diff --name-only main...HEAD
```

Reject or ask the coder to move files if the diff touches another lane's paths.

### Contract guard

```bash
git diff main...HEAD -- CONTRACT.md app/contracts.py
```

Must be empty. If not, stop and review the interface change with the coder.

### Secrets guard

```bash
git diff --name-only main...HEAD | grep -E '\.env$|\.key$|\.pem$' && echo "REJECT"
```

Also confirm no API keys appear in the diff.

## 2. Lane 1 — privacy core

```bash
python -m privacy
python -m pytest tests/privacy -q
```

Pass criteria:

- Sanitized output contains placeholders only; no raw Aadhaar/PAN/name.
- Repeated values reuse the same placeholder.
- The CLI shows reorder + dropped-placeholder handling.
- `tests/privacy` green.

## 3. Lane 2 — gateway platform

Terminal A:

```bash
uvicorn app.main:app --port 8000
```

Terminal B:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/v1/sanitize \
  -H 'content-type: application/json' \
  -d '{"text":"My name is Rahul Sharma. My Aadhaar number is 1234-5678-9012 and my PAN is ABCDE1234F.","doc_type":"kyc"}'
```

Pass criteria:

- Response has `sanitized_text`, `entities`, `counts`, and **no original values**.
- Placeholders are `<PERSON_1>`, `<AADHAAR_1>`, `<PAN_1>`.
- Then test the real LLM path:

```bash
curl -s -X POST localhost:8000/v1/process \
  -H 'content-type: application/json' \
  -d '{"text":"My name is Rahul Sharma. My Aadhaar number is 1234-5678-9012 and my PAN is ABCDE1234F.","task":"summarize"}'
```

- `outbound_payload` contains no `Rahul Sharma`, no `1234-5678-9012`.
- `final_text` has the originals restored.
- `GET /v1/audit?limit=5` shows the request with model and latency.
- Audit DB contains no raw values:

```bash
python -c "import sqlite3;c=sqlite3.connect('data/audit.db');print(c.execute('select outbound_payload from audit_requests order by rowid desc limit 3').fetchall())"
```

## 4. Lane 3 — demo / dataset / evidence

```bash
python -m pytest tests/demo -q
python -c "import json;rows=[json.loads(l) for l in open('data/dataset.jsonl')];print(len(rows), {r['doc_type'] for r in rows})"
streamlit run ui/app.py     # open http://127.0.0.1:8501
python -m evaluation.run
```

Pass criteria:

- Exactly 50 docs, all 4 doc types present.
- UI shows three panes; outbound pane shows placeholders and a green leakage badge.
- `reports/metrics.md` exists, leakage count is 0, precision/recall and latency tables are populated.

## 5. Merge

```bash
git checkout main
git pull
git merge --no-ff agent/<lane>
python -m pytest -q
git push origin main
```

After merging lane 1, tell lane 2 to rebase and finish the real e2e before its
merge. After lane 2, tell lane 3 to rebase and run the UI + evaluation before
its merge. If something breaks, send it back to the coder who owns those files;
do not patch other people's lanes yourself.

## 6. Final demo check (hour 5.5)

- `make test` green on `main`.
- `/v1/process` with the PS-02 sample: outbound payload has zero raw PII.
- UI three panes + audit tab work.
- `reports/metrics.md` shows leakage = 0.
- Ollama model loaded (`ollama ps`), API and UI both running.
- One dry run end to end, then freeze.
