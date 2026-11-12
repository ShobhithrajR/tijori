"""CLI proof for the lane 1 privacy core (PS-02 sample round-trip).

    python -m privacy
    python -m privacy --dataset
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

from privacy.detection import detect
from privacy.masking import mask
from privacy.reinsertion import reinsert

SAMPLE = (
    "My name is Rahul Sharma. My Aadhaar number is 2234-5678-9012 "
    "and my PAN is ABCDE1234F."
)

#: Simulated LLM reply — placeholders reordered and one dropped.
SIMULATED_LLM_REPLY = "Sure — <AADHAAR_1> and <PAN_1> verified for the holder."


def _run_dataset_sweep() -> int:
    dataset_path = None
    for cand in [Path("data/dataset.jsonl"), Path(__file__).resolve().parents[1] / "data" / "dataset.jsonl"]:
        if cand.is_file():
            dataset_path = cand
            break
    if not dataset_path:
        env_val = os.getenv("TIJORI_DATASET")
        if env_val and Path(env_val).is_file():
            dataset_path = Path(env_val)
        elif env_val:
            temp_p = Path(tempfile.gettempdir()) / Path(env_val).name
            if temp_p.is_file():
                dataset_path = temp_p
    if not dataset_path:
        temp_default = Path(tempfile.gettempdir()) / "tijori_dataset.jsonl"
        if temp_default.is_file():
            dataset_path = temp_default

    if not dataset_path or not dataset_path.is_file():
        print("Error: dataset file not found (checked data/dataset.jsonl and TIJORI_DATASET).", file=sys.stderr)
        return 1

    docs = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    leakages = 0
    per_type_tp: Counter[str] = Counter()
    per_type_fp: Counter[str] = Counter()
    per_type_fn: Counter[str] = Counter()
    gold_counts: Counter[str] = Counter()

    for doc in docs:
        text = doc["text"]
        det = detect(text)
        res = mask(text, det.entities)
        for ent in doc["entities"]:
            orig = ent["text"]
            if orig in res.sanitized_text:
                leakages += 1
            if ent["type"] == "AADHAAR":
                raw_digits = re.sub(r"[\s-]", "", orig)
                san_digits = re.sub(r"[\s-]", "", res.sanitized_text)
                if raw_digits in san_digits:
                    leakages += 1

        gold_spans = {(e["type"], e["start"], e["end"]) for e in doc["entities"]}
        pred_spans = {(e.type.value, e.start, e.end) for e in det.entities}
        for t, _, _ in gold_spans & pred_spans:
            per_type_tp[t] += 1
        for t, _, _ in pred_spans - gold_spans:
            per_type_fp[t] += 1
        for t, _, _ in gold_spans - pred_spans:
            per_type_fn[t] += 1
        for t, _, _ in gold_spans:
            gold_counts[t] += 1

    print(f"Dataset sweep: {len(docs)} documents processed")
    print(f"PII Leakages: {leakages}")
    print(f"{'Type':<15} {'TP':<6} {'FP':<6} {'FN':<6} {'Precision':<10} {'Recall':<10}")
    print("-" * 55)
    for t in sorted(gold_counts.keys()):
        tp = per_type_tp[t]
        fp = per_type_fp[t]
        fn = per_type_fn[t]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        print(f"{t:<15} {tp:<6} {fp:<6} {fn:<6} {p:<10.3f} {r:<10.3f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Tijori Privacy CLI")
    parser.add_argument("--dataset", action="store_true", help="Run dataset sweep summary")
    args = parser.parse_args(argv)

    if args.dataset:
        return _run_dataset_sweep()

    detection = detect(SAMPLE)
    masked = mask(SAMPLE, detection.entities)

    print("sanitized_text:", masked.sanitized_text)
    for entry in masked.mapping:
        print(f"mapping: {entry.placeholder} -> {entry.type}")

    reply = reinsert(SIMULATED_LLM_REPLY, masked.mapping)
    print("simulated_llm_reply:", SIMULATED_LLM_REPLY)
    print("final_text:", reply.text)
    print(f"reinsertion: replaced={reply.replaced} missing={reply.missing} unknown={reply.unknown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
