"""CLI proof for the lane 1 privacy core (PS-02 sample round-trip).

    python -m privacy
"""

from __future__ import annotations

from privacy.detection import detect
from privacy.masking import mask
from privacy.reinsertion import reinsert

SAMPLE = (
    "My name is Rahul Sharma. My Aadhaar number is 2234-5678-9012 "
    "and my PAN is ABCDE1234F."
)

#: Simulated LLM reply — placeholders reordered and one dropped.
SIMULATED_LLM_REPLY = "Sure — <AADHAAR_1> and <PAN_1> verified for the holder."


def main() -> int:
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
