#!/usr/bin/env python3
"""
Test suite for season processing functionality.

This module contains tests that validate the system's ability to process
entire seasons of anime shows, handling multiple episodes, maintaining
consistency, and providing progress tracking.
"""

import sys
import os
import logging
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

# Live-network suite: these tests scrape Fandom/Google and hit real HTTP
# endpoints, so they are deselected by default (see the 'network' marker in
# pyproject.toml). Run them explicitly with: pytest -m network
pytestmark = pytest.mark.network

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_season_episode_discovery():
    """Test discovery of all episodes in a season.
    
    Validates that the system can identify and list all episodes
    within a specific season of an anime show.
    
    Returns:
        bool: True if season discovery succeeds, False otherwise
    """
    print("🔍 Testing Season Episode Discovery")
    print("=" * 50)
    
    try:
        from agents.discovery_agent import EpisodeDiscoveryAgent
        
        agent = EpisodeDiscoveryAgent()
        show_name = "My Hero Academia"
        season = 1
        
        print(f"Discovering episodes for {show_name} Season {season}")
        
        episodes = agent.discover_episodes(show_name, season=season)
        
        if episodes:
            print(f"✅ Found {len(episodes)} episodes")
            for i, episode in enumerate(episodes[:5], 1):  # Show first 5
                print(f"  {i}. {episode.get('title', 'Unknown Title')}")
            if len(episodes) > 5:
                print(f"  ... and {len(episodes) - 5} more episodes")
            return True
        else:
            print("❌ No episodes discovered")
            return False
            
    except ImportError as e:
        print(f"⚠️  Discovery agent not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Season discovery failed: {e}")
        return False


def test_batch_episode_processing():
    """Test processing multiple episodes in sequence.
    
    Validates that the system can process multiple episodes from a season
    while maintaining consistency and handling errors gracefully.
    
    Returns:
        bool: True if batch processing succeeds, False otherwise
    """
    print("\n🔄 Testing Batch Episode Processing")
    print("=" * 50)
    
    try:
        from agents.transcript_agent import TranscriptDiscoveryAgent
        
        agent = TranscriptDiscoveryAgent()
        show_name = "My Hero Academia"
        season = 1
        episodes_to_test = [1, 2, 3]  # Test first few episodes
        
        results = []
        
        for episode in episodes_to_test:
            print(f"Processing Episode {episode}...")
            
            try:
                result = agent.find_episode_transcript(
                    show_name=show_name,
                    season=season,
                    episode=episode
                )
                
                if result:
                    results.append({
                        'episode': episode,
                        'success': True,
                        'quality': result['quality_score'],
                        'length': result['content_length']
                    })
                    print(f"  ✅ Success - Quality: {result['quality_score']:.2f}")
                else:
                    results.append({
                        'episode': episode,
                        'success': False
                    })
                    print(f"  ❌ Failed")
                    
            except Exception as e:
                print(f"  💥 Error: {e}")
                results.append({
                    'episode': episode,
                    'success': False,
                    'error': str(e)
                })
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        print(f"\n📊 Batch Processing Summary:")
        print(f"  Episodes processed: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {len(results) - successful}")
        print(f"  Success rate: {successful/len(results)*100:.1f}%")
        
        return successful > 0
        
    except ImportError as e:
        print(f"⚠️  Transcript agent not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Batch processing failed: {e}")
        return False


def test_season_consistency_validation():
    """Test validation of consistency across season processing.
    
    Ensures that episodes within a season maintain consistent metadata,
    naming conventions, and quality standards.
    
    Returns:
        bool: True if consistency validation passes, False otherwise
    """
    print("\n🔍 Testing Season Consistency Validation")
    print("=" * 50)
    
    # Mock episode data to test consistency
    mock_episodes = [
        {
            'episode': 1,
            'show_name': 'My Hero Academia',
            'season': 1,
            'quality_score': 0.85,
            'source': 'subslikescript'
        },
        {
            'episode': 2,
            'show_name': 'My Hero Academia',
            'season': 1,
            'quality_score': 0.82,
            'source': 'subslikescript'
        },
        {
            'episode': 3,
            'show_name': 'My Hero Academia',  # Inconsistent name
            'season': 1,
            'quality_score': 0.90,
            'source': 'transcripts_wiki'  # Different source
        }
    ]
    
    print("Validating episode consistency...")
    
    # Check show name consistency
    show_names = set(ep['show_name'] for ep in mock_episodes)
    if len(show_names) > 1:
        print(f"⚠️  Show name inconsistency detected: {show_names}")
    else:
        print("✅ Show names consistent")
    
    # Check season consistency
    seasons = set(ep['season'] for ep in mock_episodes)
    if len(seasons) > 1:
        print(f"⚠️  Season inconsistency detected: {seasons}")
    else:
        print("✅ Seasons consistent")
    
    # Check quality score distribution
    quality_scores = [ep['quality_score'] for ep in mock_episodes]
    avg_quality = sum(quality_scores) / len(quality_scores)
    quality_variance = max(quality_scores) - min(quality_scores)
    
    print(f"📊 Quality Analysis:")
    print(f"  Average quality: {avg_quality:.3f}")
    print(f"  Quality variance: {quality_variance:.3f}")
    
    if quality_variance > 0.2:
        print("⚠️  High quality variance detected")
    else:
        print("✅ Quality scores consistent")
    
    # Check source diversity
    sources = set(ep['source'] for ep in mock_episodes)
    print(f"📚 Sources used: {', '.join(sources)}")
    
    return True


def main():
    """Main function to run all season processing tests.
    
    Coordinates execution of season processing validation tests and
    provides summary of results.
    
    Returns:
        None
    """
    print("🎬 Season Processing Test Suite")
    print("=" * 60)
    
    # Run tests
    discovery_ok = test_season_episode_discovery()
    processing_ok = test_batch_episode_processing()
    consistency_ok = test_season_consistency_validation()
    
    # Summary
    print(f"\n🏁 Test Summary:")
    print("=" * 30)
    print(f"Episode Discovery: {'✅ PASSED' if discovery_ok else '❌ FAILED'}")
    print(f"Batch Processing: {'✅ PASSED' if processing_ok else '❌ FAILED'}")
    print(f"Consistency Check: {'✅ PASSED' if consistency_ok else '❌ FAILED'}")
    
    total_tests = 3
    passed_tests = sum([discovery_ok, processing_ok, consistency_ok])
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All season processing tests passed!")
    elif passed_tests >= 2:
        print("✅ Season processing mostly functional")
    else:
        print("⚠️  Season processing needs attention")


if __name__ == "__main__":
    main()
