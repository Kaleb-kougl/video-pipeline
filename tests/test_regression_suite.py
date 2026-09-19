#!/usr/bin/env python3
"""
The regression-suite manifest, and tests that keep it honest.

This module used to contain a `test_regression_suite` that shelled out to each
module below and *returned* a bool. pytest collects a function named `test_*`,
so a returned `False` still reported as a pass (with a
`PytestReturnNotNoneWarning`) - the test could not fail. It also re-ran four
suites in subprocesses that the same `pytest` invocation was already running
directly, for about five minutes of duplicated work.

The reporting harness now lives in `scripts/run_regression_suite.py`, which is
where a runner that prints a summary and exits non-zero belongs. What stays here
is the manifest itself - the single source of truth both the harness and these
tests read - plus real assertions about it.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent

#: Modules whose job is to prove a previously fixed bug is still fixed.
#: `scripts/run_regression_suite.py` imports this list; do not duplicate it.
REGRESSION_TESTS = [
    {
        "name": "ChromaDB Array Boolean Fixes",
        "description": "Validates fixes for 'truth value of array is ambiguous' errors in ChromaDB result handling",
        "file": "tests/test_chromadb_array_fixes.py",
        "critical": True,
    },
    {
        "name": "Google AI Client Fixes",
        "description": "Validates fixes for Google Generative AI client initialization and API usage",
        "file": "tests/test_google_ai_client_fixes.py",
        "critical": True,
    },
    {
        "name": "File Path Consistency",
        "description": "Validates that file paths are consistent between image generation and video creation",
        "file": "tests/test_file_path_consistency.py",
        "critical": False,
    },
    {
        "name": "Character Season Analysis",
        "description": "Validates that character analysis season episode retrieval works without errors",
        "file": "tests/test_character_season_analysis.py",
        "critical": True,
    },
]


def _manifest_ids() -> list[str]:
    return [entry["name"] for entry in REGRESSION_TESTS]


def test_manifest_is_not_empty():
    """An empty manifest would make every other check here vacuously true."""
    assert REGRESSION_TESTS, "the regression manifest has been emptied"
    assert any(entry["critical"] for entry in REGRESSION_TESTS), (
        "no entry is marked critical, so the runner can never fail"
    )


@pytest.mark.parametrize("entry", REGRESSION_TESTS, ids=_manifest_ids())
def test_manifest_entry_has_the_fields_the_runner_reads(entry):
    """A missing key would crash the runner rather than report a failure."""
    assert set(entry) == {"name", "description", "file", "critical"}
    assert isinstance(entry["critical"], bool)
    assert entry["name"] and entry["description"]


@pytest.mark.parametrize("entry", REGRESSION_TESTS, ids=_manifest_ids())
def test_manifest_entry_points_at_a_real_test_module(entry):
    """
    A renamed or deleted module must fail loudly.

    The old harness printed "⚠️ Test file not found", recorded the entry as
    "missing" and carried on; because `missing` is not `passed` it could drag
    the critical success rate down, but the returned bool never failed anything.
    """
    path = PROJECT_ROOT / entry["file"]
    assert path.is_file(), f"{entry['name']}: {entry['file']} does not exist"


@pytest.mark.parametrize("entry", REGRESSION_TESTS, ids=_manifest_ids())
def test_manifest_entry_is_collected_by_a_plain_pytest_run(entry):
    """
    Each regression module is run directly by `pytest`, not only by the script.

    That is what makes the script a convenience rather than the only thing
    standing between a regression and a green build.
    """
    path = PROJECT_ROOT / entry["file"]
    assert path.parent.name == "tests", f"{entry['file']} is outside the collected testpath"
    assert path.name.startswith("test_"), f"{entry['file']} would not be collected by pytest"
    assert "pytest.mark.network" not in path.read_text(), (
        f"{entry['file']} is network-marked, so a default pytest run deselects it"
    )


def test_manifest_entries_are_unique():
    """Duplicate entries would double-run a module and skew the success rate."""
    files = [entry["file"] for entry in REGRESSION_TESTS]
    names = [entry["name"] for entry in REGRESSION_TESTS]
    assert len(set(files)) == len(files), "a module appears twice in the manifest"
    assert len(set(names)) == len(names), "a name appears twice in the manifest"


def test_the_runner_reads_this_manifest():
    """The harness must not keep a second, drifting copy of the list."""
    runner = PROJECT_ROOT / "scripts" / "run_regression_suite.py"
    assert runner.is_file(), "the regression runner script is missing"
    source = runner.read_text()
    assert "from tests.test_regression_suite import REGRESSION_TESTS" in source
    assert '"file": "tests/' not in source, "the runner has its own copy of the manifest"


def test_no_test_in_this_module_returns_a_value():
    """
    The bug this module is named after: a test that returns instead of asserting.

    pytest treats the return value as nothing at all, so `return False` passes.
    """
    tree = ast.parse(Path(__file__).read_text())
    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("test_")
        and any(
            isinstance(inner, ast.Return) and inner.value is not None for inner in ast.walk(node)
        )
    ]
    assert not offenders, f"test functions must assert, not return: {offenders}"
