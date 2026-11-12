# ghost — pre-hackathon setup (Windows). Run in PowerShell on good Wi-Fi.
py -3 -c "import sys; assert sys.version_info >= (3,10), 'Need Python 3.10+'; print('Python OK')"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install gliner presidio-analyzer spacy fastapi "uvicorn[standard]" streamlit anthropic openai httpx pytest pytest-timeout requests
python -m spacy download en_core_web_sm
python -c "from huggingface_hub import snapshot_download; print(snapshot_download('urchade/gliner_multi_pii-v1'))"
pip freeze > requirements.lock.txt
Write-Host "DONE. Airplane-mode test: re-run python and load GLiNER + spaCy with Wi-Fi off."
