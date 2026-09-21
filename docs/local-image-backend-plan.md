# Plan: a local FLUX.1-schnell image backend

Assessed at `0e97006`. Depends on Phase 1 of
[content-cache-plan.md](content-cache-plan.md) — both need the same generator
seam, and it should be built once.

## Why this is cheaper than it looks

`torch==2.7.1` and `transformers==4.54.0` are already hard dependencies in
`requirements.txt`. The 1.1 GB install everyone already pays for covers the
expensive part; this adds `diffusers` and `accelerate`, which are small.

The target hardware is an **M1 Max with 64 GB unified memory**. FLUX.1-schnell is
roughly 24 GB in bf16, so it fits with room to spare — on a 16 GB machine this
plan would not be viable and SDXL would be the honest recommendation instead.

**Licensing matters here and the variants differ.** FLUX.1-schnell is released
under Apache 2.0, which permits commercial use. FLUX.1-dev is a non-commercial
licence. This plan is specifically for *schnell*; substituting *dev* changes what
you are allowed to do with the output and should not be done casually.

## Current state of the seam

Two injection points exist and the paid path uses neither:

- `core/visual_coherence_manager.py:56` accepts an injected image generator
- `core/content_cache.py:425` documents a `generate_image(prompt)` protocol
- The only implementation is a test fake at `tests/conftest.py:248`
- `media/media_utils.py` `create_image` constructs a Google client inline and
  calls Imagen directly

So the architecture for swapping generators is already described in three places
and routed around in the one place that spends money.

## Phases

### Phase 1 — shared with the cache plan

The generator protocol and an Imagen adapter. Do not build it twice. If the cache
plan lands first, this phase is already done.

### Phase 2 — the local backend (~1–2 days)

A second implementation of the same protocol, in a new module under `core/`,
loading FLUX.1-schnell through `diffusers` with the MPS device.

Decisions to make explicitly rather than by default:

- **Steps.** schnell is a 4-step distilled model. It does not want 30 steps and
  will not improve with them; running it like SDXL wastes minutes per image.
- **Seeding.** Take a seed per image derived from the prompt, so a re-run
  reproduces the frame. This matters for the cache plan — a deterministic
  generator makes an exact-hash hit and a regeneration equivalent, which makes
  cache correctness testable.
- **Model residency.** Loading 24 GB per image is unusable. The pipeline
  generates N images per episode in a loop, so the backend must hold the model
  across calls and release it when the run ends.
- **Where weights live.** Not in the repo, not in `data/`. A configurable cache
  directory defaulting to the platform location, so the CI-parity guard in
  `tests/conftest.py` — which already blocks model downloads and repo `data/`
  access — stays satisfied.

### Phase 3 — selection and fallback (~half a day)

A setting choosing the backend: Imagen, local, or the existing placeholder
renderer. Default stays Imagen so nothing changes for an existing user.

The fallback chain is the interesting part. `media/media_utils.py` already has a
placeholder title-card path for when generation is unavailable, and the
degradation lesson from `b6fde06` applies directly: an optional backend has to be
optional for every reason it can be unavailable. Missing `diffusers`, absent
weights, insufficient memory, and an MPS failure are four different causes and
each should degrade with its reason logged, not just the one that was thought of.

### Phase 4 — measure the tradeoff (~half a day)

`image_generation` is already a timed telemetry stage, so the comparison is
nearly free. Record for the same episode on both backends: wall-clock per image,
total run time, and cost — which is a real measured number for Imagen and
genuinely zero marginal for local.

Write it into `docs/operations.md` next to the existing cost table. **The measured
tradeoff is the artifact worth having**; "pluggable backends with numbers" reads
considerably better than either backend alone.

Expected shape, to be replaced by measurement: roughly 30–60s per 1024×1024 image
on this hardware at 4 steps, against seconds for the API. At 5–15 images per
episode that is minutes versus seconds — acceptable for an offline batch pipeline
with `--resume` already working, and unacceptable for anything interactive.

## Constraints that must hold

- **CI must not download 24 GB.** The parity guard already forces offline mode and
  an empty model cache, so local-backend tests must use a fake pipeline object,
  not real weights. Any test wanting real weights belongs behind the `network`
  marker and will not run by default.
- **`make demo` must keep working with no model present**, on the placeholder
  path. The demo's value is that a stranger can run it in 26 seconds.
- **`requirements-demo.txt` must not grow.** The slim set exists so the demo image
  stays ~330 MB; `diffusers` belongs with the full install or in an extra.

## On prompts

The coherence manager builds prompts from style and scene description rather than
character likenesses, and that should not change with the backend. Running
inference locally changes who hosts the compute, not the derivative-work position
that `docs/adr/` already records as an open question. Keeping prompts to original
scene description — what happens in a shot — rather than naming characters is
both the safer position and, in practice, what the existing prompt construction
already does.

## Honest assessment

The cost saving is real but secondary: image spend is bounded by episode count,
and the unbounded-plot-point issue is a larger lever than the per-image price.
The stronger reasons to do this are that it removes a paid dependency from the
critical path, makes the pipeline runnable with no API key at full quality rather
than placeholder quality, and produces a measured comparison between two real
backends.

If the goal is purely to spend less, the cache plan and a cap on plot points are
cheaper and land sooner.
