"""Test documentation completeness and accuracy."""
import pytest
import os
from pathlib import Path


class TestDocumentation:
    """Test documentation requirements."""
    
    def test_readme_contains_parallel_image_section(self):
        """Test that README contains parallel image generation documentation."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.exists(), "README.md must exist"
        
        content = readme_path.read_text()
        
        # Check for parallel image generation section
        assert "Parallel Image Generation" in content
        assert "60-70%" in content
        assert "AnyIO" in content
        assert "concurrent processing" in content
        
    def test_readme_contains_usage_examples(self):
        """Test that README contains usage examples."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()
        
        # Check for usage examples
        assert "ParallelImageGenerator" in content
        assert "generate_images_parallel" in content
        
    def test_readme_performance_metrics_documented(self):
        """Test that performance metrics are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()
        
        assert "Performance Improvements" in content
        assert "image generation time" in content
        
    def test_readme_technology_stack_updated(self):
        """Test that technology stack mentions parallel processing."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()
        
        assert "Performance & Concurrency" in content
        assert "structured concurrency" in content
