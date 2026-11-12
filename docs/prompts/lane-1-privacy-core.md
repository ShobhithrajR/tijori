# Lane 1 prompt — Privacy Core

You are the Lane 1 agent for a 6-hour hackathon build. Work independently.

- Repo: `https://github.com/Shreyas-a-j/tijori.git`
- Branch: `agent/privacy-core` (create it from `main`; the scaffold is already on main)
- Read first: `CONTRACT.md` (§2, §3, §8, §11), `app/contracts.py`, `README.md`, `docs/PS02.md` §3.1–3.2 and §5.
- Env: Python 3.14 `.venv`. Activate it. Presidio, GLiNER, spaCy + `en_core_web_sm`, torch CPU are installed. **Do not add dependencies.**
- You own only: `privacy/**` and `tests/privacy/**`. Do not edit `CONTRACT.md`, `app/contracts.py`, `app/main.py`, root configs, or another lane's files.

## Objective

Implement the local PII detection + masking + reinsertion core. Timebox: **2.5 hours**. Working and tested beats clever.

## Tasks (in order)

1. **India recognizers** — `privacy/detection/india.py`
   Use `presidio_analyzer` `PatternRecognizer`/`Pattern` and wrap them in a configured `AnalyzerEngine`:
   - AADHAAR: `\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b`, first digit 2–9, context `aadhaar/aadhar/uidai/आधार`.
   - PAN: `\b[A-Z]{5}[0-9]{4}[A-Z]\b`, context `pan/income tax`.
   - GSTIN: `\b\d{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b`, context `gstin/gst`.
   - VOTER_ID: `\b[A-Z]{3}[0-9]{7}\b`, context `voter/epic/election`.
   - PASSPORT: `\b[A-Z][0-9]{7}\b`, context `passport`.
   Filter weak matches without context. Add positive and negative tests per type.

2. **NER for names/addresses** — `privacy/detection/ner.py`
   - GLiNER `urchade/gliner_multi_pii-v1`, labels `["person", "name", "address", "location"]`, threshold ~0.4. Map person/name → PERSON, address/location → ADDRESS.
   - Merge with spaCy `en_core_web_sm` (`PERSON`, `GPE`, `LOC`).
   - Deduplicate by `(type, start, end)`. Convert to `DetectedEntity` with `source`.
   - Run both on every input; do not depend on language detection. Hinglish is expected.

3. **Public detect API** — `privacy/detection/__init__.py`
   `detect(text, *, language="auto") -> DetectionResult`.
   Merge Presidio + NER, resolve overlaps using `ENTITY_PRIORITY` (higher priority wins; on ties keep the longer span), drop empty/invalid spans, sort by `start`, set `duration_ms`. Never raise on ordinary text.

4. **Masking** — `privacy/masking/__init__.py`
   `mask(text, entities) -> MaskingResult`.
   Use `privacy.vault.PlaceholderVault`. Replace spans right-to-left. Reuse placeholders for repeated equivalent values. Return `sanitized_text`, ordered `mapping`, `entities`, `duration_ms`. The sanitized text must contain **none** of the original values.

5. **Reinsertion** — `privacy/reinsertion/__init__.py`
   `reinsert(text, mapping) -> ReinsertionResult`.
   Use `PLACEHOLDER_SCAN_RE` from `app/contracts.py`. Match tokens case-insensitively (`<person_1>` → `<PERSON_1>`). Substitute only the token, never surrounding text. Compute `missing` (mapping entries absent from the LLM text) and `unknown` (tokens present but not in the mapping). Never fuzzy-match or repair damaged tokens.

6. **CLI proof** — `privacy/__main__.py`
   `python -m privacy` reads the PS-02 sample, prints sanitized text, mapping (placeholder → type only), a simulated LLM reply with placeholders reordered/dropped, and the restored text. Keep it under 60 lines.

7. **Tests** — `tests/privacy/`
   Cover: each recognizer (positive/negative), names/addresses, Hinglish sample, overlap resolution, repeated-value consistency, zero leakage in `sanitized_text`, reinsertion after reorder, dropped placeholder → `missing`, malformed token → `unknown`, and no cross-person substitution.

## Acceptance

```bash
source .venv/bin/activate
python -m pytest tests/privacy -q
python -m privacy
```

`tests/privacy` must be green. If GLiNER is too slow or unavailable, fall back to spaCy + regex, keep the same interface, and report the limitation.

## Finish

Commit on `agent/privacy-core` with conventional commits, push the branch, open a PR against `main`. **Do not merge.** Final message: files changed, test output, what is stubbed, and anything lane 2/3 must know. Stop at 2.5 hours.
