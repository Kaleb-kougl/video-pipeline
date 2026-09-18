PYTHON ?= python3
VENV   ?= .venv
BIN    := $(VENV)/bin

.PHONY: install test lint format typecheck

install:  ## Create the venv, install deps and the pre-commit hooks
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	$(BIN)/pip install ruff==0.16.8 mypy==2.3.1 pre-commit
	$(BIN)/pre-commit install

test:  ## Run the test suite (network suites are excluded via pyproject addopts)
	$(BIN)/python -m pytest

lint:  ## Check style and imports without changing anything
	$(BIN)/python -m ruff check .
	$(BIN)/python -m ruff format --check .

format:  ## Apply autofixes and reformat
	$(BIN)/python -m ruff check --fix .
	$(BIN)/python -m ruff format .

typecheck:  ## Type check the strictly-typed packages (core.* only, for now)
	$(BIN)/python -m mypy --no-incremental core
