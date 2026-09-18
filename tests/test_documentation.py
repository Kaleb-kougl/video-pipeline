"""Test documentation completeness and accuracy."""
import pytest
import os
from pathlib import Path


class TestDocumentation:
    """Test documentation requirements."""

    def test_readme_exists_and_describes_project(self):
        """Test that README exists and states what the project is."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.exists(), "README.md must exist"

        content = readme_path.read_text()

        assert "# Anime Video Generator" in content
        assert "Repository Overview" in content

    def test_readme_contains_usage_examples(self):
        """Test that README contains runnable usage examples."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        # Check for usage examples
        assert "Quick Start" in content
        assert "```bash" in content
        assert "```python" in content

    def test_readme_documents_content_caching(self):
        """Test that the content caching system is documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        assert "Intelligent Content Caching System" in content
        assert "create_content_cache" in content

    def test_readme_documents_cli_parameters(self):
        """Test that the CLI parameter reference is documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        assert "CLI Parameter Reference" in content
        assert "--format" in content
