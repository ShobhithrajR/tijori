.PHONY: test api ui eval demo

test:
	.venv/bin/pytest

api:
	.venv/bin/uvicorn app.main:app --reload --port 8000

ui:
	.venv/bin/streamlit run ui/app.py

eval:
	.venv/bin/python -m evaluation.run

demo: test
	@echo "Run 'make api' and 'make ui' in two terminals."
