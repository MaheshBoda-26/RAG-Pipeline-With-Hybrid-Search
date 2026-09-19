.PHONY: help install test test-integration lint typecheck check api demo site clean

help:  ## show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## install runtime + dev dependencies
	python -m pip install -r requirements.txt -r requirements-dev.txt

test:  ## run the self-contained unit test suite
	python -m pytest

test-integration:  ## run security/integration tests against a live API on :8000
	RUN_INTEGRATION_TESTS=1 python -m pytest -m integration

lint:  ## ruff
	ruff check .

typecheck:  ## mypy (configured module subset)
	mypy

check: lint typecheck test  ## everything CI runs

api:  ## run the API locally on :8000
	uvicorn api:app --reload --port 8000

demo:  ## ingest the sample corpus and ask one question end to end
	python cli.py ingest ./sample_docs
	python cli.py ask "What does the hybrid retrieval pipeline combine?"

eval:  ## run the 54-question golden-set benchmark against a fresh local store
	USE_SUPABASE=false QDRANT_PATH=./qdrant_data_eval python tests/eval/run_eval.py --golden-set tests/eval/golden_set.json --output tests/eval/results.json

corpus:  ## regenerate the Aegis demo corpus from the golden set
	python scripts/build_demo_corpus.py

site:  ## run the marketing site
	cd website && npm run dev

clean:  ## remove local caches and runtime stores
	rm -rf .pytest_cache test_qdrant_data test_bm25_data bm25_data
	find . -name '__pycache__' -not -path './.venv/*' -prune -exec rm -rf {} +
