PYTHON ?= python3
VENV   ?= .venv
BIN    := $(VENV)/bin

.PHONY: help demo install install-demo test lint format typecheck docker-demo clean-demo

.DEFAULT_GOAL := help

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# The one command a reviewer runs.
# ---------------------------------------------------------------------------

demo: $(BIN)/python  ## Render a real MP4 offline - no API key, no network
	$(BIN)/python scripts/demo.py

# Bootstrap rule: if there is no venv yet, build one from the *slim* demo
# dependency set rather than the full ~1.1 GB production install. Nothing here
# fires when $(VENV)/bin/python already exists (including the /opt/venv the
# Docker image passes in via VENV=/opt/venv).
$(BIN)/python:
	@$(PYTHON) -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,12) else 1)' \
		|| { echo "ERROR: $(PYTHON) is `$(PYTHON) -V 2>&1`, but the pinned wheels" \
		     "(pydantic-core, numpy, opencv) only publish builds for Python 3.11-3.12."; \
		     echo "       Point make at one, e.g.:  make demo PYTHON=python3.12"; \
		     echo "       Or skip the toolchain entirely:  make docker-demo"; exit 1; }
	@echo "No interpreter at $(BIN)/python - creating a venv with the slim demo deps."
	@echo "(For the full pipeline instead, run: make install)"
	@# --clear: this target only runs when $(BIN)/python is missing, which means
	@# the venv is absent OR broken. A stale venv (e.g. built on another machine)
	@# leaves python/python3 as dangling symlinks that plain `venv` will not
	@# repoint, so the bootstrap would 'succeed' and still have no interpreter.
	$(PYTHON) -m venv --clear $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-demo.txt

clean-demo:  ## Delete everything the demo wrote
	rm -rf demo_output

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

install:  ## Create the venv, install the FULL deps and the pre-commit hooks
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	$(BIN)/pip install ruff==0.16.8 mypy==2.3.1 pre-commit
	$(BIN)/pre-commit install

install-demo:  ## Create the venv with only the deps the demo needs (~0.3 GB)
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-demo.txt

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

# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------

docker-demo:  ## Build the demo image and run it, copying the MP4 to demo_output/
	docker build -t anime-video-generator:demo .
	docker run --rm --network none -v "$(CURDIR)/demo_output:/out" anime-video-generator:demo
