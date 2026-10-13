PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: venv install dev test lint fmt run migrate seed-demo clean purge \
        preflight fresh-clone smoke

venv:
	python3.12 -m venv .venv

install:
	$(PIP) install -U pip
	$(PIP) install -r requirements-dev.txt

dev:
	$(PY) -m uvicorn app.main:app --reload --port 8000

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .

fmt:
	$(PY) -m ruff format .

run:
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

migrate:
	$(PY) -m alembic upgrade head

seed-demo:
	$(PY) -m app.cli seed-demo

purge:
	$(PY) -m app.cli purge

preflight: lint test

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -name __pycache__ -type d -exec rm -rf {} +

smoke:
	bash scripts/smoke_test.sh

fresh-clone:
	bash scripts/fresh_clone.sh
