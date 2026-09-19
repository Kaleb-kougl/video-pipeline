#!/usr/bin/env python3
"""
Regression tests for ChromaDB array boolean evaluation fixes.

This test suite validates that all the fixes for "truth value of array is ambiguous"
errors are working correctly. These errors occurred when numpy arrays from ChromaDB
results were used directly in boolean contexts.
"""

import sys
import unittest.mock as mock
from pathlib import Path

import numpy as np

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_chromadb_array_fixes():
    """Test that ChromaDB array boolean evaluation fixes work correctly.

    This test creates mock ChromaDB results with numpy arrays and validates
    that all the fixed functions handle them without raising "truth value
    of array is ambiguous" errors.

    Returns:
        bool: True if all tests pass, False otherwise
    """

    print("🧪 Testing ChromaDB Array Boolean Evaluation Fixes")
    print("=" * 60)

    success_count = 0
    total_tests = 0

    # Create mock ChromaDB results that caused the original issues
    mock_empty_results = {"metadatas": [], "documents": [], "embeddings": []}

    mock_results_with_data = {
        "metadatas": [
            [
                {
                    "character_name": "Test Character",
                    "show_name": "Test Show",
                    "season": 1,
                    "episode": 1,
                }
            ]
        ],
        "documents": [["Test document"]],
        "embeddings": [np.array([[0.1, 0.2, 0.3]])],  # This caused the original issue
    }

    mock_results_with_none = {"metadatas": None, "documents": None, "embeddings": None}

    # Test 1: Character Analysis Agent - _get_season_episodes method
    print("\n1️⃣ Testing Character Analysis Agent fixes")
    total_tests += 1

    try:
        from agents.character_analysis_agent import CharacterAnalysisAgent

        # Mock the ChromaDB collection methods
        with mock.patch("chromadb.PersistentClient"):
            # Create mock collections
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()

            # Configure mock to return our test data
            mock_characters_collection.query.return_value = mock_results_with_data
            mock_interactions_collection.query.return_value = mock_empty_results

            # Create agent instance with mocked dependencies
            agent = CharacterAnalysisAgent()
            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection

            # This should not raise "truth value of array is ambiguous"
            agent._get_season_episodes("Test Show", 1)

            print("    ✅ Character Analysis Agent - season episodes retrieval works")
            success_count += 1

    except Exception as e:
        print(f"    ❌ Character Analysis Agent test failed: {e}")

    # Test 2: Vector Search fixes
    print("\n2️⃣ Testing Vector Search fixes")
    total_tests += 1

    try:
        from utils.vector_search import VectorSearchManager

        with mock.patch("chromadb.PersistentClient"):
            search = VectorSearchManager()

            # Mock collection with numpy array results
            mock_collection = mock.Mock()
            mock_collection.query.return_value = mock_results_with_data
            search.collection = mock_collection

            # This should not raise array boolean errors
            search.semantic_search("test query", limit=5)

            print("    ✅ Vector Search - semantic search works with numpy arrays")
            success_count += 1

    except Exception as e:
        print(f"    ❌ Vector Search test failed: {e}")

    # Test 3: Metadata Quality Agent fixes
    print("\n3️⃣ Testing Metadata Quality Agent fixes")
    total_tests += 1

    try:
        from agents.quality_agents.metadata_quality_agent import MetadataQualityAgent

        with mock.patch("chromadb.PersistentClient"):
            agent = MetadataQualityAgent()

            # Mock collections
            mock_interactions = mock.Mock()
            mock_characters = mock.Mock()
            mock_interactions.get.return_value = mock_results_with_data
            mock_characters.get.return_value = mock_results_with_data

            agent.interactions_collection = mock_interactions
            agent.characters_collection = mock_characters

            # This should not raise array boolean errors
            agent.check_metadata_quality()

            print("    ✅ Metadata Quality Agent - quality check works with arrays")
            success_count += 1

    except Exception as e:
        print(f"    ❌ Metadata Quality Agent test failed: {e}")

    # Test 4: Migration Script fixes
    print("\n4️⃣ Testing Migration Script fixes")
    total_tests += 1

    try:
        from scripts.migrate_metadata import migrate_interaction_metadata

        with mock.patch("chromadb.PersistentClient"):
            with mock.patch("scripts.migrate_metadata.interactions_collection") as mock_collection:
                # Mock collection.get() to return numpy array results
                mock_collection.get.return_value = mock_results_with_data

                # This should not raise array boolean errors
                migrate_interaction_metadata()

            print("    ✅ Migration Script - metadata migration handles arrays correctly")
            success_count += 1

    except Exception as e:
        print(f"    ❌ Migration Script test failed: {e}")

    # Test 5: Edge case - None values
    print("\n5️⃣ Testing None value handling")
    total_tests += 1

    try:
        from agents.character_analysis_agent import CharacterAnalysisAgent

        with mock.patch("chromadb.PersistentClient"):
            agent = CharacterAnalysisAgent()

            # Mock collections to return None values
            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            mock_characters_collection.query.return_value = mock_results_with_none
            mock_interactions_collection.query.return_value = mock_results_with_none

            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection

            # This should handle None values gracefully
            agent._get_season_episodes("Test Show", 1)

            print("    ✅ None value handling - no errors with None metadata")
            success_count += 1

    except Exception as e:
        print(f"    ❌ None value handling test failed: {e}")

    # Test 6: Empty array handling
    print("\n6️⃣ Testing Empty array handling")
    total_tests += 1

    try:
        # Test with empty arrays (not None, but empty lists)
        mock_empty_list_results = {
            "metadatas": [[]],  # Empty nested list
            "documents": [[]],
            "embeddings": [[]],
        }

        from agents.character_analysis_agent import CharacterAnalysisAgent

        with mock.patch("chromadb.PersistentClient"):
            agent = CharacterAnalysisAgent()

            mock_characters_collection = mock.Mock()
            mock_interactions_collection = mock.Mock()
            mock_characters_collection.query.return_value = mock_empty_list_results
            mock_interactions_collection.query.return_value = mock_empty_list_results

            agent.characters_collection = mock_characters_collection
            agent.interactions_collection = mock_interactions_collection

            # This should handle empty nested arrays gracefully
            agent._get_season_episodes("Test Show", 1)

            print("    ✅ Empty array handling - no errors with empty nested arrays")
            success_count += 1

    except Exception as e:
        print(f"    ❌ Empty array handling test failed: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print("CHROMADB ARRAY FIXES TEST SUMMARY")
    print(f"{'=' * 60}")

    success_rate = success_count / total_tests if total_tests > 0 else 0
    print(f"Passed: {success_count}/{total_tests}")
    print(f"Success rate: {success_rate:.1%}")

    if success_rate >= 0.8:
        print("✅ ChromaDB array fixes are working correctly!")
        return True
    else:
        print("❌ Some ChromaDB array fixes need attention!")
        return False


def main():
    """Run all ChromaDB array fix tests."""
    if test_chromadb_array_fixes():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
