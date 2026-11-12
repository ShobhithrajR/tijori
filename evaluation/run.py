"""Evaluation harness for Tijori (lane 3).

Runs the seeded dataset through the frozen gateway contract and writes
``reports/metrics.md``:

  * per-type and per-doc-type detection precision/recall (exact span + type)
  * PII leakage scan of sanitized text / outbound payloads
  * reinsertion verification on 5 documents via ``POST /v1/process``
  * gateway-only and end-to-end latency p50/p95

Usage::

    python -m evaluation.run            # needs the API on TIJORI_API_URL

Exit codes: 0 = report written and leakage is zero, 1 = leakage found,
2 = gateway offline (report written as blocked).
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "dataset.jsonl"
REPORT_PATH = ROOT / "reports" / "metrics.md"
DATASET_SEED = 2026
DEFAULT_API_URL = os.getenv("TIJORI_API_URL", "http://127.0.0.1:8000")
PROCESS_DOC_IDS = ("loan_001", "kyc_002", "support_003", "insurance_004", "loan_005")


# ---------------------------------------------------------------------------
# Pure helpers (also covered by tests/demo/test_eval.py)
# ---------------------------------------------------------------------------


def load_dataset(path: Path = DATASET_PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - git is optional at report time
        return "unknown"


def leak_occurrences(entity: dict, payload: str) -> int:
    """Occurrences of one gold value in a payload (Aadhaar also de-formatted)."""
    value = entity.get("text", "")
    variants = {value}
    if entity.get("type") == "AADHAAR":
        variants.add(re.sub(r"[\s-]", "", value))
    best = 0
    for variant in variants:
        if not variant:
            continue
        if variant.isdigit():
            best = max(best, payload.count(variant))
        else:
            best = max(best, payload.casefold().count(variant.casefold()))
    return best


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _md_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def score_predictions(doc: dict, response: dict) -> tuple[dict, dict]:
    """Return (per_type accumulators, doc_type accumulators) for one document."""
    gold = {(e["type"], e["start"], e["end"]) for e in doc["entities"]}
    predicted = {
        (e.get("type"), e.get("start"), e.get("end"))
        for e in response.get("entities", [])
        if isinstance(e.get("start"), int) and isinstance(e.get("end"), int)
    }
    tp = gold & predicted
    fp = predicted - gold
    fn = gold - predicted

    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for entity_type, _, _ in tp:
        per_type[entity_type][0] += 1
    for entity_type, _, _ in fp:
        per_type[entity_type][1] += 1
    for entity_type, _, _ in fn:
        per_type[entity_type][2] += 1
    return per_type, {"tp": len(tp), "fp": len(fp), "fn": len(fn)}


# ---------------------------------------------------------------------------
# Live evaluation
# ---------------------------------------------------------------------------


def _headers() -> str:
    return "\n".join([
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- Dataset seed: `{DATASET_SEED}`",
        f"- Dataset: `{DATASET_PATH.relative_to(ROOT)}`",
        f"- Gateway commit: `{commit_hash()}`",
        f"- API: `{DEFAULT_API_URL}`",
    ])


def write_blocked_report(docs: list[dict], reason: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "# Tijori Evaluation Report — blocked on gateway\n\n"
        f"{_headers()}\n\n"
        "## Status\n\n"
        f"**Blocked on gateway:** {reason}\n\n"
        "The seeded dataset is generated and its span checks pass. Start the gateway "
        "(`uvicorn app.main:app`), then rerun `python -m evaluation.run` to fill in "
        "detection, leakage, reinsertion and latency metrics.\n\n"
        f"- Documents available: {len(docs)}\n"
        f"- Labelled entities: {sum(len(doc['entities']) for doc in docs)}\n",
        encoding="utf-8",
    )


def evaluate(docs: list[dict], catch_all: str) -> tuple[int, str]:
    types = sorted({entity["type"] for doc in docs for entity in doc["entities"]})
    per_type: dict[str, list[int]] = {entity_type: [0, 0, 0] for entity_type in types}
    per_doc_type: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    doc_counts: Counter = Counter(doc["doc_type"] for doc in docs)

    leaks: list[dict] = []
    sanitize_failures: list[str] = []
    sanitize_latencies: list[int] = []
    processed: list[dict] = []

    with httpx.Client(base_url=catch_all, timeout=60.0) as client:
        for doc in docs:
            try:
                response = client.post(
                    "/v1/sanitize",
                    json={"text": doc["text"], "doc_type": doc["doc_type"], "purpose": "general"},
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:  # noqa: BLE001 - report partial runs honestly
                sanitize_failures.append(f"{doc['id']}: {exc}")
                continue

            sanitize_latencies.append(int(payload.get("duration_ms", 0)))
            doc_type_stats, totals = score_predictions(doc, payload)
            for entity_type, (tp, fp, fn) in doc_type_stats.items():
                bucket = per_type.setdefault(entity_type, [0, 0, 0])
                bucket[0] += tp
                bucket[1] += fp
                bucket[2] += fn
            bucket = per_doc_type[doc["doc_type"]]
            bucket[0] += totals["tp"]
            bucket[1] += totals["fp"]
            bucket[2] += totals["fn"]

            sanitized = payload.get("sanitized_text", "")
            for entity in doc["entities"]:
                count = leak_occurrences(entity, sanitized)
                if count:
                    leaks.append({
                        "doc": doc["id"],
                        "type": entity["type"],
                        "value": entity["text"],
                        "count": count,
                    })

        selected = [doc for doc in docs if doc["id"] in PROCESS_DOC_IDS][:5]
        for doc in selected:
            try:
                response = client.post(
                    "/v1/process",
                    json={
                        "text": doc["text"],
                        "doc_type": doc["doc_type"],
                        "purpose": "general",
                        "task": "summarize",
                        "instruction": "Summarize in 3 bullet points and keep all placeholders.",
                    },
                    timeout=180.0,
                )
                response.raise_for_status()
                result = response.json()
            except Exception as exc:  # noqa: BLE001
                processed.append({"doc": doc["id"], "error": str(exc)})
                continue

            outbound = result.get("outbound_payload", "")
            for entity in doc["entities"]:
                count = leak_occurrences(entity, outbound)
                if count:
                    leaks.append({
                        "doc": f"{doc['id']} (process)",
                        "type": entity["type"],
                        "value": entity["text"],
                        "count": count,
                    })

            final_text = result.get("final_text", "")
            mapping: dict[str, str] = {}
            for view in result.get("entities", []):
                start, end = view.get("start"), view.get("end")
                if not isinstance(start, int) or not isinstance(end, int):
                    continue
                if doc["text"][start:end]:
                    mapping[view.get("placeholder", "")] = doc["text"][start:end]

            confirmed = dropped = unreplaced = 0
            for placeholder, original in mapping.items():
                if not placeholder:
                    continue
                if placeholder in final_text:
                    unreplaced += 1
                elif original in final_text:
                    confirmed += 1
                else:
                    dropped += 1

            stats = result.get("reinsertion") or {}
            processed.append({
                "doc": doc["id"],
                "latency_ms": int(result.get("latency_ms", 0)),
                "api_replaced": int(stats.get("replaced", 0)),
                "api_missing": len(stats.get("missing") or []),
                "api_unknown": len(stats.get("unknown") or []),
                "confirmed": confirmed,
                "unreplaced": unreplaced,
                "dropped": dropped,
                "placeholder_left": any(p in final_text for p in mapping),
            })

    leakage_count = sum(item["count"] for item in leaks)
    return leakage_count, _render_report(
        docs=docs,
        leakage_count=leakage_count,
        leaks=leaks,
        per_type=per_type,
        per_doc_type=per_doc_type,
        doc_counts=doc_counts,
        sanitize_failures=sanitize_failures,
        sanitize_latencies=sanitize_latencies,
        processed=processed,
    )


def _render_report(
    *,
    docs: list[dict],
    leakage_count: int,
    leaks: list[dict],
    per_type: dict[str, list[int]],
    per_doc_type: dict[str, list[int]],
    doc_counts: Counter,
    sanitize_failures: list[str],
    sanitize_latencies: list[int],
    processed: list[dict],
) -> str:
    detection_rows = []
    precisions: list[float] = []
    recalls: list[float] = []
    for entity_type in sorted(per_type):
        tp, fp, fn = per_type[entity_type]
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        if precision is not None:
            precisions.append(precision)
        if recall is not None:
            recalls.append(recall)
        detection_rows.append([
            entity_type, tp, fp, fn, _fmt(precision), _fmt(recall), tp + fn,
        ])

    if detection_rows:
        totals = [sum(per_type[t][i] for t in per_type) for i in range(3)]
        detection_rows.append([
            "**macro**",
            totals[0],
            totals[1],
            totals[2],
            _fmt(sum(precisions) / len(precisions) if precisions else None),
            _fmt(sum(recalls) / len(recalls) if recalls else None),
            totals[0] + totals[2],
        ])

    doc_type_rows = []
    for doc_type in sorted(per_doc_type):
        tp, fp, fn = per_doc_type[doc_type]
        doc_type_rows.append([
            doc_type, doc_counts[doc_type], tp, fp, fn,
            _fmt(_ratio(tp, tp + fp)), _fmt(_ratio(tp, tp + fn)),
        ])

    if leaks:
        leak_summary = "\n".join(
            f"- `{item['doc']}` · {item['type']} · {item['count']} occurrence(s): `{item['value']}`"
            for item in leaks[:20]
        )
    else:
        leak_summary = "No gold value was found in any sanitized text or outbound payload."

    sanitize_success = len(docs) - len(sanitize_failures)
    failure_block = (
        "\n".join(f"- {failure}" for failure in sanitize_failures[:10])
        if sanitize_failures else "- None"
    )

    process_rows = []
    confirmed = api_replaced = unknown = unreplaced = 0
    process_latencies: list[int] = []
    for item in processed:
        if "error" in item:
            process_rows.append([item["doc"], "ERROR", "—", "—", "—", "—", "—", "—"])
            continue
        process_latencies.append(item["latency_ms"])
        confirmed += item["confirmed"]
        api_replaced += item["api_replaced"]
        unknown += item["api_unknown"]
        unreplaced += item["unreplaced"]
        process_rows.append([
            item["doc"], item["latency_ms"], item["api_replaced"], item["api_missing"],
            item["api_unknown"], item["confirmed"], item["dropped"],
            "yes" if item["placeholder_left"] else "no",
        ])

    denominator = api_replaced + unknown
    reinsertion_accuracy = _ratio(api_replaced, denominator)
    local_denominator = confirmed + unreplaced + unknown
    local_accuracy = _ratio(confirmed, local_denominator)
    process_errors = sum(1 for item in processed if "error" in item)

    process_p50 = percentile(process_latencies, 50)
    process_p95 = percentile(process_latencies, 95)
    sanitize_p50 = percentile(sanitize_latencies, 50)
    sanitize_p95 = percentile(sanitize_latencies, 95)

    zero_leak = leakage_count == 0
    assertion = (
        "PASS — leakage count is 0." if zero_leak
        else f"FAIL — leakage count is {leakage_count}; raw PII reached the outbound payload."
    )

    return f"""# Tijori Evaluation Report

{_headers()}

## Summary

| Metric | Result |
|---|---|
| Documents sanitized | {sanitize_success}/{len(docs)} |
| PII leakage count (target 0) | **{leakage_count}** |
| Zero-leakage assertion | **{assertion}** |
| Macro precision | {_fmt(sum(precisions) / len(precisions) if precisions else None)} |
| Macro recall | {_fmt(sum(recalls) / len(recalls) if recalls else None)} |
| Reinsertion accuracy (API-reported) | {_fmt(reinsertion_accuracy)} |

Detection uses exact span + entity-type matching against the gold labels in
`data/dataset.jsonl` (seed `{DATASET_SEED}`). Failed sanitize requests are excluded
from detection metrics and listed below.

## PII leakage

**Leakage count: {leakage_count}** — occurrences of any gold original value (plus
the space/hyphen-stripped Aadhaar form) in `sanitized_text` or `outbound_payload`.

{leak_summary}

## Detection quality

{_md_table(
    ["Entity type", "TP", "FP", "FN", "Precision", "Recall", "Gold spans"],
    detection_rows,
)}

Macro precision/recall are the unweighted means over entity types that have gold
labels (or predictions) in this run.

### Per document type

{_md_table(
    ["Document type", "Docs", "TP", "FP", "FN", "Precision", "Recall"],
    doc_type_rows,
)}

### Failed sanitize requests

{failure_block}

## Reinsertion

Five documents were sent through `POST /v1/process` with task `summarize`.

{_md_table(
    ["Document", "Latency ms", "API replaced", "API missing", "API unknown", "Confirmed", "Dropped", "Placeholder left"],
    process_rows,
)}

- API-reported accuracy: **{_fmt(reinsertion_accuracy)}** (`replaced / (replaced + unknown)`).
- Locally verified accuracy: **{_fmt(local_accuracy)}** (confirmed originals / (confirmed + unreplaced + unknown)).
- Confirmed substitutions: {confirmed}; unreplaced placeholders left in `final_text`: {unreplaced}.
- Dropped placeholders (LLM omitted them) are not counted as failures.
- Process calls failed: {process_errors}.

## Latency

{_md_table(
    ["Measurement", "n", "p50 ms", "p95 ms", "What it includes"],
    [
        ["Gateway sanitize (`/v1/sanitize` `duration_ms`)", len(sanitize_latencies),
         _fmt(sanitize_p50, 1), _fmt(sanitize_p95, 1), "detection + masking only, no LLM"],
        ["End-to-end `/v1/process` (`latency_ms`)", len(process_latencies),
         _fmt(process_p50, 1), _fmt(process_p95, 1), "gateway + LLM call + reinsertion"],
    ],
)}

Provider-only latency (a direct call to the model) is not exposed by the gateway
contract, so gateway overhead versus a direct provider call is **not measured** in
this run.

## Known limitations

- Exact span + type matching is strict: a detector that finds the right value with
  a different boundary is scored as both a false positive and a false negative.
- `OTHER` gold values are synthetic identifiers (policy/customer IDs); detectors
  are not guaranteed to support that label.
- The API does not return the raw LLM response, so the reinsertion denominator
  relies on the gateway's `replaced` and `unknown` counts (cross-checked locally
  against `final_text`).
- Reinsertion is measured on 5 documents only.
- The dataset is synthetic and generated by `data/generate.py`; it is not a
  substitute for a production-annotated corpus.
"""


def main() -> int:
    if not DATASET_PATH.exists():
        print(f"Dataset missing at {DATASET_PATH}. Run `python -m data.generate` first.")
        return 2
    docs = load_dataset()
    if len(docs) != 50:
        print(f"Warning: expected 50 documents, found {len(docs)}.")

    api_url = DEFAULT_API_URL.rstrip("/")
    try:
        health = httpx.get(f"{api_url}/health", timeout=3.0)
        online = health.status_code == 200
    except Exception:  # noqa: BLE001
        online = False

    if not online:
        reason = f"no healthy gateway at `{api_url}` (`GET /health` did not return 200)."
        write_blocked_report(docs, reason)
        print(f"API offline at {api_url}. Wrote blocked report to {REPORT_PATH}.")
        print("Dataset generation and tests are independent of the gateway.")
        return 2

    leakage_count, report = evaluate(docs, api_url)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(f"Leakage count: {leakage_count}")
    if leakage_count > 0:
        print("FAIL: raw PII found in outbound payloads.")
        return 1
    print("PASS: zero leakage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
