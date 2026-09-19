"""
Test suite for the Anime Video Generator modular architecture.

This package contains comprehensive tests for all agents and system components.
"""

# Test categories
AGENT_TESTS = [
    "test_transcript_agent",
    "test_transcript_source_agent",
    "test_content_agent",
    "test_video_agent",
    "test_quality_agent",
    "test_discovery_agent",
    "test_config_manager",
    "test_workflow_orchestrator",
]

INTEGRATION_TESTS = ["test_all_agents", "test_agents_fixed"]

DISCOVERY_TESTS = ["test_complete_discovery", "test_complex_shows", "test_fandom_search"]

ALL_TESTS = AGENT_TESTS + INTEGRATION_TESTS + DISCOVERY_TESTS
