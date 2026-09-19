# Content cache

`core/content_cache.py` is an in-process cache for generated content — text,
character analyses and image-generation results. It combines exact-hash lookup
with similarity matching. Covered by `tests/unit/test_content_cache.py`.

> **This module has no production call sites.** Nothing in `agents/`, `core/`,
> `main.py`, `utils/` or `media/` constructs a `ContentCache`. It is a working,
> tested component that is not wired into the pipeline, and no generator in this
> repository implements the `generate_image(prompt)` protocol that
> `get_or_generate_image()` requires. Treat everything below as a description of
> a library, not of pipeline behaviour. There are no measured cost or speed
> savings for this repository, because the cache never runs in it.

This file used to be ~700 lines of configuration guidance, sizing tables, cache
warming, security notes and monitoring dashboards for that uncalled component,
and closed by calling it "production-ready and integrated into the main video
generation pipeline". It was cut to what can be checked against the source.
**It should probably be deleted outright**; it survives only because
`README.md` and `docs/architecture.md` link to it and
`tests/test_documentation.py` asserts that README's `docs/` links resolve.

## API

Every signature below is current as of `core/content_cache.py`.

```python
class ContentCache:
    def __init__(self, config: CacheConfig | None = None)

    def cache_content(self, content_hash: str, content: Any,
                      content_type: ContentType) -> bool
    def get_cached_content(self, content_hash: str,
                           content_type: ContentType) -> Any | None
    def find_similar_content(self, content: Any, content_type: ContentType,
                             episode_context: str | None = None) -> dict[str, Any] | None
    def get_or_generate_image(self, prompt: str, image_generator: Any,
                              episode_context: str | None = None) -> dict[str, Any]
    def clear_cache(self, content_type: ContentType | None = None) -> None
    def save_to_disk(self) -> bool
    def load_from_disk(self) -> bool
    def get_cache_info(self) -> dict[str, Any]
```

Factory:

```python
def create_content_cache(max_content_entries: int = 1000,
                         max_image_entries: int = 500,
                         similarity_threshold: float = 0.85,
                         enable_persistence: bool = False) -> ContentCache
```

`ContentType` is an `Enum` with exactly four members: `TEXT`, `IMAGE`,
`CHARACTER_ANALYSIS`, `AUDIO`.

`CacheConfig` is a dataclass with eight fields and the defaults shown:

```python
CacheConfig(
    max_content_entries=1000,
    max_image_entries=500,
    similarity_threshold=0.85,
    ttl_hours=24,
    enable_lru_eviction=True,
    persist_to_disk=False,  # note: False, not True
    cache_file_path="data/cache/content_cache.json",
    enable_similarity_search=True,
)
```

There is no `_cleanup_expired_entries()` and no `_reorganize_lru_order()`.
Expiry is checked lazily by `_is_expired()` on read; eviction happens in
`_evict_lru_entry()` on write.

## Usage

```python
from core.content_cache import ContentCache, CacheConfig, ContentType

cache = ContentCache(config=CacheConfig(max_image_entries=5, persist_to_disk=False))

content_hash = cache._generate_content_hash({"prompt": "anime forest"}, ContentType.IMAGE)
cache.cache_content(content_hash, {"path": "a.png"}, ContentType.IMAGE)
cache.get_cached_content(content_hash, ContentType.IMAGE)  # -> {'path': 'a.png'}
```

Hashing is the only way to produce a key, and `_generate_content_hash` is
private — a public key-derivation method is the obvious missing piece if this is
ever wired in.

### `get_or_generate_image`

Generator-agnostic: pass any object exposing `generate_image(prompt) -> dict`.

```python
class MyGenerator:
    def generate_image(self, prompt: str) -> dict:
        return {"path": f"{prompt}.png"}


cache.get_or_generate_image("a new prompt", MyGenerator())
# -> {'path': 'a new prompt.png'}

cache.get_or_generate_image("another", object())
# TypeError: image_generator 'object' does not implement the required
#            'generate_image(prompt)' method
```

**It never returns a falsy value.** It returns a dict or raises `TypeError`, so
`if not cached_result: ...generate anyway...` is dead code.

### `get_cache_info`

Returns four top-level keys — `stats`, `content_cache`, `image_cache`, `config`:

```python
info = cache.get_cache_info()
info["stats"]  # cache_hits, cache_misses, hit_rate, total_entries
info["content_cache"]  # entries, max_entries, usage_percentage
info["image_cache"]  # entries, max_entries, usage_percentage
info["config"]  # similarity_threshold, ttl_hours, lru_eviction_enabled
```

`hit_rate` returns `0.0` when there have been no requests, so it is safe to
format directly.

## Similarity

`SimilarityCalculator` exposes `calculate_text_similarity(a, b)` and
`calculate_prompt_similarity(a, b)`. Measured on the current implementation:

```python
sc = SimilarityCalculator()

sc.calculate_text_similarity(
    "Naruto trains with shadow clones in the forest",
    "Naruto practices with shadow clones in the woods",
)  # -> 1.0

sc.calculate_prompt_similarity(
    "anime style forest scene with ninja training",
    "anime style woodland scene with ninja practice",
)  # -> 0.693
```

Earlier revisions of this guide quoted `~0.87` and `~0.75` for these two pairs.
Both were wrong. Note also that `calculate_text_similarity` returning exactly
`1.0` for two sentences that differ in two words is worth a look — the
normalization appears to discard more than intended.

Similarity matching is *not* as eager as this guide used to claim. With
`{"prompt": "anime forest"}` cached, looking up `{"prompt": "anime woodland"}` at
the default threshold returns `None`, not a hit.

## Format adapter

`IntelligentFormatAdapter` (`core/intelligent_format_adapter.py`) is a separate
component, and the orchestrator does use it. Its two public methods are
coroutines, and **`quality_profile` is a required positional argument**:

```python
async def adapt_content_for_platform(self, content: dict, platform: str,
                                     quality_profile: Any) -> dict
async def batch_adapt_for_platforms(self, content: dict, platforms: list[str],
                                    quality_profile: Any) -> dict[str, dict]
```

There is no `adapt_for_tiktok()`, and calling `adapt_content_for_platform(content,
platform="tiktok")` raises `TypeError` for the missing third argument.

## Tests

```bash
python -m pytest tests/unit/test_content_cache.py -v
```
