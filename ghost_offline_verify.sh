#!/usr/bin/env bash
# Airplane-mode smoke test. Turn Wi-Fi OFF first, then run this.
set -euo pipefail
source .venv/bin/activate

echo "--- verifying imports (must not touch network) ---"
python - <<'EOF'
import fastapi, uvicorn, streamlit, anthropic, openai, httpx, pytest, spacy, presidio_analyzer
print("core imports OK")
import torch
print("torch", torch.__version__)
from gliner import GLiNER
m = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")
ents = m.predict_entities("My name is Rahul Sharma and my Aadhaar is 2341 5678 9012.", ["person","address","phone number"])
print("GLiNER offline OK:", ents)
nlp = spacy.load("en_core_web_sm")
print("spaCy offline OK")
EOF

echo "--- project tests (once repo code exists) ---"
if [ -d tests ] || ls test_*.py tests/*.py >/dev/null 2>&1; then
  pytest -q
else
  echo "NOTE: no project tests yet (code is written at the event) — skipping."
fi

echo "OFFLINE VERIFY PASSED"
