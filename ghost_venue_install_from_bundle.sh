#!/usr/bin/env bash
# Venue machine: install everything from the offline bundle (no Wi-Fi needed).
# Usage:  bash venue_install_from_bundle.sh /path/to/offline_bundle
set -euo pipefail
BUNDLE="${1:?usage: venue_install_from_bundle.sh <bundle_dir>}"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
$PY -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links "$BUNDLE/wheels" -r "$BUNDLE/requirements.lock.txt"

echo "--- restoring models from bundle ---"
mkdir -p ~/.cache/huggingface/hub
cp -r "$BUNDLE/models/hf/"* ~/.cache/huggingface/hub/ 2>/dev/null || true
cp -r "$BUNDLE/models/spacy/"* ~/.spacy/ 2>/dev/null || true

echo "--- offline sanity ---"
python - <<'EOF'
from gliner import GLiNER
GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")
import spacy; spacy.load("en_core_web_sm")
print("venue offline install OK")
EOF
