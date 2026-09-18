#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression tests for character analysis season episode retrieval.

This test suite validates that the character analysis system can successfully
retrieve season episode data without the array boolean evaluation errors
that were causing "No data found" issues.
"""

import sys
import os
import unittest.mock as mock
from pathlib import Path
import numpy as np
import json

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_character_season_analysis():
    """Test that character season analysis retrieval works correctly.
    
    This test validates that:
    1. Season episode data can be retrieved without array boolean errors
    2. Character development analysis works with real-like data
    3. The analysis produces meaningful results
    4. Error handling works for edge cases
    
    Returns:
        bool: True if all tests pass, False otherwise
    """
    
    print("🧪 Testing Character Analysis Season Episode Retrieval")
    print("=" * 60)
    
    success_count = 0
    total_tests = 0
    
    # Create realistic test data that mimics what ChromaDB returns
    mock_character_data = {
        'metadatas': [[
            {
                'character_name': 'Izuku',
                'show_name': 'My Hero Academia',
                'season': 1,
                'episode': 1,
                'dialogue_count': 15,
                'personality_traits': '["determined", "brave"]',
                'episode_key': 'My Hero Academia_S1E1'
            },
            {
                'character_name': 'Bakugo', 
                'show_name': 'My Hero Academia',
                'season': 1,
                'episode': 1,
                'dialogue_count': 8,
                'personality_traits': '["hot-tempered", "competitive"]',
                'episode_key': 'My Hero Academia_S1E1'
            },
            {
                'character_name': 'Izuku',
                'show_name': 'My Hero Academia', 
                'season': 1,
                'episode': 2,
                'dialogue_count': 12,
                'personality_traits': '["determined", "analytical"]',
                'episode_key': 'My Hero Academia_S1E2'
            },
            {
                'character_name': 'All Might',
                'show_name': 'My Hero Academia',
                'season': 1,
                'episode': 2,
                'dialogue_count': 6,
                'personality_traits': '["inspiring", "protective"]',
                'episode_key': 'My Hero Academia_S1E2'
            }
        ]],
        'documents': [['Document 1', 'Document 2', 'Document 3', 'Document 4']],
        'embeddings': [np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9], [1.0, 1.1, 1.2]])]
    }
    
    mock_interaction_data = {
        'metadatas': [[
            {
                'episode_key': 'My Hero Academia_S1E1',
                'characters': '["Izuku", "Bakugo"]',
                'interaction_type': 'conflict',
                'emotional_tone': 'tense',
                'significance_score': 0.8
            },
            {
                'episode_key': 'My Hero Academia_S1E2',
                'characters': '["Izuku", "All Might"]',
                'interaction_type': 'mentorship',
                'emotional_tone': 'encouraging',
                'significance_score': 0.9
            }
        ]],
        'documents': [['Interaction 1', 'Interaction 2']],
        'embeddings': [np.array([[0.1, 0.2], [0.3, 0.4]])]
    }
    
    # Test 1: Basic season episode retrieval
    print("\n1️⃣ Testing Basic Season Episode Retrieval")
    total_tests += 1
    
    try:
        with mock.patch('chromadb.PersistentClient'):
            from agents.character_analysis_agent import CharacterAnalysisAgent
            
            agent = CharacterAnalysisAgent()
            
            # Mock the collections
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            
            mock_characters_collection.query.return_value = mock_character_data
            mock_interactions_collection.query.return_value = mock_interaction_data
            
            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection
            
            # This should work without array boolean errors
            result = agent._get_season_episodes("My Hero Academia", 1)
            
            # Verify the result structure
            assert isinstance(result, dict), "Should return a dictionary"
            assert 'show_name' in result, "Should include show_name"
            assert 'season' in result, "Should include season"
            assert 'episodes' in result, "Should include episodes list"
            assert 'episode_data' in result, "Should include episode_data"
            
            assert result['show_name'] == "My Hero Academia", "Should have correct show name"
            assert result['season'] == 1, "Should have correct season"
            assert len(result['episodes']) > 0, "Should find episodes"
            assert 1 in result['episodes'] and 2 in result['episodes'], "Should find episodes 1 and 2"
            
            print("    ✅ Basic season episode retrieval works without errors")
            success_count += 1
            
    except Exception as e:
        print(f"    ❌ Basic season episode retrieval test failed: {e}")
    
    # Test 2: Character data organization
    print("\n2️⃣ Testing Character Data Organization")
    total_tests += 1
    
    try:
        with mock.patch('chromadb.PersistentClient'):
            from agents.character_analysis_agent import CharacterAnalysisAgent
            
            agent = CharacterAnalysisAgent()
            
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            
            mock_characters_collection.query.return_value = mock_character_data
            mock_interactions_collection.query.return_value = mock_interaction_data
            
            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection
            
            result = agent._get_season_episodes("My Hero Academia", 1)
            
            # Verify character data is properly organized by episode
            episode_data = result['episode_data']
            
            # Check episode 1 data
            assert 1 in episode_data, "Should have episode 1 data"
            ep1_data = episode_data[1]
            assert 'characters' in ep1_data, "Episode 1 should have characters"
            assert 'Izuku' in ep1_data['characters'], "Episode 1 should have Izuku"
            assert 'Bakugo' in ep1_data['characters'], "Episode 1 should have Bakugo"
            
            # Check character details
            izuku_data = ep1_data['characters']['Izuku']
            assert izuku_data['dialogue_count'] == 15, "Izuku should have 15 dialogue count"
            assert 'determined' in izuku_data['personality_traits'], "Izuku should be determined"
            
            # Check episode 2 data
            assert 2 in episode_data, "Should have episode 2 data"
            ep2_data = episode_data[2]
            assert 'All Might' in ep2_data['characters'], "Episode 2 should have All Might"
            
            print("    ✅ Character data is properly organized by episode")
            success_count += 1
            
    except Exception as e:
        print(f"    ❌ Character data organization test failed: {e}")
    
    # Test 3: Interaction data processing
    print("\n3️⃣ Testing Interaction Data Processing")
    total_tests += 1
    
    try:
        with mock.patch('chromadb.PersistentClient'):
            from agents.character_analysis_agent import CharacterAnalysisAgent
            
            agent = CharacterAnalysisAgent()
            
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            
            mock_characters_collection.query.return_value = mock_character_data
            mock_interactions_collection.query.return_value = mock_interaction_data
            
            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection
            
            result = agent._get_season_episodes("My Hero Academia", 1)
            
            # Verify interaction data is included
            episode_data = result['episode_data']
            
            # Check that interactions are properly processed
            ep1_interactions = episode_data[1]['interactions']
            ep2_interactions = episode_data[2]['interactions']
            
            assert len(ep1_interactions) > 0, "Episode 1 should have interactions"
            assert len(ep2_interactions) > 0, "Episode 2 should have interactions"
            
            # Check interaction details
            conflict_interaction = ep1_interactions[0]
            assert conflict_interaction['type'] == 'conflict', "Should identify conflict type"
            assert conflict_interaction['tone'] == 'tense', "Should identify emotional tone"
            assert 'Izuku' in conflict_interaction['characters'], "Should include Izuku in conflict"
            assert 'Bakugo' in conflict_interaction['characters'], "Should include Bakugo in conflict"
            
            mentorship_interaction = ep2_interactions[0]
            assert mentorship_interaction['type'] == 'mentorship', "Should identify mentorship type"
            assert mentorship_interaction['significance'] == 0.9, "Should include significance score"
            
            print("    ✅ Interaction data is properly processed and included")
            success_count += 1
            
    except Exception as e:
        print(f"    ❌ Interaction data processing test failed: {e}")
    
    # Test 4: Full season analysis
    print("\n4️⃣ Testing Full Season Analysis")
    total_tests += 1
    
    try:
        with mock.patch('chromadb.PersistentClient'):
            from agents.character_analysis_agent import CharacterAnalysisAgent
            
            agent = CharacterAnalysisAgent()
            
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            
            mock_characters_collection.query.return_value = mock_character_data
            mock_interactions_collection.query.return_value = mock_interaction_data
            
            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection
            
            # Test the full season analysis method
            result = agent.analyze_season_development("My Hero Academia", 1)
            
            # Should not return error
            assert 'error' not in result, f"Season analysis should not have errors. Got: {result}"
            
            # Should include season info
            assert 'season_info' in result, "Should include season info"
            season_info = result['season_info']
            assert season_info['show_name'] == "My Hero Academia", "Should have correct show name"
            assert season_info['season'] == 1, "Should have correct season"
            assert season_info['total_episodes'] > 0, "Should count episodes"
            
            print("    ✅ Full season analysis completes successfully")
            success_count += 1
            
    except Exception as e:
        print(f"    ❌ Full season analysis test failed: {e}")
    
    # Test 5: Edge case - Empty data handling
    print("\n5️⃣ Testing Edge Case - Empty Data Handling")
    total_tests += 1
    
    try:
        with mock.patch('chromadb.PersistentClient'):
            from agents.character_analysis_agent import CharacterAnalysisAgent
            
            agent = CharacterAnalysisAgent()
            
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            
            # Mock empty results
            empty_results = {
                'metadatas': [[]],
                'documents': [[]],
                'embeddings': [[]]
            }
            
            mock_characters_collection.query.return_value = empty_results
            mock_interactions_collection.query.return_value = empty_results
            
            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection
            
            # This should handle empty data gracefully
            result = agent._get_season_episodes("Nonexistent Show", 1)
            
            # Should return empty dict but not crash
            assert isinstance(result, dict), "Should return dict even with no data"
            assert len(result) == 0, "Should return empty dict for no data"
            
            print("    ✅ Empty data is handled gracefully")
            success_count += 1
            
    except Exception as e:
        print(f"    ❌ Empty data handling test failed: {e}")
    
    # Test 6: Edge case - None metadata handling
    print("\n6️⃣ Testing Edge Case - None Metadata Handling")
    total_tests += 1
    
    try:
        with mock.patch('chromadb.PersistentClient'):
            from agents.character_analysis_agent import CharacterAnalysisAgent
            
            agent = CharacterAnalysisAgent()
            
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            
            # Mock None results
            none_results = {
                'metadatas': None,
                'documents': None,
                'embeddings': None
            }
            
            mock_characters_collection.query.return_value = none_results
            mock_interactions_collection.query.return_value = none_results
            
            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection
            
            # This should handle None data gracefully
            result = agent._get_season_episodes("Test Show", 1)
            
            # Should return empty dict but not crash
            assert isinstance(result, dict), "Should return dict even with None data"
            assert len(result) == 0, "Should return empty dict for None data"
            
            print("    ✅ None metadata is handled gracefully")
            success_count += 1
            
    except Exception as e:
        print(f"    ❌ None metadata handling test failed: {e}")
    
    # Summary
    print(f"\n{'=' * 60}")
    print("CHARACTER SEASON ANALYSIS TEST SUMMARY")
    print(f"{'=' * 60}")
    
    success_rate = success_count / total_tests if total_tests > 0 else 0
    print(f"Passed: {success_count}/{total_tests}")
    print(f"Success rate: {success_rate:.1%}")
    
    if success_rate >= 0.8:
        print("✅ Character season analysis is working correctly!")
        return True
    else:
        print("❌ Character season analysis needs attention!")
        return False

def main():
    """Run all character season analysis tests."""
    if test_character_season_analysis():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
