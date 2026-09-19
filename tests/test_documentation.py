"""
Checks that the project documentation stays usable and internally consistent.

These assertions deliberately avoid pinning exact prose. An earlier version of
this file asserted marketing headings such as "Intelligent Content Caching
System", which meant every honest documentation edit broke the build and the
cheapest fix was always to put the wording back. Instead this verifies
structural properties and, more usefully, that the docs do not promise CLI
commands the program does not implement.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
README = PROJECT_ROOT / "README.md"
DOCS = PROJECT_ROOT / "docs"


def _visible(markdown: str) -> str:
    """Markdown with HTML comments removed.

    Comments hold maintainer instructions (e.g. how to add a demo GIF) and
    may reference files that do not exist yet. They never render, so they
    are not part of what a reader sees.
    """
    return re.sub(r"<!--.*?-->", "", markdown, flags=re.S)


def _registered_commands() -> set[str]:
    """Every subcommand main.py registers with argparse."""
    source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    return set(re.findall(r"add_parser\(\s*['\"]([a-z0-9-]+)", source))


class TestReadme:
    def test_exists_and_is_not_a_wall_of_text(self):
        assert README.exists(), "README.md must exist"
        content = README.read_text(encoding="utf-8")
        assert content.startswith("# "), "README should open with a title"
        line_count = len(content.splitlines())
        assert line_count < 400, (
            f"README is {line_count} lines. It is the first thing a reader sees; "
            "move reference material into docs/ rather than growing this file."
        )

    def test_explains_how_to_run_it(self):
        content = README.read_text(encoding="utf-8")
        assert "```bash" in content, "README needs a runnable quickstart block"
        assert "pip install" in content or "uv pip install" in content
        assert "GOOGLE_API_KEY" in content, "the required credential must be named"

    def test_links_to_docs_that_exist(self):
        content = _visible(README.read_text(encoding="utf-8"))
        for target in re.findall(r"\]\((docs/[^)#]+)", content):
            assert (PROJECT_ROOT / target).exists(), f"README links to missing {target}"


class TestDocsDirectory:
    def test_architecture_doc_exists(self):
        assert (DOCS / "architecture.md").exists()

    def test_cli_reference_exists(self):
        assert (DOCS / "cli.md").exists()


class TestDocumentedCommandsAreReal:
    """The docs previously advertised six commands that were never implemented."""

    @pytest.mark.parametrize("doc", ["README.md", "docs/cli.md"])
    def test_no_invented_commands(self, doc):
        content = _visible((PROJECT_ROOT / doc).read_text(encoding="utf-8"))
        registered = _registered_commands()
        # Hyphenated backticked tokens in these docs are command names.
        mentioned = {
            token
            for token in re.findall(r"`([a-z][a-z0-9]+(?:-[a-z0-9]+)+)`", content)
            if not token.endswith((".py", ".md", ".txt", ".toml"))
        }
        invented = {m for m in mentioned if m not in registered} - {
            "anime-video-generator",
            "video-pipeline",
            "anime-generator",  # console script in [project.scripts]
            "pre-commit",
            "requirements-vector",
            "sentence-transformers",
            "google-genai",
            "opencv-python",
            "imageio-ffmpeg",
            "pytest-asyncio",
            "pytest-timeout",
            "ruff-format",
        }
        assert not invented, (
            f"{doc} documents commands main.py does not register: {sorted(invented)}"
        )

    def test_cli_reference_covers_every_command(self):
        content = (DOCS / "cli.md").read_text(encoding="utf-8")
        missing = sorted(c for c in _registered_commands() if f"`{c}`" not in content)
        assert not missing, f"docs/cli.md is missing real commands: {missing}"
