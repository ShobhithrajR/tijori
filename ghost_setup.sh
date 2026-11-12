#!/usr/bin/env bash
# ============================================================
# ghost — pre-hackathon setup & offline bundle builder
# Run this ON GOOD WI-FI, BEFORE the event.
# Produces ./offline_bundle/ you can copy to the venue machine.
# ============================================================
set -euo pipefail

echo "=== [1/8] Python version check ==="
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
$PY --version
$PY -c "import sys; assert sys.version_info >= (3,10), 'Need Python 3.10+'; print('Python OK')"

echo "=== [2/8] Create venv ==="
$PY -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

echo "=== [3/8] Install torch (CPU wheel — smaller, no CUDA) ==="
pip install torch --index-url https://download.pytorch.org/whl/cpu

echo "=== [4/8] Install everything else ==="
pip install gliner presidio-analyzer spacy fastapi "uvicorn[standard]" \
            streamlit anthropic openai httpx pytest pytest-timeout requests

echo "=== [5/8] Download spaCy model ==="
python -m spacy download en_core_web_sm

echo "=== [6/8] Download GLiNER model (urchade/gliner_multi_pii-v1) ==="
python - <<'EOF'
from huggingface_hub import snapshot_download
p = snapshot_download("urchade/gliner_multi_pii-v1")
print("GLiNER model at:", p)
EOF

echo "=== [7/8] Build offline wheel bundle (for venue install without Wi-Fi) ==="
mkdir -p offline_bundle/wheels
pip download torch --index-url https://download.pytorch.org/whl/cpu -d offline_bundle/wheels
pip download gliner presidio-analyzer spacy fastapi "uvicorn[standard]" \
             streamlit anthropic openai httpx pytest pytest-timeout requests \
             -d offline_bundle/wheels
python -m spacy download en_core_web_sm --direct 2>/dev/null || true
# copy model caches into the bundle
mkdir -p offline_bundle/models/hf offline_bundle/models/spacy
cp -r ~/.cache/huggingface/hub/models--urchade--gliner_multi_pii-v1* offline_bundle/models/hf/ 2>/dev/null || echo "NOTE: HF cache not found, run step 6 again"
SPACY_DIR=$(python -c "import spacy,os;print(os.path.dirname(spacy.__file__))")
cp -r "$SPACY_DIR/data/en_core_web_sm"* offline_bundle/models/spacy/ 2>/dev/null || true
ls ~/.spacy 2>/dev/null && cp -r ~/.spacy/* offline_bundle/models/spacy/ 2>/dev/null || true

echo "=== [8/8] Write requirements lock ==="
pip freeze > offline_bundle/requirements.lock.txt

echo ""
echo "DONE. Next:"
echo "  1. Airplane-mode test:  bash offline_verify.sh"
echo "  2. Copy ./offline_bundle to the venue machine (USB or cloud)."
echo "  3. At venue, if fresh machine:  bash venue_install_from_bundle.sh"
