# Tijori Evaluation Report — blocked on gateway

- Generated: 2026-11-12 08:46:37 UTC
- Dataset seed: `2026`
- Dataset: `data\dataset.jsonl`
- Gateway commit: `10b2d47`
- API: `http://127.0.0.1:8000`

## Status

**Blocked on gateway:** no healthy gateway at `http://127.0.0.1:8000` (`GET /health` did not return 200).

The seeded dataset is generated and its span checks pass. Start the gateway (`uvicorn app.main:app`), then rerun `python -m evaluation.run` to fill in detection, leakage, reinsertion and latency metrics.

- Documents available: 50
- Labelled entities: 362
