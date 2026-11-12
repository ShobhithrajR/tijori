"""Evaluation harness (lane 3).

Spine state: placeholder. Lane 3 implements:
  - per-entity precision / recall against data/dataset.jsonl
  - zero-leakage scan of outbound payloads
  - reinsertion accuracy
  - latency p50/p95
  and writes reports/metrics.md.
"""

from __future__ import annotations


def main() -> int:
    print("Evaluation harness not implemented yet (lane 3).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
