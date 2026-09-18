#!/usr/bin/env python3
"""
Unit tests for Basic Content Caching System.

This module tests the ContentCache implementation for AI-generated content,
including similarity detection, LRU eviction, and cross-episode content reuse.

Following TDD methodology - these tests should FAIL initially (RED phase).
"""

import pytest
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any, List

# Import the module we're testing - will fail initially
try:
    from core.content_cache import (
        ContentCache,
        CacheStats,
        CacheConfig,
        ContentType,
        SimilarityCalculator,
    )
except ImportError:
    # Expected to fail in RED phase
    pytest.skip("ContentCache not implemented yet", allow_module_level=True)


class TestContentCache:
    """Test suite for basic content caching system."""

    @pytest.fixture
    def cache_config(self) -> CacheConfig:
        """Cache configuration for testing."""
        return CacheConfig(
            max_content_entries=100,
            max_image_entries=50,
            similarity_threshold=0.85,
            ttl_hours=24,
            enable_lru_eviction=True
        )

    @pytest.fixture
    def content_cache(self, cache_config) -> ContentCache:
        """ContentCache instance for testing."""
        return ContentCache(config=cache_config)

    @pytest.fixture
    def sample_text_content(self) -> str:
        """Sample text content for caching tests."""
        return "Naruto trains intensely with his shadow clones in the forest."

    @pytest.fixture
    def similar_text_content(self) -> str:
        """Similar text content for similarity testing."""
        return "Naruto practices hard with shadow clones in the woods."

    @pytest.fixture
    def sample_image_data(self) -> Dict[str, Any]:
        """Sample image data for caching tests."""
        return {
            "prompt": "anime style forest training scene",
            "style": "consistent_anime",
            "characters": ["Naruto"],
            "resolution": "1920x1080",
            "url": "/generated/image_123.png"
        }

    def test_cache_initialization(self, cache_config):
        """Test that ContentCache initializes correctly."""
        cache = ContentCache(config=cache_config)
        
        assert cache.config == cache_config
        assert len(cache._content_cache) == 0
        assert len(cache._image_cache) == 0
        assert cache.stats.cache_hits == 0
        assert cache.stats.cache_misses == 0

    def test_cache_text_content_success(self, content_cache, sample_text_content):
        """Test caching text content successfully."""
        content_hash = content_cache._generate_content_hash(
            sample_text_content, ContentType.TEXT
        )
        
        # Cache the content
        result = content_cache.cache_content(
            content_hash, sample_text_content, ContentType.TEXT
        )
        
        assert result is True
        assert content_hash in content_cache._content_cache
        
        cached_item = content_cache._content_cache[content_hash]
        assert cached_item['content'] == sample_text_content
        assert cached_item['usage_count'] == 0
        assert isinstance(cached_item['created_at'], datetime)

    def test_cache_image_content_success(self, content_cache, sample_image_data):
        """Test caching image content successfully."""
        content_hash = content_cache._generate_content_hash(
            sample_image_data, ContentType.IMAGE
        )
        
        # Cache the image data
        result = content_cache.cache_content(
            content_hash, sample_image_data, ContentType.IMAGE
        )
        
        assert result is True
        assert content_hash in content_cache._image_cache
        
        cached_item = content_cache._image_cache[content_hash]
        assert cached_item['content'] == sample_image_data
        assert cached_item['usage_count'] == 0

    def test_retrieve_cached_content_hit(self, content_cache, sample_text_content):
        """Test successful cache hit when retrieving content."""
        content_hash = content_cache._generate_content_hash(
            sample_text_content, ContentType.TEXT
        )
        
        # Cache the content first
        content_cache.cache_content(content_hash, sample_text_content, ContentType.TEXT)
        
        # Retrieve from cache
        retrieved = content_cache.get_cached_content(content_hash, ContentType.TEXT)
        
        assert retrieved == sample_text_content
        assert content_cache.stats.cache_hits == 1
        assert content_cache.stats.cache_misses == 0
        
        # Usage count should increment
        cached_item = content_cache._content_cache[content_hash]
        assert cached_item['usage_count'] == 1

    def test_retrieve_cached_content_miss(self, content_cache):
        """Test cache miss when content doesn't exist."""
        non_existent_hash = "non_existent_hash_123"
        
        retrieved = content_cache.get_cached_content(
            non_existent_hash, ContentType.TEXT
        )
        
        assert retrieved is None
        assert content_cache.stats.cache_hits == 0
        assert content_cache.stats.cache_misses == 1

    def test_content_similarity_detection(self, content_cache, sample_text_content, similar_text_content):
        """Test similarity detection between similar content."""
        # Cache original content
        original_hash = content_cache._generate_content_hash(
            sample_text_content, ContentType.TEXT
        )
        content_cache.cache_content(original_hash, sample_text_content, ContentType.TEXT)
        
        # Check for similar content
        similar_content = content_cache.find_similar_content(
            similar_text_content, ContentType.TEXT
        )
        
        assert similar_content is not None
        assert similar_content['content'] == sample_text_content
        assert similar_content['similarity_score'] >= 0.85

    def test_content_similarity_below_threshold(self, content_cache, sample_text_content):
        """Test that dissimilar content doesn't match."""
        # Cache original content
        original_hash = content_cache._generate_content_hash(
            sample_text_content, ContentType.TEXT
        )
        content_cache.cache_content(original_hash, sample_text_content, ContentType.TEXT)
        
        # Try to find similar content with very different text
        dissimilar_content = "Sasuke uses his Sharingan in a completely different battle."
        similar_content = content_cache.find_similar_content(
            dissimilar_content, ContentType.TEXT
        )
        
        assert similar_content is None

    def test_lru_eviction_when_cache_full(self, content_cache):
        """Test LRU eviction when cache reaches maximum capacity."""
        # Fill cache to capacity (100 entries)
        for i in range(100):
            content = f"Sample content {i}"
            content_hash = content_cache._generate_content_hash(content, ContentType.TEXT)
            content_cache.cache_content(content_hash, content, ContentType.TEXT)
        
        # Access first item to make it recently used
        first_hash = content_cache._generate_content_hash("Sample content 0", ContentType.TEXT)
        content_cache.get_cached_content(first_hash, ContentType.TEXT)
        
        # Add one more item to trigger eviction
        new_content = "New content that should trigger eviction"
        new_hash = content_cache._generate_content_hash(new_content, ContentType.TEXT)
        content_cache.cache_content(new_hash, new_content, ContentType.TEXT)
        
        # Cache should still have max entries
        assert len(content_cache._content_cache) == 100
        
        # First item should still exist (recently accessed)
        assert first_hash in content_cache._content_cache
        
        # Some other item should have been evicted
        second_hash = content_cache._generate_content_hash("Sample content 1", ContentType.TEXT)
        assert second_hash not in content_cache._content_cache

    def test_ttl_expiration(self, content_cache, sample_text_content):
        """Test that content expires after TTL."""
        content_hash = content_cache._generate_content_hash(
            sample_text_content, ContentType.TEXT
        )
        
        # Cache content with past timestamp
        with patch('core.content_cache.datetime') as mock_datetime:
            past_time = datetime.now() - timedelta(hours=25)  # Expired
            mock_datetime.now.return_value = past_time
            
            content_cache.cache_content(
                content_hash, sample_text_content, ContentType.TEXT
            )
        
        # Try to retrieve expired content
        retrieved = content_cache.get_cached_content(content_hash, ContentType.TEXT)
        
        assert retrieved is None
        assert content_hash not in content_cache._content_cache

    def test_cache_stats_tracking(self, content_cache, sample_text_content):
        """Test that cache statistics are tracked correctly."""
        content_hash = content_cache._generate_content_hash(
            sample_text_content, ContentType.TEXT
        )
        
        # Cache content
        content_cache.cache_content(content_hash, sample_text_content, ContentType.TEXT)
        
        # Test cache hit
        content_cache.get_cached_content(content_hash, ContentType.TEXT)
        assert content_cache.stats.cache_hits == 1
        
        # Test cache miss
        content_cache.get_cached_content("non_existent", ContentType.TEXT)
        assert content_cache.stats.cache_misses == 1
        
        # Test hit rate calculation
        assert content_cache.stats.hit_rate == 0.5

    def test_cross_episode_content_reuse(self, content_cache):
        """Test that content can be reused across different episodes."""
        # Common content that might appear in multiple episodes
        common_prompt = "anime style village scene with cherry blossoms"
        
        # Episode 1 context
        ep1_hash = content_cache._generate_content_hash(
            common_prompt, ContentType.TEXT, episode_context="S1E1"
        )
        content_cache.cache_content(ep1_hash, common_prompt, ContentType.TEXT)
        
        # Episode 2 context - should find similar content
        similar_content = content_cache.find_similar_content(
            common_prompt, ContentType.TEXT, episode_context="S1E2"
        )
        
        assert similar_content is not None
        assert similar_content['content'] == common_prompt

    def test_content_hash_generation_consistency(self, content_cache):
        """Test that content hash generation is consistent."""
        content = "Test content for hashing"
        
        hash1 = content_cache._generate_content_hash(content, ContentType.TEXT)
        hash2 = content_cache._generate_content_hash(content, ContentType.TEXT)
        
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) > 0

    def test_clear_cache_functionality(self, content_cache, sample_text_content):
        """Test cache clearing functionality."""
        # Add content to cache
        content_hash = content_cache._generate_content_hash(
            sample_text_content, ContentType.TEXT
        )
        content_cache.cache_content(content_hash, sample_text_content, ContentType.TEXT)
        
        assert len(content_cache._content_cache) == 1
        
        # Clear cache
        content_cache.clear_cache(ContentType.TEXT)
        
        assert len(content_cache._content_cache) == 0
        assert len(content_cache._image_cache) == 0  # Should clear all by default

    def test_cache_performance_under_load(self, content_cache):
        """Test cache performance with high volume operations."""
        import time
        
        start_time = time.time()
        
        # Cache 1000 items
        for i in range(1000):
            content = f"Performance test content {i}"
            content_hash = content_cache._generate_content_hash(content, ContentType.TEXT)
            content_cache.cache_content(content_hash, content, ContentType.TEXT)
        
        # Retrieve 1000 items
        for i in range(1000):
            content = f"Performance test content {i}"
            content_hash = content_cache._generate_content_hash(content, ContentType.TEXT)
            content_cache.get_cached_content(content_hash, ContentType.TEXT)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete in reasonable time (< 1 second for 2000 operations)
        assert total_time < 1.0
        # Cache hits limited by max_content_entries (100), rest are evicted
        assert content_cache.stats.cache_hits == 100


class TestSimilarityCalculator:
    """Test suite for content similarity calculation."""

    @pytest.fixture
    def similarity_calculator(self):
        """SimilarityCalculator instance for testing."""
        return SimilarityCalculator()

    def test_text_similarity_high(self, similarity_calculator):
        """Test high similarity detection for similar text."""
        text1 = "Naruto trains with shadow clones in the forest"
        text2 = "Naruto practices with shadow clones in the woods"
        
        similarity = similarity_calculator.calculate_text_similarity(text1, text2)
        
        assert similarity >= 0.8

    def test_text_similarity_low(self, similarity_calculator):
        """Test low similarity for different text."""
        text1 = "Naruto trains with shadow clones"
        text2 = "Sasuke uses his Sharingan in battle"
        
        similarity = similarity_calculator.calculate_text_similarity(text1, text2)
        
        assert similarity < 0.5

    def test_image_prompt_similarity(self, similarity_calculator):
        """Test similarity calculation for image prompts."""
        prompt1 = "anime style forest scene with ninja training"
        prompt2 = "anime style woodland scene with ninja practice"
        
        similarity = similarity_calculator.calculate_prompt_similarity(prompt1, prompt2)
        
        assert similarity >= 0.65


class TestCacheConfig:
    """Test suite for cache configuration."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = CacheConfig()
        
        assert config.max_content_entries == 1000
        assert config.max_image_entries == 500
        assert config.similarity_threshold == 0.85
        assert config.ttl_hours == 24
        assert config.enable_lru_eviction is True

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = CacheConfig(
            max_content_entries=50,
            similarity_threshold=0.9,
            ttl_hours=12
        )
        
        assert config.max_content_entries == 50
        assert config.similarity_threshold == 0.9
        assert config.ttl_hours == 12


class TestCacheStats:
    """Test suite for cache statistics tracking."""

    def test_stats_initialization(self):
        """Test that cache stats initialize correctly."""
        stats = CacheStats()
        
        assert stats.cache_hits == 0
        assert stats.cache_misses == 0
        assert stats.hit_rate == 0.0
        assert stats.total_entries == 0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation with various scenarios."""
        stats = CacheStats()
        
        # No operations yet
        assert stats.hit_rate == 0.0
        
        # Update stats
        stats.cache_hits = 8
        stats.cache_misses = 2
        
        assert stats.hit_rate == 0.8

    def test_stats_reset(self):
        """Test resetting cache statistics."""
        stats = CacheStats()
        stats.cache_hits = 10
        stats.cache_misses = 5
        
        stats.reset()
        
        assert stats.cache_hits == 0
        assert stats.cache_misses == 0
        assert stats.hit_rate == 0.0


class TestCacheIntegration:
    """Integration tests for content cache with existing systems."""

    @pytest.fixture
    def mock_image_generator(self):
        """Mock image generator for integration testing."""
        generator = Mock()
        generator.generate_image.return_value = {
            "url": "/generated/test_image.png",
            "prompt": "test prompt",
            "style": "anime"
        }
        return generator

    def test_cache_integration_with_image_generation(self, mock_image_generator):
        """Test cache integration with image generation workflow."""
        content_cache = ContentCache()
        prompt = "anime forest training scene"
        
        # First generation - should miss cache
        result1 = content_cache.get_or_generate_image(
            prompt, mock_image_generator, episode_context="S1E1"
        )
        
        assert content_cache.stats.cache_misses == 1
        assert mock_image_generator.generate_image.call_count == 1
        
        # Second generation with same prompt - should find similar content
        result2 = content_cache.get_or_generate_image(
            prompt, mock_image_generator, episode_context="S1E1"  # Same context should hit cache
        )
        
        assert content_cache.stats.cache_hits == 1
        assert mock_image_generator.generate_image.call_count == 1  # No additional call
        assert result1 == result2

    def test_cache_with_character_enhancement_integration(self):
        """Test cache integration with character enhancement system."""
        content_cache = ContentCache()
        character_data = {
            "name": "Naruto",
            "importance": 0.9,
            "screen_time": 0.8
        }
        
        # Cache character analysis
        character_hash = content_cache._generate_content_hash(
            character_data, ContentType.CHARACTER_ANALYSIS
        )
        content_cache.cache_content(character_hash, character_data, ContentType.CHARACTER_ANALYSIS)
        
        # Retrieve for different episode
        retrieved = content_cache.get_cached_content(character_hash, ContentType.CHARACTER_ANALYSIS)
        
        assert retrieved == character_data

    def test_cache_memory_constraints(self):
        """Test cache behavior under memory constraints."""
        # Create cache with very small limits
        small_config = CacheConfig(
            max_content_entries=5,
            max_image_entries=3
        )
        cache = ContentCache(config=small_config)
        
        # Fill beyond capacity
        for i in range(10):
            content = f"Content {i}"
            content_hash = cache._generate_content_hash(content, ContentType.TEXT)
            cache.cache_content(content_hash, content, ContentType.TEXT)
        
        # Should not exceed max entries
        assert len(cache._content_cache) <= 5

    def test_cache_persistence_across_sessions(self, tmp_path):
        """Test cache persistence to disk for cross-session reuse."""
        cache_file = tmp_path / "content_cache.json"
        
        config = CacheConfig(persist_to_disk=True, cache_file_path=str(cache_file))
        cache = ContentCache(config=config)
        
        # Cache some content
        content = "Persistent test content"
        content_hash = cache._generate_content_hash(content, ContentType.TEXT)
        cache.cache_content(content_hash, content, ContentType.TEXT)
        
        # Save cache
        cache.save_to_disk()
        assert cache_file.exists()
        
        # Create new cache instance and load
        new_cache = ContentCache(config=config)
        new_cache.load_from_disk()
        
        # Should retrieve cached content
        retrieved = new_cache.get_cached_content(content_hash, ContentType.TEXT)
        assert retrieved == content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
