#!/usr/bin/env python3
"""
Test script for the TranscriptDiscoveryAgent to demonstrate how it finds transcripts
from multiple public sources for any anime episode.
"""

import sys
import os
import logging

# Add the parent directory to the path so we can import from main.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.transcript_agent import TranscriptDiscoveryAgent

# Set up logging to see the search process
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_transcript_discovery():
    """Test the transcript discovery agent with various anime shows.
    
    Validates the TranscriptDiscoveryAgent across multiple popular anime shows
    to test robustness and success rates across different source sites and
    content types.
    
    Returns:
        None
    """
    
    print("🔍 Testing Transcript Discovery Agent")
    print("=" * 50)
    
    # Initialize the agent
    agent = TranscriptDiscoveryAgent()
    
    # Test cases for different anime shows
    test_cases = [
        # (show_name, season, episode, episode_title)
        ("My Hero Academia", 1, 4, "Start Line"),
        ("Attack on Titan", 1, 1, None),
        ("Demon Slayer", 1, 1, None),
        ("Death Note", 1, 1, None),
        ("One Piece", 1, 1, None),
    ]
    
    results = []
    
    for show_name, season, episode, episode_title in test_cases:
        print(f"\n🎯 Searching for: {show_name} Season {season} Episode {episode}")
        if episode_title:
            print(f"   Episode Title: {episode_title}")
        
        try:
            result = agent.find_episode_transcript(show_name, season, episode, episode_title)
            
            if result:
                print(f"✅ SUCCESS!")
                print(f"   📡 Source: {result['source']}")
                print(f"   🔗 URL: {result['url']}")
                print(f"   ⭐ Quality Score: {result['quality_score']:.2f}")
                print(f"   📝 Content Length: {result['content_length']} characters")
                print(f"   📖 Title: {result['title'][:100]}...")
                print(f"   📄 Preview: {result['transcript'][:200]}...")
                
                results.append({
                    'show': show_name,
                    'season': season,
                    'episode': episode,
                    'success': True,
                    'source': result['source'],
                    'quality': result['quality_score']
                })
            else:
                print(f"❌ FAILED - No transcript found")
                results.append({
                    'show': show_name,
                    'season': season,
                    'episode': episode,
                    'success': False,
                    'source': None,
                    'quality': 0
                })
                
        except Exception as e:
            print(f"💥 ERROR: {e}")
            results.append({
                'show': show_name,
                'season': season,
                'episode': episode,
                'success': False,
                'source': None,
                'quality': 0,
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY RESULTS")
    print("=" * 50)
    
    successful = sum(1 for r in results if r['success'])
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {total - successful}")
    print(f"Success Rate: {successful/total*100:.1f}%")
    
    print("\n📋 Detailed Results:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        show_info = f"{result['show']} S{result['season']}E{result['episode']}"
        if result['success']:
            print(f"{status} {show_info:<30} | Source: {result['source']:<15} | Quality: {result['quality']:.2f}")
        else:
            error_msg = result.get('error', 'No transcript found')[:40]
            print(f"{status} {show_info:<30} | Error: {error_msg}")

def test_single_episode():
    """Test finding a transcript for a single episode with detailed output.
    
    Performs an in-depth test of transcript discovery for a known episode,
    providing detailed output including content preview and extracted metadata
    to validate parsing accuracy and quality.
    
    Returns:
        None
    """
    
    print("\n🎯 SINGLE EPISODE TEST")
    print("=" * 50)
    
    agent = TranscriptDiscoveryAgent()
    
    # Test My Hero Academia Episode 4 (known to exist)
    show_name = "My Hero Academia"
    season = 1
    episode = 4
    episode_title = "Start Line"
    
    print(f"Searching for: {show_name} Season {season} Episode {episode}")
    print(f"Episode Title: {episode_title}")
    
    result = agent.find_episode_transcript(show_name, season, episode, episode_title)
    
    if result:
        print(f"\n🎉 Found transcript!")
        print(f"Source: {result['source']}")
        print(f"URL: {result['url']}")
        print(f"Quality Score: {result['quality_score']:.2f}")
        print(f"Content Length: {result['content_length']} characters")
        print(f"Title: {result['title']}")
        
        print("\n📄 Transcript Preview (first 500 characters):")
        print("-" * 50)
        print(result['transcript'][:500] + "...")
        print("-" * 50)
        
        # Show episode info if extracted
        if result['episode_info']['season'] or result['episode_info']['episode']:
            print(f"\n📺 Extracted Episode Info:")
            print(f"Season: {result['episode_info']['season']}")
            print(f"Episode: {result['episode_info']['episode']}")
    else:
        print("❌ No transcript found")

def show_supported_shows():
    """Display all supported anime shows and their slug variations.
    
    Provides a comprehensive overview of all anime shows that have predefined
    URL patterns and slug variations, helping users understand which shows
    have better success rates for transcript discovery.
    
    Returns:
        None
    """
    
    print("\n📚 SUPPORTED ANIME SHOWS")
    print("=" * 50)
    
    agent = TranscriptDiscoveryAgent()
    
    print("The agent can search for transcripts of the following anime shows:")
    print("(Shows with predefined URL patterns have better success rates)\n")
    
    for show, slugs in agent.show_mappings.items():
        print(f"🎬 {show}")
        print(f"   URL Variations: {', '.join(slugs)}")
        print()
    
    print("💡 The agent can also attempt to find transcripts for other anime shows")
    print("   by automatically generating URL patterns from the show name.")

if __name__ == "__main__":
    """Run the test based on command line arguments."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the Transcript Discovery Agent")
    parser.add_argument(
        "--mode", 
        choices=["single", "batch", "shows"], 
        default="single",
        help="Test mode: single episode, batch test, or show supported shows"
    )
    
    args = parser.parse_args()
    
    if args.mode == "single":
        test_single_episode()
    elif args.mode == "batch":
        test_transcript_discovery()
    elif args.mode == "shows":
        show_supported_shows()
    
    print("\n🎯 Want to test a specific episode?")
    print("Use the agent directly in Python:")
    print("""
from main import TranscriptDiscoveryAgent

agent = TranscriptDiscoveryAgent()
result = agent.find_episode_transcript("Your Anime Show", season=1, episode=1)

if result:
    print(f"Found transcript from {result['source']}")
    print(f"Quality: {result['quality_score']:.2f}")
    print(f"URL: {result['url']}")
else:
    print("No transcript found")
""")
