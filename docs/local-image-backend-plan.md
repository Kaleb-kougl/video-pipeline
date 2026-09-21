# Plan: a local image backend

Assessed at `f22155f`. **Revised after review: the model recommendation changed
and most of the performance figures in the first version were wrong.**
Re-read at `59fd32d`: Phase 1 has since been built, so the plan now starts at
Phase 2. Everything below Phase 1 was re-checked against that tree and stands
unless marked.

Phase 1 was the generator adapter described in
[content-cache-plan.md](content-cache-plan.md). It exists:
`core.protocols.ImageFileGenerator`, with `media.media_utils.ImagenImageGenerator`
behind it and a run-scoped instance injected from `main.py` and
`WorkflowOrchestrator`.

## What the first version got wrong

Worth stating, because the errors were all in the same direction — optimistic
about hardware I had not measured.

| Claim | Reality |
|---|---|
| ~30–60s per 1024² image, FLUX.1-schnell, M1 Max | That is roughly the figure for **SDXL**. schnell is a 12B transformer at ~110 TFLOPs/step against maybe 5–7 TFLOPS sustained through MPS: closer to **3–6 minutes per image**, so 20–90 min per episode |
| ~24 GB in bf16, "fits comfortably in 64 GB" | 24 GB is the transformer alone. Plus T5-XXL ~9.5 GB, CLIP-L, VAE ≈ **33.5 GB**, peaking near 38–42 GB with activations — against a macOS GPU-wired limit of roughly 2/3 of RAM. Exceeding it swaps rather than failing, so you get a twenty-minute image and no error |
| Prompt-derived seeds make cache correctness testable | **Bit-identical reproducibility is not achievable on MPS.** No deterministic-algorithms coverage, MPS RNG differs from CPU, kernel selection can vary. Same seed gives perceptually identical output, not identical bytes |
| "runnable with no API key at full quality" | False. Content generation is stage 2 and has no offline substitute; `GOOGLE_API_KEY` is still required. This removes one of three paid calls |
| "the demo image stays ~330 MB" | That figure exists nowhere. The `Dockerfile` header says ~500 MB, and says it is an estimate |
| "cost — a real measured number for Imagen" | Imagen is **not metered**. `docs/operations.md` marks it so, and records that no live paid run has ever been made |
| "the derivative-work position `docs/adr/` records as open" | No ADR covers it. That question is in `docs/portfolio-refinement.md` as an open gap |

## Revised recommendation: SDXL-Lightning, not FLUX

For stylized narrative illustration, offline, 5–15 frames per episode:

| Option | Size | Per image | Licence |
|---|---|---|---|
| **SDXL-Lightning** (LoRA over an SDXL illustration finetune) | ~7 GB fp16 | ~5–15s, 4–8 steps | Apache-2.0 LoRA; base licence varies |
| SDXL base/finetune, 25–30 steps | ~7 GB | ~30–60s | OpenRAIL++-M, commercial use with restrictions |
| SD 3.5-medium | ~5 GB | middle | Stability Community Licence, free under $1M revenue |
| FLUX.1-schnell | ~33 GB total | ~3–6 min | Apache-2.0 |
| SDXL-Turbo | ~7 GB | seconds | **Non-commercial** — same trap as FLUX-dev |

SDXL-Lightning is 20–50x faster than schnell here for arguably better stylized
output, because the SDXL style-LoRA ecosystem is large. schnell's genuine edge is
prompt adherence on complex scenes and text rendering — and most FLUX style LoRAs
target *dev*, which is non-commercial, so the Apache-2.0 advantage quietly erodes
as soon as you want a consistent look.

**If FLUX is wanted anyway**, use `mflux` (MLX) rather than `diffusers`: it is the
fast Apple path and supports 8-bit quantisation (~12 GB). `torch.compile` on MPS
will not close the gap.

## Phases

### Phase 1 — the generator adapter (shared, ~half a day) — **done**

Landed in two commits rather than one, and the interface question was decided
against this plan's recommendation.

`f2597bf` extracted the inline Google client from `create_image` behind
`core.protocols.ImageFileGenerator`, and `59fd32d` made production use it:
`create_images` takes a generator and forwards it to every `create_image`,
`WorkflowOrchestrator` takes it as a keyword-only collaborator, and `main.py`
builds one per process for both the orchestrator and the season path. An Imagen
client is built once per run instead of once per frame, and the demo and the
tests inject instead of monkeypatching — the wiring test asserts that by
failing if `build_image_generator` is called at all.

**The shape is a path, not bytes.** `generate_image(prompt, destination) -> str`
writes the file and returns where it wrote it. This plan recommended bytes; the
render seam it had to match already wrote files (`create_image` names the
destination, and `mp4_file_enhanced` reopens those exact paths), so bytes would
have added an encode/decode hop for no caller. The content-cache seam, which
returns a dict, was left alone rather than bent to fit — see
[content-cache-plan.md](content-cache-plan.md).

**Two consequences for Phase 2**, both in its favour:

- The injection point already exists, so a local backend is a class plus a
  composition-root choice, with no plumbing to change.
- Construction is already run-scoped, which is exactly the residency Phase 2
  needs — the model gets loaded once per run for free rather than needing a
  cache bolted on.

### Phase 2 — the local backend (~1–2 days)

A second implementation of `core.protocols.ImageFileGenerator`: take a prompt
and a destination path, write a PNG there, return the path. Decisions to make
explicitly:

- **Steps and guidance.** Lightning is 4–8 steps. If FLUX: 4 steps,
  `guidance_scale=0.0` (it is guidance-distilled; the dev default degrades it) and
  `max_sequence_length=256`.
- **dtype.** fp32 doubles a bandwidth-bound workload; fp16 NaNs in T5-XXL; bf16 is
  correct but emulated on M1, so correct rather than fast. Set
  `PYTORCH_ENABLE_MPS_FALLBACK=1` for op gaps.
- **Residency and memory.** Hold the model across the per-episode loop.
  `torch.mps.empty_cache()` between images — the MPS allocator does not return
  memory to the OS. Do **not** use `enable_model_cpu_offload`: on unified memory
  it is a memcpy within the same DRAM, pure cost. If using FLUX, encode all N
  prompts up front, then free the text encoders before looping.
- **Fixed resolution.** MPSGraph recompiles per unique shape.
- **Weights location.** Configurable cache dir, never `data/`, so the CI-parity
  guard stays satisfied.

### Phase 3 — selection and fallback (~half a day)

A setting choosing Imagen, local, or the existing placeholder renderer, defaulting
to Imagen — read where `media.media_utils.resolve_image_generator` is called, so
the choice is made once per run at the composition root and nothing downstream
branches. The `b6fde06` lesson applies directly: missing `diffusers`, absent
weights, insufficient memory and an MPS failure are four causes and each should
degrade with its reason logged. `59fd32d` supplies the pattern as well as the
lesson: an unbuildable generator becomes an `UnavailableImageGenerator` carrying
the reason, which re-raises per frame into the existing placeholder branch, so a
local backend that cannot start degrades exactly like a missing API key.

**Add a fifth: swapping away from Imagen removes its content filtering.**
FluxPipeline ships no safety checker, and this pipeline feeds it text derived from
scraped transcripts. That is a deliberate decision, not an implementation detail.

### Phase 4 — measure it (~1 day, not half)

Per-episode timing is nearly free; **per-image timing is not instrumented** —
`docs/operations.md` lists it under known unmeasured dimensions, and
`image_generation` is one timer for all scenes. Phase 4 has to add that
instrumentation, and must separate cold from warm, since the first image carries
model load plus graph compilation.

## Constraints

- CI must not download tens of GB; the parity guard already forces offline mode.
- `make demo` must keep working with no model present.
- `requirements-demo.txt` must not grow. It has in fact shrunk: `3005fc4`
  dropped the `google-genai` pin, which was only there because
  `agents/video_agent.py` imported it unguarded at module scope.
- `diffusers` and `accelerate` are unpinned and absent; FluxPipeline needs
  diffusers ≥0.30, and the T5 tokenizer wants `sentencepiece`, which is not in
  `requirements.txt`.
- First-run download is tens of GB. "Download died at 22 GB" is a likelier failure
  than "insufficient memory"; use `allow_patterns` or a naive snapshot pulls the
  single-file weights too.

## On prompts

Prompts should stay with original scene description — what happens in a shot —
rather than naming characters, which is what the existing style-prompt
construction already does. Running inference locally changes who hosts the
compute, not the derivative-work question that `docs/portfolio-refinement.md`
records as open.

## Honest assessment

The cost saving is secondary and the "no API key needed" claim was false. What
this actually buys is a pluggable backend, a measured comparison between two real
implementations, and images that cost nothing at the margin.

Whether that is worth two or three days on a portfolio piece is a real question.
Phase 1 was worth doing regardless, and has been done, so what is left is two
days rather than two and a half. Phases 2–4 are a weekend project that produces
a good story **only if Phase 4's measurement actually happens** — without it, this
is a second code path with no evidence attached, which is the pattern this repo
spent forty commits removing.
