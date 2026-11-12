# Stream A prompt — Demo truth (UI + runbook)

You are Stream A in a 2-hour parallel hardening sprint on Tijori (PS-02). Work
independently; Stream B is editing the gateway at the same time.

- Repo: `https://github.com/Shreyas-a-j/tijori.git`
- Branch: `agent/stream-a-demo` (create from `main` = `4fb65eb`)
- Read first: `README.md`, `ui/app.py`, `tests/demo/*`, `CONTRACT.md` §4 (`ProcessRequest`), `reports/metrics.md`.
- Env: Python 3.14 `.venv`, Streamlit + pytest already installed. **Do not add dependencies.**
- You own only: `ui/app.py`, `README.md`, `docs/screenshots/**`, `tests/demo/**`.
  Do not edit `app/**`, `privacy/**`, `evaluation/**`, `reports/**`, `CONTRACT.md`, root configs.

## Shared contract (fixed before the sprint — do not change it)

Stream B implements auth; you only send it.

```text
TIJORI_API_KEY              unset or empty -> auth disabled (dev default)
header on /v1/*             X-API-Key: <key>
/health                     stays unauthenticated
401 body                    {"detail": "unauthorized"}
```

## Problem to fix

With the current default instruction ("Summarize the following document."),
`qwen2.5:3b` largely echoes the document. On screen the "Initial document" and
"Final response" panes look identical, so the demo fails to show that the
gateway does anything. The UI also cannot send a custom instruction, and will
break the moment auth is enabled.

## Tasks (in order)

1. **Instruction field** — `ui/app.py`
   - Add a `st.text_area("Instruction", key="instruction")` in the left sidebar,
     below the Task selector.
   - Default it (via `session_state`) to:

     ```text
     Summarize this document in 3 short bullet points.
     Do not copy the document. Keep every placeholder like <PERSON_1> exactly as written.
     ```

   - Send it as `"instruction": st.session_state.instruction` in the
     `POST /v1/process` JSON, only when non-empty (the field is optional in the
     contract).
   - Show the instruction actually used in the result caption (truncate to ~80
     chars) so the demo can point at it.

2. **Optional API key** — `ui/app.py`
   - `key = os.getenv("TIJORI_API_KEY", "")`; if set, send
     `headers={"X-API-Key": key}` on `/v1/process` and the `/v1/audit` GET.
   - On `401`, show "Gateway rejected the API key (check TIJORI_API_KEY)" — no
     traceback, no retry loop.
   - Never print, log, or place the key in a widget, `st.write`, or the audit pane.

3. **Do not regress the offline path**
   - With the API down the app must still render both tabs and the "API offline"
     message; the instruction textarea must render too.
   - No `localStorage`, no console writes of document text (checked by
     `tests/demo/test_ui_leakage.py`).

4. **Tests** — `tests/demo/test_ui_instruction.py`
   - `AppTest` with a stubbed `httpx.post` that records `json=` and `headers=`.
   - Assert: the default instruction is sent; a custom instruction replaces it;
     `X-API-Key` is sent when `TIJORI_API_KEY` is set and absent when it is not.
   - No network, no LLM call. Keep the existing tests untouched and green.

5. **Runbook** — `README.md`
   - Demo order: `ollama serve` → pre-warm call → `uvicorn app.main:app --port 8000`
     → `streamlit run ui/app.py`.
   - Recommend `OLLAMA_KEEP_ALIVE=30m` for the pre-warm, name one good sample
     document, and state the expected latency (`/v1/process` p50 ≈ 4.8 s warm,
     sanitize p50 ≈ 0.26 s).
   - Add a short "Auth enabled" variant: `export TIJORI_API_KEY=...` before
     starting uvicorn, Streamlit picks it up from the same shell.
   - Replace the demo screenshots in `docs/screenshots/` with ones taken using
     the new instruction, where the final response is visibly shorter than the
     input.

## Acceptance

```bash
source .venv/bin/activate
python -m pytest tests/demo -q          # green, no network
streamlit run ui/app.py                 # manual: response visibly != input
```

Manual check to record in the PR: paste one dataset document, run, confirm the
final response is shorter, every placeholder restored, and the audit pane shows
one row with the new instruction's request.

Do not regenerate `reports/metrics.md`; detection is unchanged and the numbers
stay valid. Commit in small steps, report the exact pytest output, and say what
you could not verify.
