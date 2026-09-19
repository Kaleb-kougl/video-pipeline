#!/usr/bin/env python3
"""
Test script to validate Fandom search functionality for the TranscriptDiscoveryAgent.
"""

import logging
import os
import sys

# Add the main directory to path so we can import the agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from agents.transcript_agent import TranscriptDiscoveryAgent

# Live-network suite: these tests scrape Fandom/Google and hit real HTTP
# endpoints, so they are deselected by default (see the 'network' marker in
# pyproject.toml). Run them explicitly with: pytest -m network
pytestmark = pytest.mark.network

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_fandom_search():
    """Test the Fandom search functionality.

    Validates the TranscriptDiscoveryAgent's ability to search Fandom wikis
    for transcript content across different anime shows with varying name
    complexity and special characters.

    Returns:
        None
    """

    print("🧪 Testing Fandom Search Functionality")
    print("=" * 50)

    # Initialize the agent
    agent = TranscriptDiscoveryAgent()

    # Test cases with different anime shows
    test_cases = [
        {
            "show": "Frieren: Beyond Journey's End",
            "season": 1,
            "episode": 1,
            "description": "Complex show name with special characters",
        },
        {
            "show": "My Hero Academia",
            "season": 1,
            "episode": 1,
            "description": "Well-known anime series",
        },
        {
            "show": "Attack on Titan",
            "season": 1,
            "episode": 1,
            "description": "Popular series with potential variations",
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}: {test_case['description']}")
        print(f"   Show: {test_case['show']}")
        print(f"   Season: {test_case['season']}, Episode: {test_case['episode']}")

        try:
            # Test Fandom search specifically
            result = agent.search_using_site_search(
                "transcripts_wiki", test_case["show"], test_case["season"], test_case["episode"]
            )

            if result:
                print("   ✅ Success!")
                print(f"   📄 Title: {result['title']}")
                print(f"   🔗 URL: {result['url']}")
                print(f"   📊 Quality Score: {result['quality_score']:.2f}")
                print(f"   📏 Content Length: {result['content_length']} chars")

                # Show a preview of the transcript
                preview = (
                    result["transcript"][:200] + "..."
                    if len(result["transcript"]) > 200
                    else result["transcript"]
                )
                print(f"   📖 Preview: {preview}")

                results.append({"test_case": test_case, "success": True, "result": result})
            else:
                print("   ❌ No results found")
                results.append({"test_case": test_case, "success": False, "result": None})

        except Exception as e:
            print(f"   💥 Error: {e}")
            results.append({"test_case": test_case, "success": False, "error": str(e)})

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)

    successful = sum(1 for r in results if r["success"])
    total = len(results)

    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {total - successful}/{total}")

    if successful > 0:
        print("\n🎉 Fandom search functionality is working!")
        print(f"   Successfully found transcripts for {successful} out of {total} test cases.")
    else:
        print("\n⚠️  No successful searches found.")
        print("   This might indicate issues with:")
        print("   - Search query formatting")
        print("   - Search result parsing")
        print("   - Network connectivity")
        print("   - Source availability")

    return results


def test_search_query_generation():
    """Test the search query generation for different sources."""

    print("\n🔍 Testing Search Query Generation")
    print("=" * 50)

    agent = TranscriptDiscoveryAgent()

    test_show = "Frieren: Beyond Journey's End"

    sources_to_test = ["transcripts_wiki", "subslikescript", "anime_transcripts"]

    for source in sources_to_test:
        if source in agent.sources:
            source_config = agent.sources[source]
            print(f"\n📋 {source}:")
            print(f"   Base URL: {source_config.get('base_url', 'N/A')}")
            print(f"   Search URL: {source_config.get('search_url', 'N/A')}")
            print(f"   Supports Search: {source_config.get('supports_search', False)}")

            # Test show slug generation
            slugs = agent.get_show_slugs(test_show)
            print(f"   Generated slugs: {slugs[:3]}...")  # Show first 3 slugs
        else:
            print(f"\n❌ {source}: Source not configured")


if __name__ == "__main__":
    print("🚀 Starting Fandom Search Tests")

    # Test search query generation first
    test_search_query_generation()

    # Test actual search functionality
    test_results = test_fandom_search()

    print("\n🏁 Testing complete!")
