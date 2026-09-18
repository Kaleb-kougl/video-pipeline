#!/usr/bin/env python3
"""
CLI integration tests for video length configuration.
"""

import subprocess
import pytest

class TestCLIVideoLength:
    """Test suite for CLI video length configuration functionality.
    
    This class validates that the command-line interface properly handles
    video duration parameters, validates input ranges, and provides
    appropriate help documentation.
    """
    
    def test_cli_help_shows_duration_parameter(self):
        """Test that CLI help shows the --duration parameter.
        
        Validates that the CLI help output includes the --duration parameter
        with appropriate description and range information.
        """
        result = subprocess.run([
            'python3', 'main_refactored.py', 'create-season-summary', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "--duration" in result.stdout
        assert "Video duration in minutes (5-15)" in result.stdout
    
    def test_cli_validates_duration_range(self):
        """Test that CLI validates duration is within 5-15 minute range.
        
        Validates that the CLI properly rejects duration values outside
        the acceptable range and provides meaningful error messages.
        """
        # Test too short
        result = subprocess.run([
            'python3', 'main_refactored.py', 'create-season-summary',
            'Test Show', '1', '--duration', '3'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        assert "Duration must be between 5 and 15 minutes" in result.stderr
