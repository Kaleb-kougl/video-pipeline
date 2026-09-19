#!/usr/bin/env python3
"""
Test script for the Transcript Source Discovery Agent.
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

from agents.transcript_source_agent import TranscriptSourceDiscoveryAgent

# Live-network suite: these tests scrape Fandom/Google and hit real HTTP
# endpoints, so they are deselected by default (see the 'network' marker in
# pyproject.toml). Run them explicitly with: pytest -m network
pytestmark = pytest.mark.network


def test_source_discovery():
    """Test the transcript source discovery functionality.

    Validates that the TranscriptSourceDiscoveryAgent can discover transcript
    sources for a given show and season, providing detailed metadata about
    each source's reliability, quality, and accessibility.

    Returns:
        None
    """
    print("Testing Transcript Source Discovery Agent...")
    print("=" * 50)

    # Initialize the agent
    source_agent = TranscriptSourceDiscoveryAgent()

    # Test show
    show_name = "My Hero Academia"
    season = 1

    print(f"Discovering transcript sources for: {show_name}")
    if season:
        print(f"Season: {season}")
    print()

    try:
        # Discover sources
        sources = source_agent.discover_sources_for_show(show_name, season)

        if sources:
            print(f"Found {len(sources)} potential transcript sources:")
            print("-" * 40)

            for i, source in enumerate(sources, 1):
                print(f"{i}. {source.url}")
                print(f"   Type: {source.source_type}")
                print(f"   Reliability Score: {source.reliability_score:.2f}")
                print(f"   Content Quality: {source.content_quality}")
                print(f"   Episode Coverage: {source.episode_coverage}")
                print(f"   Accessibility: {source.accessibility}")
                print(f"   Format: {source.format_type}")
                print(f"   Language: {source.language}")
                print()

            # Get recommendations
            print("Source Recommendations:")
            print("-" * 40)
            recommendations = source_agent.get_source_recommendations(sources)

            print(f"Summary: {recommendations['summary']}")
            print()

            if recommendations["recommended"]:
                print("✅ Recommended Sources:")
                for source in recommendations["recommended"]:
                    print(f"  • {source.url} (Score: {source.reliability_score:.2f})")
                print()

            if recommendations["backup"]:
                print("⚠️  Backup Sources:")
                for source in recommendations["backup"]:
                    print(f"  • {source.url} (Score: {source.reliability_score:.2f})")
                print()

            if recommendations["avoid"]:
                print("❌ Sources to Avoid:")
                for source in recommendations["avoid"]:
                    print(f"  • {source.url} (Score: {source.reliability_score:.2f})")
                print()

            if recommendations["best_source"]:
                best = recommendations["best_source"]
                print(f"🏆 Best Source: {best.url}")
                print(f"   Score: {best.reliability_score:.2f}")
                print(f"   Type: {best.source_type}")
                print()

            # Test detailed evaluation of the best source
            if sources:
                print("Detailed Evaluation of First Source:")
                print("-" * 40)
                first_source = sources[0]
                evaluation = source_agent.evaluate_source_quality(first_source)

                if evaluation.get("accessible", False):
                    print(f"Overall Score: {evaluation['overall_score']:.2f}")
                    print(f"Accessibility: {evaluation['accessibility']}")
                    print(f"Update Frequency: {evaluation['update_frequency']}")

                    content_analysis = evaluation.get("content_analysis", {})
                    if content_analysis:
                        print("\nContent Analysis:")
                        print(f"  Word Count: {content_analysis.get('word_count', 0)}")
                        print(
                            f"  Character Dialogue: {content_analysis.get('character_dialogue_count', 0)}"
                        )
                        print(
                            f"  Scene Descriptions: {content_analysis.get('scene_description_count', 0)}"
                        )
                        print(
                            f"  Structure Quality: {content_analysis.get('structure_quality', 'unknown')}"
                        )
                        print(f"  Has Timestamps: {content_analysis.get('has_timestamps', False)}")
                        print(
                            f"  Content Density: {content_analysis.get('content_density', 0):.2f}"
                        )

                    community_validation = evaluation.get("community_validation", {})
                    if community_validation:
                        print("\nCommunity Validation:")
                        print(
                            f"  Has Community: {community_validation.get('has_community', False)}"
                        )
                        print(f"  Type: {community_validation.get('type', 'unknown')}")
                        print(
                            f"  Validation Level: {community_validation.get('validation_level', 'unknown')}"
                        )

                    technical_quality = evaluation.get("technical_quality", {})
                    if technical_quality:
                        print("\nTechnical Quality:")
                        print(f"  Load Time: {technical_quality.get('load_time', 0):.2f}s")
                        print(
                            f"  Content Length: {technical_quality.get('content_length', 0)} bytes"
                        )
                        print(f"  Has SSL: {technical_quality.get('has_ssl', False)}")
                        print(
                            f"  Mobile Friendly: {technical_quality.get('mobile_friendly', False)}"
                        )
                else:
                    error = evaluation.get("error", "Unknown error")
                    print(f"❌ Evaluation failed: {error}")
        else:
            print("❌ No transcript sources found.")
            print("This could mean:")
            print("  - The show name might need different formatting")
            print("  - Sources might be behind authentication")
            print("  - Network connectivity issues")
            print("  - Rate limiting by source websites")

    except Exception as e:
        print(f"❌ Error during source discovery: {e}")
        import traceback

        print("\nFull traceback:")
        traceback.print_exc()


def test_known_patterns():
    """Test the known source patterns functionality."""
    print("\n" + "=" * 50)
    print("Testing Known Source Patterns...")
    print("=" * 50)

    source_agent = TranscriptSourceDiscoveryAgent()

    print("Known source patterns:")
    print("\nFandom Wikis:")
    for pattern in source_agent.known_source_patterns["fandom_wikis"]:
        print(f"  • {pattern}")

    print("\nTranscript Databases:")
    for pattern in source_agent.known_source_patterns["transcript_databases"]:
        print(f"  • {pattern}")

    print("\nCommunity Sites:")
    for pattern in source_agent.known_source_patterns["community_sites"]:
        print(f"  • {pattern}")

    print("\nStreaming Platforms:")
    for pattern in source_agent.known_source_patterns["streaming_platforms"]:
        print(f"  • {pattern}")

    print("\nReliability Indicators:")
    print("High Trust:")
    for domain in source_agent.reliability_indicators["high_trust"]:
        print(f"  • {domain}")

    print("Medium Trust:")
    for domain in source_agent.reliability_indicators["medium_trust"]:
        print(f"  • {domain}")

    print("Verify Needed:")
    for domain in source_agent.reliability_indicators["verify_needed"]:
        print(f"  • {domain}")


if __name__ == "__main__":
    print("Transcript Source Discovery Agent Test")
    print("=" * 50)

    # Test basic functionality
    test_source_discovery()

    # Test known patterns
    test_known_patterns()

    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nTo use the agent in the main application:")
    print("python main.py discover-sources 'My Hero Academia' --season 1")
    print("python main.py recommend-sources 'My Hero Academia'")
    print("python main.py evaluate-source 'https://example.com' 'My Hero Academia'")
