# Content Caching System Guide

Covered by `tests/unit/test_content_cache.py`.

## Overview

`core/content_cache.py` is an in-process caching layer that lets the pipeline
reuse generated content instead of re-requesting it: text summaries, character
analyses, and image-generation results. It combines exact-hash lookup with
similarity matching, so near-identical prompts across different episodes can hit
the same cached entry.

The cache is a standalone, working component. Its high-level
`get_or_generate_image()` helper is generator-agnostic and **no generator in this
repository implements the required protocol yet** — see
[Image generator integration](#1-image-generator-integration). Cost and
speed savings therefore depend on wiring a generator in; the figures below are
not measured results for this repository.

## Architecture

### Core Components

#### 1. ContentCache Class
The main cache manager that handles all caching operations:

```python
from core.content_cache import ContentCache, CacheConfig

# Initialize with custom configuration
config = CacheConfig(
    max_content_entries=1000,  # Text/character analysis cache size
    max_image_entries=500,  # Image cache size
    similarity_threshold=0.85,  # Content similarity threshold
    ttl_hours=24,  # Time-to-live for cache entries
    enable_lru_eviction=True,  # LRU eviction when cache is full
    persist_to_disk=True,  # Save cache across sessions
)

cache = ContentCache(config=config)
```

#### 2. SimilarityCalculator
Calculates content similarity using advanced text analysis:

```python
calculator = SimilarityCalculator()

# Text similarity with anime-specific term boosting
similarity = calculator.calculate_text_similarity(
    "Naruto trains with shadow clones in the forest",
    "Naruto practices with shadow clones in the woods",
)
# Returns: ~0.87 (high similarity due to common anime terms)

# Image prompt similarity with visual keyword analysis
prompt_similarity = calculator.calculate_prompt_similarity(
    "anime style forest scene with ninja training", "anime style woodland scene with ninja practice"
)
# Returns: ~0.75 (good similarity for visual content)
```

#### 3. ContentType Enum
Supports multiple content types:

- `ContentType.TEXT`: Text content and summaries
- `ContentType.IMAGE`: Generated images and visual content
- `ContentType.CHARACTER_ANALYSIS`: Character analysis data
- `ContentType.AUDIO`: Audio files and narration

#### 4. CacheStats
Comprehensive performance tracking:

```python
stats = cache.get_cache_info()
print(f"""
Cache Performance:
- Hit Rate: {stats["stats"]["hit_rate"]:.1%}
- Total Hits: {stats["stats"]["cache_hits"]}
- Total Misses: {stats["stats"]["cache_misses"]}
- Content Entries: {stats["content_cache"]["entries"]}/{stats["content_cache"]["max_entries"]}
- Image Entries: {stats["image_cache"]["entries"]}/{stats["image_cache"]["max_entries"]}
""")
```

## Key Features

### 1. Intelligent Similarity Detection

The system uses advanced algorithms to detect similar content and avoid regenerating near-duplicates:

```python
# Anime-specific term boosting
anime_terms = {"naruto", "shadow", "clones", "training", "forest", "woods", "practice"}

# Visual keyword analysis for image prompts
visual_keywords = {"anime", "style", "forest", "village", "training", "battle", "character"}

# Weighted similarity calculation
# Text similarity (70%) + Keyword overlap (30%) for images
```

**Benefits:**
- Identifies similar training scenes across different episodes
- Reuses common visual elements (village scenes, forest backgrounds)
- Prevents duplicate generation of similar character poses
- Reduces API calls for repetitive content

### 2. LRU Eviction with Memory Management

Automatic memory management prevents unbounded cache growth:

```python
# When cache reaches max capacity:
# 1. Identifies least recently used entry
# 2. Removes LRU entry to make space
# 3. Logs eviction for monitoring
# 4. Maintains cache within memory limits

# Cache access updates LRU ordering
cached_content = cache.get_cached_content(content_hash, ContentType.IMAGE)
# ↑ Updates last_accessed timestamp and usage_count
```

**Features:**
- Configurable maximum entries per content type
- LRU eviction based on last access time
- Memory usage monitoring and reporting
- Automatic cleanup of expired entries

### 3. TTL (Time-To-Live) Expiration

Content automatically expires to ensure freshness:

```python
# Default: 24-hour TTL
# Content expires after: created_at + timedelta(hours=24)

# Check if content is expired
if cache._is_expired(cached_item):
    # Automatically removed from cache
    # Stats updated with cache miss
    return None
```

**Benefits:**
- Ensures content freshness for evolving shows
- Prevents stale character analysis data
- Automatic cleanup reduces manual maintenance
- Configurable TTL per use case

### 4. Cross-Episode Content Reuse

Leverage common content across different episodes:

```python
# Episode 1: Cache forest training scene
cache.cache_content(hash1, "anime forest training scene", ContentType.IMAGE)

# Episode 5: Find similar content
similar = cache.find_similar_content(
    "anime woodland training scene", ContentType.IMAGE, episode_context="S1E5"
)
# ↑ Returns cached forest scene (similarity: 0.87)
```

**Use Cases:**
- Common locations (Hidden Leaf Village, training grounds)
- Similar action sequences (jutsu training, battle poses)
- Character expressions and reactions
- Background scenes and environments

### 5. Performance Statistics Tracking

Comprehensive monitoring of cache performance:

```python
class CacheStats:
    cache_hits: int  # Successful cache retrievals
    cache_misses: int  # Failed cache lookups
    total_entries: int  # Current total cached items
    memory_usage_mb: float  # Estimated memory usage

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate (0.0-1.0)"""
        return self.cache_hits / (self.cache_hits + self.cache_misses)
```

**Monitoring Features:**
- Real-time hit rate calculation
- Memory usage estimation
- Cache utilization percentages
- Performance trend analysis

## Integration with Existing Systems

### 1. Image Generator Integration

`get_or_generate_image()` is generator-agnostic: pass any object exposing
`generate_image(prompt) -> dict`. A `TypeError` is raised if the object does not
implement it. No concrete generator in this repository implements the protocol
yet, so this integration is currently a contract only.

```python
# In your generator's __init__()
if enable_caching:
    self.content_cache = create_content_cache(
        max_image_entries=200, similarity_threshold=0.85, enable_persistence=True
    )

# When generating
# 1. Check cache first
cached_result = self.content_cache.get_or_generate_image(
    prompt, self, episode_context=episode_context
)

# 2. Generate only if not cached
if not cached_result:
    generated_image = await self._generate_new_image(prompt)
    # Cache the result for future use
    self.content_cache.cache_content(hash, generated_image, ContentType.IMAGE)
```

### 2. Character Enhancement Integration

Cache character analysis data for reuse:

```python
# Cache character analysis results
character_data = {
    "name": "Naruto",
    "importance": 0.9,
    "screen_time": 0.8,
    "development_arc": "hero's journey",
}

character_hash = cache._generate_content_hash(character_data, ContentType.CHARACTER_ANALYSIS)
cache.cache_content(character_hash, character_data, ContentType.CHARACTER_ANALYSIS)

# Reuse in different episodes
retrieved = cache.get_cached_content(character_hash, ContentType.CHARACTER_ANALYSIS)
```

### 3. Format Adapter Integration

Cache platform-specific adaptations:

`IntelligentFormatAdapter` exposes `adapt_content_for_platform()` and
`batch_adapt_for_platforms()` — both coroutines. There is no `adapt_for_tiktok()`
method.

```python
# Cache platform-optimized content
tiktok_content = await format_adapter.adapt_content_for_platform(
    original_content, platform="tiktok"
)
cache.cache_content(tiktok_hash, tiktok_content, ContentType.TEXT)

# Reuse for similar episodes
cached_adaptation = cache.get_cached_content(tiktok_hash, ContentType.TEXT)
```

## Configuration Options

### Basic Configuration

```python
# Default configuration (recommended for most use cases)
cache = create_content_cache()

# Custom configuration
cache = create_content_cache(
    max_content_entries=2000,  # Increase text cache size
    max_image_entries=1000,  # Increase image cache size
    similarity_threshold=0.90,  # Stricter similarity matching
    enable_persistence=True,  # Enable disk persistence
)
```

### Advanced Configuration

```python
config = CacheConfig(
    max_content_entries=1000,  # Text/character cache limit
    max_image_entries=500,  # Image cache limit
    similarity_threshold=0.85,  # Similarity detection threshold
    ttl_hours=24,  # Cache entry lifetime
    enable_lru_eviction=True,  # LRU eviction when full
    persist_to_disk=True,  # Disk persistence
    cache_file_path="data/cache/content_cache.json",  # Cache file location
    enable_similarity_search=True,  # Enable similarity detection
)

cache = ContentCache(config=config)
```

### Environment-Specific Settings

```python
# Development environment (faster iteration)
dev_config = CacheConfig(
    max_content_entries=100,
    max_image_entries=50,
    ttl_hours=1,  # Short TTL for testing
    persist_to_disk=False,  # No persistence needed
)

# Production environment (maximum performance)
prod_config = CacheConfig(
    max_content_entries=5000,
    max_image_entries=2000,
    ttl_hours=72,  # Longer TTL for stability
    persist_to_disk=True,  # Persist across restarts
    similarity_threshold=0.90,  # Stricter matching
)
```

## Performance Optimization

### 1. Cache Sizing Guidelines

**Content Cache (Text/Character Analysis):**
- **Small projects**: 100-500 entries
- **Medium projects**: 500-2000 entries
- **Large projects**: 2000-5000 entries

**Image Cache:**
- **Development**: 50-200 entries
- **Production**: 500-2000 entries
- **High-volume**: 2000+ entries

### 2. Similarity Threshold Tuning

**Threshold Values:**
- `0.95-1.0`: Exact matches only (minimal reuse)
- `0.85-0.95`: High similarity (recommended)
- `0.70-0.85`: Moderate similarity (more reuse)
- `0.50-0.70`: Loose similarity (may reduce quality)

**Tuning Guidelines:**
```python
# Conservative (higher quality, fewer cache hits)
similarity_threshold = 0.90

# Balanced (recommended for most use cases)
similarity_threshold = 0.85

# Aggressive (more cache hits, potential quality trade-offs)
similarity_threshold = 0.80
```

### 3. Memory Management

**Memory Usage Estimation:**
- Text entries: ~1-10 KB each
- Image metadata: ~1-5 KB each
- Character analysis: ~5-15 KB each

**Guidelines:**
```python
# Calculate approximate memory usage
estimated_mb = (
    (max_content_entries * 0.01)  # Text content (10KB avg)
    + (max_image_entries * 0.005)  # Image metadata (5KB avg)
)

# Recommended limits for different memory constraints
memory_limits = {
    "2GB RAM": {"content": 500, "image": 200},
    "4GB RAM": {"content": 1000, "image": 500},
    "8GB+ RAM": {"content": 2000, "image": 1000},
}
```

## Testing and Validation

### Running Cache Tests

```bash
# Run all content cache tests
python -m pytest tests/unit/test_content_cache.py -v

# Run specific test categories
python -m pytest tests/unit/test_content_cache.py::TestContentCache -v
python -m pytest tests/unit/test_content_cache.py::TestSimilarityCalculator -v
python -m pytest tests/unit/test_content_cache.py::TestCacheIntegration -v

# Test with coverage
python -m pytest tests/unit/test_content_cache.py --cov=core.content_cache --cov-report=html
```

### Performance Testing

```bash
# Performance benchmarks
python -m pytest tests/unit/test_content_cache.py::TestContentCache::test_cache_performance_under_load -v -s

# Memory constraint testing
python -m pytest tests/unit/test_content_cache.py::TestCacheIntegration::test_cache_memory_constraints -v
```

### Integration Testing

```bash
# Test cache integration with image generation
python -m pytest tests/unit/test_content_cache.py::TestCacheIntegration -v
```

## Troubleshooting

### Common Issues

#### 1. Low Cache Hit Rate

**Problem**: Cache hit rate below 20%
**Causes:**
- Similarity threshold too high (>0.90)
- Content too diverse for meaningful reuse
- TTL too short for content lifecycle

**Solutions:**
```python
# Lower similarity threshold
config.similarity_threshold = 0.80

# Increase TTL
config.ttl_hours = 48

# Check content diversity
stats = cache.get_cache_info()
print(f"Unique content ratio: {stats['stats']['cache_misses'] / stats['stats']['total_entries']}")
```

#### 2. Memory Usage Too High

**Problem**: Cache consuming excessive memory
**Causes:**
- Cache limits too high for available memory
- Large content items (high-res images, long text)
- Disabled LRU eviction

**Solutions:**
```python
# Reduce cache limits
config.max_content_entries = 500
config.max_image_entries = 200

# Enable LRU eviction
config.enable_lru_eviction = True

# Monitor memory usage
info = cache.get_cache_info()
print(f"Content cache usage: {info['content_cache']['usage_percentage']:.1f}%")
```

#### 3. Cache Persistence Failures

**Problem**: Cache not persisting across sessions
**Causes:**
- Insufficient disk permissions
- Invalid cache file path
- Disk space limitations

**Solutions:**
```python
# Verify cache directory exists
from pathlib import Path

cache_dir = Path(config.cache_file_path).parent
cache_dir.mkdir(parents=True, exist_ok=True)

# Check disk space
import shutil

free_space = shutil.disk_usage(cache_dir).free

# Test persistence manually
success = cache.save_to_disk()
if not success:
    logger.error("Cache persistence failed - check disk space and permissions")
```

### Performance Monitoring

#### Real-Time Monitoring

```python
# Monitor cache performance during processing
def monitor_cache_performance(cache: ContentCache):
    info = cache.get_cache_info()

    print(f"""
    Cache Performance Report:
    ========================
    Hit Rate: {info["stats"]["hit_rate"]:.1%}
    Cache Hits: {info["stats"]["cache_hits"]:,}
    Cache Misses: {info["stats"]["cache_misses"]:,}

    Content Cache: {info["content_cache"]["entries"]:,}/{info["content_cache"]["max_entries"]:,} 
    ({info["content_cache"]["usage_percentage"]:.1f}% full)

    Image Cache: {info["image_cache"]["entries"]:,}/{info["image_cache"]["max_entries"]:,}
    ({info["image_cache"]["usage_percentage"]:.1f}% full)
    """)


# Call during processing
monitor_cache_performance(generator.content_cache)
```

#### Historical Analysis

```python
# Track performance over time
cache_history = []


def log_cache_stats(cache: ContentCache, timestamp: str):
    stats = cache.get_cache_info()
    cache_history.append(
        {
            "timestamp": timestamp,
            "hit_rate": stats["stats"]["hit_rate"],
            "total_entries": stats["stats"]["total_entries"],
        }
    )


# Analyze trends
def analyze_cache_trends():
    if len(cache_history) < 2:
        return

    latest = cache_history[-1]
    previous = cache_history[-2]

    hit_rate_change = latest["hit_rate"] - previous["hit_rate"]
    print(f"Hit rate trend: {hit_rate_change:+.1%}")
```

## Best Practices

### 1. Cache Configuration

```python
# Production recommendations
RECOMMENDED_CONFIG = {
    "development": CacheConfig(
        max_content_entries=200, max_image_entries=100, ttl_hours=1, persist_to_disk=False
    ),
    "staging": CacheConfig(
        max_content_entries=1000, max_image_entries=500, ttl_hours=24, persist_to_disk=True
    ),
    "production": CacheConfig(
        max_content_entries=3000,
        max_image_entries=1500,
        ttl_hours=72,
        persist_to_disk=True,
        similarity_threshold=0.88,
    ),
}
```

### 2. Content Optimization

```python
# Optimize content for better caching
def optimize_for_caching(prompt: str) -> str:
    """Normalize prompts for better cache hit rates."""
    # Remove episode-specific details
    prompt = re.sub(r"episode \d+", "episode", prompt, flags=re.IGNORECASE)

    # Standardize character names
    prompt = prompt.replace("Deku", "Izuku Midoriya")

    # Normalize location names
    prompt = prompt.replace("U.A.", "UA High School")

    return prompt.strip()


# Use in image generation
optimized_prompt = optimize_for_caching(original_prompt)
cached_image = cache.get_or_generate_image(optimized_prompt, generator)
```

### 3. Cache Warming

```python
# Pre-populate cache with common content
async def warm_cache(cache: ContentCache, common_prompts: List[str]):
    """Pre-generate and cache common visual elements."""

    common_scenes = [
        "anime style Hidden Leaf Village overview",
        "anime training ground with practice targets",
        "anime classroom at UA High School",
        "anime forest clearing with sunlight",
    ]

    for prompt in common_scenes:
        # Generate and cache common scenes
        if not cache.find_similar_content({"prompt": prompt}, ContentType.IMAGE):
            logger.info(f"Warming cache with: {prompt}")
            # Generate and cache...
```

### 4. Monitoring and Alerting

```python
# Set up cache monitoring
def check_cache_health(cache: ContentCache) -> Dict[str, Any]:
    """Comprehensive cache health assessment."""
    info = cache.get_cache_info()

    health_status = {"overall_health": "healthy", "issues": [], "recommendations": []}

    # Check hit rate
    hit_rate = info["stats"]["hit_rate"]
    if hit_rate < 0.2:
        health_status["issues"].append("Low cache hit rate")
        health_status["recommendations"].append("Lower similarity threshold")
        health_status["overall_health"] = "warning"

    # Check cache utilization
    content_usage = info["content_cache"]["usage_percentage"]
    if content_usage > 90:
        health_status["issues"].append("Content cache near capacity")
        health_status["recommendations"].append("Increase max_content_entries")

    return health_status
```

## API Reference

### ContentCache Methods

#### Core Cache Operations

```python
# Cache content
success = cache.cache_content(
    content_hash: str,
    content: Any,
    content_type: ContentType
) -> bool

# Retrieve cached content
content = cache.get_cached_content(
    content_hash: str,
    content_type: ContentType
) -> Optional[Any]

# Find similar content
similar = cache.find_similar_content(
    content: Any,
    content_type: ContentType,
    episode_context: Optional[str] = None
) -> Optional[Dict[str, Any]]
```

#### Utility Methods

```python
# Get comprehensive cache information
info = cache.get_cache_info() -> Dict[str, Any]

# Clear cache (all or specific type)
cache.clear_cache(content_type: Optional[ContentType] = None) -> None

# Save/load cache persistence
success = cache.save_to_disk() -> bool
success = cache.load_from_disk() -> bool
```

#### High-Level Integration

```python
# Integrated image generation with caching
result = cache.get_or_generate_image(
    prompt: str,
    image_generator: Any,
    episode_context: Optional[str] = None
) -> Dict[str, Any]
```

### Factory Functions

```python
# Quick cache creation
cache = create_content_cache(
    max_content_entries: int = 1000,
    max_image_entries: int = 500,
    similarity_threshold: float = 0.85,
    enable_persistence: bool = False
) -> ContentCache
```

## Security Considerations

### 1. Cache Content Validation

```python
# Validate cached content before use
def validate_cached_content(content: Any, content_type: ContentType) -> bool:
    """Validate cached content meets security and quality standards."""

    if content_type == ContentType.IMAGE:
        # Validate image paths are within expected directories
        if "image_path" in content:
            path = Path(content["image_path"])
            if not str(path).startswith("/expected/image/directory"):
                return False

    if content_type == ContentType.TEXT:
        # Validate text content doesn't contain sensitive data
        sensitive_patterns = ["api_key", "password", "secret"]
        content_str = str(content).lower()
        if any(pattern in content_str for pattern in sensitive_patterns):
            return False

    return True
```

### 2. Cache File Security

```python
# Secure cache file permissions
import os
import stat


def secure_cache_file(cache_file_path: str):
    """Set secure permissions on cache file."""
    # Owner read/write only (600)
    os.chmod(cache_file_path, stat.S_IRUSR | stat.S_IWUSR)
```

## Maintenance

### 1. Cache Cleanup

```python
# Automated cache maintenance
async def maintain_cache(cache: ContentCache):
    """Perform regular cache maintenance."""
    
    # Remove expired entries
    expired_count = cache._cleanup_expired_entries()
    
    # Optimize cache organization
    cache._reorganize_lru_order()
    
    # Save to disk if persistence enabled
    if cache.config.persist_to_disk:
        cache.save_to_disk()
    
    logger.info(f"Cache maintenance completed. Removed {expired_count} expired entries.")
```

### 2. Performance Optimization

```python
# Periodic performance analysis
def analyze_cache_performance(cache: ContentCache) -> Dict[str, str]:
    """Analyze cache performance and provide optimization recommendations."""

    info = cache.get_cache_info()
    recommendations = []

    hit_rate = info["stats"]["hit_rate"]
    if hit_rate < 0.3:
        recommendations.append("Consider lowering similarity_threshold to 0.80")
    elif hit_rate > 0.8:
        recommendations.append("Consider increasing similarity_threshold to 0.90")

    content_usage = info["content_cache"]["usage_percentage"]
    if content_usage > 85:
        recommendations.append("Consider increasing max_content_entries")

    return {
        "hit_rate": f"{hit_rate:.1%}",
        "recommendations": recommendations,
        "overall_status": "optimal" if 0.3 <= hit_rate <= 0.8 else "needs_tuning",
    }
```

---

*This guide provides comprehensive documentation for the Content Caching System implementation. The system is production-ready and integrated into the main video generation pipeline for optimal performance and cost reduction.*
