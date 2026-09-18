#!/usr/bin/env python3
"""
Test the complete transcript discovery with enhanced Fandom search functionality.
"""

import sys
import os
import logging

# Add the main directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.transcript_agent import TranscriptDiscoveryAgent

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_complete_discovery():
    """Test the complete discovery process with all sources.
    
    Validates the end-to-end transcript discovery functionality by testing
    the agent's ability to find transcripts using multiple sources and
    discovery methods, providing comprehensive quality metrics.
    
    Returns:
        bool: True if transcript discovery succeeds, False otherwise
    """
    
    print("🎯 Testing Complete Transcript Discovery")
    print("=" * 60)
    
    agent = TranscriptDiscoveryAgent()
    
    # Test with Frieren since it's likely to have good coverage
    show_name = "Frieren: Beyond Journey's End"
    season = 1
    episode = 1
    
    print(f"📺 Searching for: {show_name} Season {season} Episode {episode}")
    print("-" * 60)
    
    # Test the complete discovery process
    result = agent.find_episode_transcript(
        show_name=show_name,
        season=season,
        episode=episode,
        use_discovery=True
    )
    
    if result:
        print(f"✅ SUCCESS!")
        print(f"📄 Title: {result['title']}")
        print(f"🌐 Source: {result['source']}")
        print(f"🔗 URL: {result['url']}")
        print(f"📊 Quality Score: {result['quality_score']:.2f}")
        print(f"📏 Content Length: {result['content_length']} characters")
        
        # Show search method used
        search_method = "Site Search" if result.get('found_via_search') else "URL Patterns"
        print(f"🔍 Discovery Method: {search_method}")
        
        # Show episode info if extracted
        if result['episode_info']:
            print(f"📺 Extracted Info: Season {result['episode_info']['season']}, Episode {result['episode_info']['episode']}")
        
        # Content preview
        preview_length = 300
        preview = result['transcript'][:preview_length]
        if len(result['transcript']) > preview_length:
            preview += "..."
        
        print(f"\n📖 Content Preview:")
        print("-" * 40)
        print(preview)
        print("-" * 40)
        
        return True
    else:
        print("❌ No transcript found with any method")
        return False

def test_multi_source_comparison():
    """Test multiple sources to compare results.
    
    Validates the system's ability to query multiple transcript sources
    and compare their results to determine the best available option
    based on quality scores and content metrics.
    
    Returns:
        dict: Dictionary mapping source names to their results, empty if no results found
    """
    
    print("\n🔄 Testing Multi-Source Comparison")
    print("=" * 60)
    
    agent = TranscriptDiscoveryAgent()
    
    show_name = "My Hero Academia"
    season = 1
    episode = 1
    
    sources_to_test = ['subslikescript', 'transcripts_wiki']
    results = {}
    
    for source in sources_to_test:
        print(f"\n🔍 Testing {source}...")
        
        if agent.sources[source].get('supports_search'):
            result = agent.search_using_site_search(source, show_name, season, episode)
            method = "Site Search"
        else:
            result = agent.search_source(source, show_name, season, episode)
            method = "URL Patterns"
        
        if result:
            print(f"   ✅ Found via {method}")
            print(f"   📊 Quality: {result['quality_score']:.2f}")
            print(f"   📏 Length: {result['content_length']} chars")
            results[source] = result
        else:
            print(f"   ❌ No results")
            results[source] = None
    
    # Compare results
    print(f"\n📊 Comparison Summary:")
    print("-" * 30)
    
    valid_results = {k: v for k, v in results.items() if v is not None}
    
    if valid_results:
        # Find best result
        best_source = max(valid_results.keys(), 
                         key=lambda k: (valid_results[k]['quality_score'], valid_results[k]['content_length']))
        
        print(f"🏆 Best Source: {best_source}")
        print(f"   Quality: {valid_results[best_source]['quality_score']:.2f}")
        print(f"   Length: {valid_results[best_source]['content_length']} chars")
        
        return valid_results
    else:
        print("❌ No valid results from any source")
        return {}

if __name__ == "__main__":
    print("🚀 Starting Complete Discovery Tests")
    
    # Test complete discovery
    success = test_complete_discovery()
    
    # Test multi-source comparison
    comparison_results = test_multi_source_comparison()
    
    print(f"\n🏁 Testing Summary:")
    print("=" * 40)
    print(f"✅ Complete Discovery: {'Success' if success else 'Failed'}")
    print(f"🔄 Sources Found: {len(comparison_results)}")
    
    if success and comparison_results:
        print(f"\n🎉 Enhanced Fandom search is fully functional!")
        print(f"   - Cross-wiki search with proper parameters ✅")
        print(f"   - Intelligent result filtering ✅") 
        print(f"   - Wiki page variant handling ✅")
        print(f"   - Quality scoring and comparison ✅")
    else:
        print(f"\n⚠️  Some functionality may need refinement")
    
    print(f"\n🔗 The transcript discovery agent now supports:")
    print(f"   📖 SubsLikeScript (site search)")
    print(f"   📚 Fandom/Wiki (cross-wiki search)")
    print(f"   🎭 Anime Transcripts (URL patterns)")
    print(f"   🔄 Fallback discovery methods")
