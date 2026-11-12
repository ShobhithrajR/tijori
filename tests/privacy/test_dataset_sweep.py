"""Dataset sweep test: verify zero leakage, placeholder consistency, and report P/R."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from app.contracts import EntityType
from privacy.detection import detect
from privacy.masking import mask
from privacy.vault import normalize_value


def _resolve_dataset_path() -> Path | None:
    # 1. Check local repo path
    local_candidates = [
        Path("data/dataset.jsonl"),
        Path(__file__).resolve().parents[2] / "data" / "dataset.jsonl",
    ]
    for c in local_candidates:
        if c.is_file():
            return c

    # 2. Check TIJORI_DATASET environment variable
    env_val = os.getenv("TIJORI_DATASET")
    if env_val:
        p = Path(env_val)
        if p.is_file():
            return p
        # Check in temp directory if /tmp path on Windows
        temp_candidate = Path(tempfile.gettempdir()) / p.name
        if temp_candidate.is_file():
            return temp_candidate
        if env_val.startswith("/tmp/") or env_val.startswith("\\tmp\\"):
            sub = env_val.lstrip("/\\").replace("tmp/", "").replace("tmp\\", "")
            alt = Path(tempfile.gettempdir()) / sub
            if alt.is_file():
                return alt

    # 3. Check default tempfile
    default_temp = Path(tempfile.gettempdir()) / "tijori_dataset.jsonl"
    if default_temp.is_file():
        return default_temp

    return None


def test_dataset_sweep() -> None:
    path = _resolve_dataset_path()
    if path is None:
        pytest.skip("Dataset file not found: checked data/dataset.jsonl and TIJORI_DATASET")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        pytest.skip(f"Dataset at {path} is empty")

    docs = [json.loads(line) for line in lines]

    per_type_tp: Counter[str] = Counter()
    per_type_fp: Counter[str] = Counter()
    per_type_fn: Counter[str] = Counter()
    gold_counts: Counter[str] = Counter()
    pred_counts: Counter[str] = Counter()

    for doc in docs:
        text = doc["text"]
        detection = detect(text)
        masked = mask(text, detection.entities)

        # Invariant 1: No gold original appears in sanitized_text
        for entity in doc["entities"]:
            orig = entity["text"]
            assert orig not in masked.sanitized_text, (
                f"Doc {doc['id']}: Leakage! Original {orig!r} of type {entity['type']} found in sanitized text."
            )
            if entity["type"] == "AADHAAR":
                digits = re.sub(r"[\s-]", "", orig)
                sanitized_digits = re.sub(r"[\s-]", "", masked.sanitized_text)
                assert digits not in sanitized_digits, (
                    f"Doc {doc['id']}: Leakage! Aadhaar digits {digits!r} found in sanitized text."
                )

        # Invariant 2: Repeated values reuse the same placeholder
        value_to_placeholder: dict[tuple[EntityType, str], str] = {}
        for entry in masked.mapping:
            key = (entry.type, normalize_value(entry.type, entry.original))
            if key in value_to_placeholder:
                assert value_to_placeholder[key] == entry.placeholder, (
                    f"Doc {doc['id']}: Inconsistent placeholder for {key}: "
                    f"{value_to_placeholder[key]} vs {entry.placeholder}"
                )
            else:
                value_to_placeholder[key] = entry.placeholder

        # Invariant 3: Counter occurrences match sanitized count
        for entry in masked.mapping:
            assert masked.sanitized_text.count(entry.placeholder) == entry.occurrences, (
                f"Doc {doc['id']}: Placeholder {entry.placeholder} count mismatch in sanitized text."
            )

        # Precision / recall metrics accumulation (exact span + type match per CONTRACT.md §9)
        gold_spans = {(e["type"], e["start"], e["end"]) for e in doc["entities"]}
        pred_spans = {(e.type.value, e.start, e.end) for e in detection.entities}

        tp_set = gold_spans & pred_spans
        fp_set = pred_spans - gold_spans
        fn_set = gold_spans - pred_spans

        for t, _, _ in tp_set:
            per_type_tp[t] += 1
        for t, _, _ in fp_set:
            per_type_fp[t] += 1
        for t, _, _ in fn_set:
            per_type_fn[t] += 1
        for t, _, _ in gold_spans:
            gold_counts[t] += 1
        for t, _, _ in pred_spans:
            pred_counts[t] += 1

    # Report results in test output
    report_lines = [
        "\n=================== DATASET SWEEP EVALUATION REPORT ===================",
        f"Total documents processed: {len(docs)}",
        f"Total gold entities: {sum(gold_counts.values())}",
        f"Total detected entities: {sum(pred_counts.values())}",
        f"PII Leakage count: 0",
        "",
        f"{'Entity Type':<15} {'TP':<6} {'FP':<6} {'FN':<6} {'Precision':<10} {'Recall':<10} {'Gold Spans':<10}",
        f"{'-'*15} {'-'*6} {'-'*6} {'-'*6} {'-'*10} {'-'*10} {'-'*10}",
    ]

    all_types = sorted(set(gold_counts.keys()) | set(pred_counts.keys()))
    precisions = []
    recalls = []

    for t in all_types:
        tp = per_type_tp[t]
        fp = per_type_fp[t]
        fn = per_type_fn[t]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precisions.append(p)
        recalls.append(r)
        report_lines.append(f"{t:<15} {tp:<6} {fp:<6} {fn:<6} {p:<10.3f} {r:<10.3f} {gold_counts[t]:<10}")

    macro_p = sum(precisions) / len(precisions) if precisions else 0.0
    macro_r = sum(recalls) / len(recalls) if recalls else 0.0
    report_lines.append(f"{'-'*15} {'-'*6} {'-'*6} {'-'*6} {'-'*10} {'-'*10} {'-'*10}")
    report_lines.append(f"{'MACRO AVERAGE':<15} {'':<6} {'':<6} {'':<6} {macro_p:<10.3f} {macro_r:<10.3f} {sum(gold_counts.values()):<10}")
    report_lines.append("=======================================================================\n")

    print("\n".join(report_lines))
