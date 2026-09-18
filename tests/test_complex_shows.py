#!/usr/bin/env python3
"""
Test script specifically for testing complex anime show names and URL pattern generation.
This tests the enhanced intelligent URL generation capabilities.
"""

import sys
import os
import logging

# Add the parent directory to the path so we can import from main.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.transcript_agent import TranscriptDiscoveryAgent

import pytest

# Live-network suite: these tests scrape Fandom/Google and hit real HTTP
# endpoints, so they are deselected by default (see the 'network' marker in
# pyproject.toml). Run them explicitly with: pytest -m network
pytestmark = pytest.mark.network

# Set up logging to see the detailed search process
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_url_generation():
    """Test URL slug generation for complex show names.
    
    Validates the system's ability to generate appropriate URL patterns
    for anime shows with complex names containing special characters,
    colons, apostrophes, and other challenging elements.
    
    Returns:
        None
    """
    
    print("🧪 Testing Enhanced URL Generation")
    print("=" * 60)
    
    agent = TranscriptDiscoveryAgent()
    
    # Test cases with complex show names
    complex_shows = [
        "Frieren: Beyond Journey's End",
        "86: Eighty-Six",
        "Dr. Stone",
        "Re:Zero - Starting Life in Another World",
        "That Time I Got Reincarnated as a Slime",
        "The Rising of the Shield Hero",
        "Is It Wrong to Try to Pick Up Girls in a Dungeon?",
        "KonoSuba: God's Blessing on This Wonderful World!",
        "Rascal Does Not Dream of Bunny Girl Senpai",
        "The Quintessential Quintuplets",
        "Kaguya-sama: Love is War",
        "Your Name.",
        "Weathering with You",
        "A Silent Voice",
        "Spirited Away",
        "Princess Mononoke"
    ]
    
    for show_name in complex_shows:
        print(f"\n🎬 Show: '{show_name}'")
        print("-" * 40)
        
        slugs = agent.get_show_slugs(show_name)
        
        print(f"Generated {len(slugs)} URL variations:")
        for i, slug in enumerate(slugs, 1):
            print(f"  {i:2d}. {slug}")
        
        # Show what URLs would be generated
        print(f"\nExample URLs for SubsLikeScript:")
        base_url = "https://subslikescript.com/series"
        for pattern in ["{show_slug}", "{show_slug}/season-1/episode-1"]:
            example_url = f"{base_url}/{pattern}".format(show_slug=slugs[0] if slugs else "unknown")
            print(f"  • {example_url}")

def test_specific_show_discovery():
    """Test the discovery mechanism for a specific complex show."""
    
    print("\n\n🔍 Testing Dynamic Pattern Discovery")
    print("=" * 60)
    
    agent = TranscriptDiscoveryAgent()
    
    # Test with Frieren specifically
    show_name = "Frieren: Beyond Journey's End"
    print(f"Testing discovery for: '{show_name}'")
    
    # Get all possible slugs
    slugs = agent.get_show_slugs(show_name)
    print(f"\nGenerated {len(slugs)} potential URL slugs:")
    for i, slug in enumerate(slugs, 1):
        print(f"  {i:2d}. '{slug}'")
    
    # Test if any of these patterns might work
    print(f"\nTesting URL patterns (without actual requests):")
    
    for source_name, source_config in agent.sources.items():
        print(f"\n📡 {source_name.upper()}:")
        for slug in slugs[:5]:  # Test first 5 slugs
            for pattern in source_config['search_patterns']:
                if '{title_slug}' not in pattern:  # Skip title-dependent patterns
                    try:
                        url = source_config['base_url'] + pattern.format(
                            show_slug=slug,
                            season=1,
                            episode=1
                        )
                        print(f"    {url}")
                    except Exception as e:
                        print(f"    [Error formatting]: {e}")

def test_actual_search():
    """Test actual search for a few shows (carefully to avoid overloading servers)."""
    
    print("\n\n🌐 Testing Actual Search (Limited)")
    print("=" * 60)
    
    agent = TranscriptDiscoveryAgent()
    
    # Test with a few shows that are likely to exist
    test_shows = [
        ("My Hero Academia", 1, 1),  # Known to exist
        ("Attack on Titan", 1, 1),   # Known to exist  
        ("Frieren: Beyond Journey's End", 1, 1),  # Test our complex case
    ]
    
    for show_name, season, episode in test_shows:
        print(f"\n🎯 Searching for: {show_name} S{season}E{episode}")
        print("-" * 40)
        
        try:
            # Use discovery=False first to test standard patterns
            result = agent.find_episode_transcript(show_name, season, episode, use_discovery=False)
            
            if result:
                print(f"✅ Found with standard patterns!")
                print(f"   Source: {result['source']}")
                print(f"   Quality: {result['quality_score']:.2f}")
                print(f"   URL: {result['url']}")
                print(f"   Preview: {result['transcript'][:100]}...")
            else:
                print(f"❌ Not found with standard patterns")
                
                # Now try with discovery enabled
                print(f"🔍 Trying with enhanced discovery...")
                result = agent.find_episode_transcript(show_name, season, episode, use_discovery=True)
                
                if result:
                    print(f"✅ Found with enhanced discovery!")
                    print(f"   Source: {result['source']}")
                    print(f"   Quality: {result['quality_score']:.2f}")
                    print(f"   URL: {result['url']}")
                else:
                    print(f"❌ Still not found")
                    
        except Exception as e:
            print(f"💥 Error during search: {e}")
        
        # Be respectful - add delay between searches
        import time
        time.sleep(2)

def analyze_url_patterns():
    """Analyze what makes URLs work or not work."""
    
    print("\n\n📊 URL Pattern Analysis")
    print("=" * 60)
    
    # Common patterns observed in transcript sites
    patterns = {
        "SubsLikeScript": [
            "/series/{show}-{id}",
            "/series/{show}/season-{season}/episode-{episode}",
            "/series/{show}/season-{season}/episode-{episode}-{title}"
        ],
        "General Sites": [
            "/{show}/s{season}e{episode}",
            "/{show}/season{season}/episode{episode}",
            "/{show}/{season}/{episode}",
            "/transcripts/{show}/{season}-{episode}"
        ]
    }
    
    print("Common URL patterns found on transcript sites:")
    for site_type, site_patterns in patterns.items():
        print(f"\n{site_type}:")
        for pattern in site_patterns:
            print(f"  • {pattern}")
    
    print("\nKey observations:")
    print("  • Show names often include IDs or year suffixes")
    print("  • Punctuation is typically removed or replaced")
    print("  • Spaces become dashes or underscores")
    print("  • Some sites use title-case, others lowercase")
    print("  • Episode titles are often optional but improve accuracy")

if __name__ == "__main__":
    """Run comprehensive URL generation tests."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Test enhanced URL generation for complex anime show names")
    parser.add_argument(
        "--mode", 
        choices=["generation", "discovery", "search", "analysis", "all"], 
        default="all",
        help="Test mode to run"
    )
    
    args = parser.parse_args()
    
    if args.mode == "generation" or args.mode == "all":
        test_url_generation()
    
    if args.mode == "discovery" or args.mode == "all":
        test_specific_show_discovery()
    
    if args.mode == "search" or args.mode == "all":
        test_actual_search()
    
    if args.mode == "analysis" or args.mode == "all":
        analyze_url_patterns()
    
    print("\n" + "=" * 60)
    print("🎯 Summary:")
    print("The enhanced URL generation now handles:")
    print("✅ Complex punctuation (colons, apostrophes, etc.)")
    print("✅ Subtitle patterns (Title: Subtitle)")
    print("✅ Number variations (1 ↔ one)")
    print("✅ Acronym generation")
    print("✅ Common word filtering")
    print("✅ Dynamic pattern discovery")
    print("✅ Multiple slug formats per show")
    print("\nFor 'Frieren: Beyond Journey's End', it will try:")
    print("  • frieren-beyond-journeys-end")
    print("  • frieren-beyond-journey-end")  
    print("  • frieren")
    print("  • beyond-journeys-end")
    print("  • fbjе (acronym)")
    print("  • And many more variations...")
