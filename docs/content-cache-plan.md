# Plan: wire ContentCache into the image path

Assessed at `0e97006`. This is the cheaper of the two image-cost changes and
should land first — it reduces spend whether generation stays on Imagen or moves
local.

## Current state

`core/content_cache.py` is 700 lines, well covered by unit tests, and **has zero
production callers**. A grep outside its own module and the test suite returns
nothing. Every scene is generated from scratch, including scenes an adjacent
episode of the same show already paid for.

What exists and works:

| Piece | Where |
|---|---|
| `cache_content`, `get_cached_content`, `find_similar_content` | `core/content_cache.py` |
| `get_or_generate_image(prompt, image_generator, episode_context)` | `core/content_cache.py:425` |
| `SimilarityCalculator` — 0.7 keyword / 0.3 text weighting, 0.85 threshold | same file |
| TTL + LRU eviction, `save_to_disk` / `load_from_disk` | same file |
| `CacheStats.hit_rate` | same file |

The image path it needs to intercept:

- `media/media_utils.py` `create_images(sentences, episode, season, show)` loops
  over plot points calling `create_image(sentence, episode, season, show, index)`
- `create_image` calls Imagen directly and writes a PNG to a path derived from
  show/season/episode/index
- Production callers: `agents/workflow_orchestrator.py:596` and `main.py`

## The problem to solve first

**`get_or_generate_image` returns content; `create_image` writes files.** The
cache is keyed by prompt hash and hands back a cached value, while the renderer
expects a PNG at a deterministic path that `mp4_file_enhanced` later reads. These
are different contracts and the plan is mostly about reconciling them.

Two options, and the choice determines everything downstream:

1. **Cache stores bytes.** A hit writes a fresh copy to the new path. Simple,
   self-contained, costs disk proportional to hits.
2. **Cache stores paths.** A hit copies or hardlinks an existing file. Cheaper on
   disk, but the cache now owns references to files under gitignored show
   directories that the user may delete, so every read needs an existence check
   and a miss path.

**Recommendation: bytes.** The cache already serialises content to JSON on disk
and already has TTL/LRU eviction sized in entries; paths would make eviction and
staleness two different problems. Decide this before writing code.

## The risk nobody has raised yet

A 0.85 similarity threshold means a *near* match returns **a different scene's
image**. That is the feature — adjacent episodes request visually similar scenes
— but it is also a quality decision that has never been looked at in output.

Two scenes that score 0.86 may be describing meaningfully different moments, and
reusing a frame across them will read as a rendering bug, not a saving. Before
enabling similarity matching in production, generate a season with the cache on
and **look at the frames**. The threshold is configurable for a reason; exact-hash
hits are free of this risk and similarity hits are not.

An honest fallback if the frames look wrong: ship exact-hash caching only, and
leave similarity behind a flag that defaults off. That still captures the
identical-prompt case, which is the common one within a season.

## Phases

### Phase 1 — an adapter, no behaviour change (~half a day)

Add an image-generator object that implements the documented protocol —
`generate_image(prompt)` returning a dict — and wraps the existing Imagen call.
The only implementation today is a test fake at `tests/conftest.py:248`, which
already pins the interface.

`create_image` then calls through that object rather than constructing a client
inline. No caching yet. This is the change that makes everything else possible,
and it is independently useful: it is the same seam the local-backend plan needs.

Land it green with the demo still rendering.

### Phase 2 — cache on exact hash only (~half a day)

Route `create_image` through `get_or_generate_image` with the similarity
threshold set so that only exact-hash hits return. Write the returned bytes to
the expected path.

Decide and document the cache lifetime: per-run, per-show, or global. Per-show is
the useful unit, since the saving comes from adjacent episodes of the same show
and cross-show reuse is the case most likely to look wrong.

Wire `save_to_disk` / `load_from_disk` so the cache survives between runs — a
cache that dies with the process saves nothing on the batch it is meant to help.

### Phase 3 — measure it (~half a day)

`CacheStats.hit_rate` exists and nothing reports it. Add the hit rate and the
avoided-call count to the telemetry summary that `core/telemetry.py` already
prints, so the saving is observed rather than asserted.

**This is the phase that makes the feature worth writing about.** The README
currently says the cache exists and is not wired in, and explicitly claims no
savings figure because none is measured. After this phase there is a real number,
produced the same way as every other number in the repo.

### Phase 4 — similarity, gated on looking at the output (~half a day)

Only after Phase 3 gives a baseline. Enable similarity matching behind a setting,
generate a season, compare frames, and record what the threshold does to both hit
rate and visible quality. If the frames are wrong, say so and leave it off — a
documented "we tried it and it reused the wrong scene" is a better artifact than
a silent flag.

## Tests

- The adapter satisfies the same protocol as the fake in `tests/conftest.py`
- A cache hit writes a byte-identical file to the new path and makes no API call
- A miss calls the generator exactly once and stores the result
- Eviction and TTL behave under the configured limits
- The demo path still renders offline with the cache enabled

The CI-parity guard in `tests/conftest.py` will reject any test that writes to the
repo's real `data/` directory, so the on-disk cache needs a `tmp_path` location in
tests and a configurable directory in production.

## What this does not do

It does not reduce the cost of the *first* generation of any scene, does not cap
the unbounded image count per episode (that is a separate fix at the plot-point
level), and does nothing for the text or TTS calls.
