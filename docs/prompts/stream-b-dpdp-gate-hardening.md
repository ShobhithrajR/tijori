# Stream B prompt — DPDP gate hardening

You are Stream B in a 2-hour parallel hardening sprint on Tijori (PS-02). Work
independently; Stream A is editing `ui/app.py` at the same time.

- Repo: `https://github.com/Shreyas-a-j/tijori.git`
- Branch: `agent/stream-b-gate` (create from `main` = `4fb65eb`)
- Read first: `CONTRACT.md` §4–§5, `app/api/routes.py`, `app/main.py`,
  `app/audit/repository.py`, `app/config.py`, `tests/platform/test_gateway.py`,
  `docs/DPDP-ALIGNMENT.md`, `.env.example`.
- Env: Python 3.14 `.venv`, FastAPI/pytest installed. **Do not add dependencies.**
- You own only: `app/api/**`, `app/main.py`, `app/audit/**`, `app/config.py`,
  `tests/platform/**`, `docs/DPDP-ALIGNMENT.md`, `.env.example`.
  Do not edit `ui/**`, `privacy/**`, `evaluation/**`, `reports/**`, `CONTRACT.md`,
  `app/pipeline/**`, `app/contracts.py`.

## Shared contract (fixed before the sprint — implement exactly this)

```text
TIJORI_API_KEY              unset or empty -> auth disabled (dev default)
header on /v1/*             X-API-Key: <key>
/health, /docs, /openapi.json   unauthenticated
401 body                    {"detail": "unauthorized"}
```

## Tasks (in order)

1. **Config** — `app/config.py`
   - `api_key: str = _env("TIJORI_API_KEY", "")`
   - `audit_retention_days: int = int(_env("TIJORI_AUDIT_RETENTION_DAYS", "365"))`
   - Document both in `.env.example` with the "unset = disabled" semantics.

2. **API-key auth** — `app/main.py` (middleware, applies to every `/v1/*` path)
   - Compare with `hmac.compare_digest` (constant time), reading the header from
     the raw request; return `JSONResponse({"detail": "unauthorized"}, 401)` with
     `WWW-Authenticate: X-API-Key` on missing or wrong key.
   - No auth at all when `settings.api_key == ""`. Read the key per request
     (`settings` is a frozen module-level instance, so re-read the env or use a
     small accessor) so tests can toggle it with `monkeypatch.setenv`.
   - Never log the presented key, not even truncated.

3. **Audit retention** — `app/audit/repository.py`
   - `purge_older_than(days: int, *, dry_run: bool = False) -> int` deleting rows
     whose `created_at` is older than `now - days` (ISO-8601 UTC strings already
     in the table, so string comparison is valid).
   - CLI: `python -m app.audit.retention --days 365 [--dry-run]`, printing the
     number of rows purged or that would be purged.
   - Startup (`lifespan` in `app/main.py`): call the dry-run once and log
     `audit retention: would purge N rows older than D days`. **Do not delete on
     startup** — deletion stays an explicit operator action.

4. **Monitoring signal** — `app/api/routes.py`
   - `logger.warning` with structured `extra={"request_id": ..., "leakage_count": ...}`
     when a returned record has `leakage_count > 0`.
   - Same on provider failure (`ProviderFailure`/502 path) and on
     `status="error"`.
   - Log ids, counts, and status only — never text, originals, or the mapping.

5. **Tests** — `tests/platform/`
   - Auth: 401 without header, 401 with a wrong key, 200 with the right key,
     `/health` open, and everything 200 when the env var is unset.
   - Purge: insert an audit row with an old `created_at` plus one new row, call
     `purge_older_than`, assert only the old row is gone; `dry_run=True` deletes
     nothing and returns the count; the CLI exits 0.
   - Alerting: `caplog` sees one warning for a leakage record and for an error
     record; assert the log line contains no original value.
   - Keep the existing PII-free-audit assertions green.

6. **Docs** — `docs/DPDP-ALIGNMENT.md`
   - Move Rule 6(1)(b) from Partial to **Implemented** (API-key gate, localhost
     default), Rule 6(1)(e) and Rule 8 from Gap/Partial to **Implemented** where
     the purge job and retention default exist.
   - Rule 6(1)(c) stays **Partial** (audit + warning log, still no anomaly
     detection) — do not overclaim.
   - Add the exact commands used as evidence next to each changed row.

## Acceptance

```bash
source .venv/bin/activate
python -m pytest tests/platform -q      # green, no network, no model
python -m pytest -q                     # full suite still green
```

Manual check to record in the PR:

```bash
TIJORI_API_KEY=secret uvicorn app.main:app --port 8000
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/v1/audit        # 401
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-API-Key: secret' localhost:8000/v1/audit  # 200
curl -s localhost:8000/health                                           # 200, no key
```

Do not regenerate `reports/metrics.md` and do not touch the pipeline or the
contract. If a task requires an edit outside your file set, stop and report it
instead of editing.
