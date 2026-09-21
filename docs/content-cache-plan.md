# ContentCache: do not wire it in as it stands

Assessed at `f22155f`; the two closing sections re-read at `59fd32d`, which
overtook them. **This document replaces a plan to integrate the cache. That plan
was wrong at its premise and is not worth building.**

## What the first version claimed

That `ContentCache` is fully built and unused, that adjacent episodes of the same
show request near-identical scenes, and that wiring it in would cut image spend.
Four phases, ~1.5 days.

The premise came from the README's description of the cache. The matching code
was never read. That is the same failure this repo has caught repeatedly —
trusting a document about the code instead of the code.

## What the code actually does

**Exact-hash hits cannot cross episodes.** `core/content_cache.py:447`:

<!-- docs-check: skip - quoted from the source to show the key's shape -->
```python
image_content = {"prompt": prompt, "episode_context": episode_context}
content_hash = self._generate_content_hash(image_content, ContentType.IMAGE)
```

The episode context is *inside the key*. Two episodes producing a byte-identical
prompt still hash differently, by construction. The saving the plan was built on
is unreachable through the hash path.

**The similarity path can cross episodes, and matches on boilerplate.**
Line 457 calls `find_similar_content({"prompt": prompt}, ...)`, dropping the
episode context. Scoring is `keyword * 0.7 + text * 0.3`, where keywords are the
intersection with a hardcoded 17-word vocabulary:

> anime, style, forest, village, training, battle, character, scene, background,
> lighting, color, ninja, magic, power, emotion, dramatic

Two things follow. First, `_create_enhanced_prompt` in
`core/visual_coherence_manager.py` appends constant text to every prompt —
"Create in consistent anime art style. Maintain visual consistency…" — so every
prompt contains *anime*, *style*, *character* and *scene* regardless of content.
Two unrelated scenes therefore intersect on that boilerplate and can reach a
keyword score of 1.0, which is 0.7 of 0.85 before any text comparison. Second,
prompts containing none of the 17 words score 0.0 and can never match, however
similar they are.

So the only path that can hit across episodes is the one that hits for the wrong
reason, and `village` and `ninja` in a supposedly general vocabulary show what it
was tuned against.

**The prompts are near-unique anyway.** The varying part of each prompt is a plot
point produced fresh by a nondeterministic model call per episode. Two episodes
will not emit byte-identical sentences.

## The honest conclusion

The realistic exact-hash hit rate across episodes is **zero**, not low. Wiring
the cache in as designed would take about a day and a half to instrument a
measurement of nothing.

Making it actually work is a different, larger job than "wire it in":

1. Remove `episode_context` from the hash key, or accept that hits are
   episode-scoped and find a saving that lives inside one episode.
2. Replace `_extract_visual_keywords` with something that is not a hardcoded
   vocabulary from one show — embeddings, or scene-noun extraction.
3. Re-tune the threshold against real output, since 0.85 means something
   different once scoring changes.
4. Only then measure a hit rate.

That is a genuine piece of work with a real payoff, and it should be scoped
honestly rather than hidden inside "integrate the existing cache".

## What to do instead, if the goal is lower image cost

~~**Cap the plot-point count.**~~ **Done, in `d58f1c7`.** This section used to
say that `create_images` fires once per plot point and nothing limits what the
model returns. `core.schemas.enforce_scene_cap` now truncates the list at the
point of use on both paid paths, bounded by `VideoConfig.max_scenes` (48 by
default and derived, not picked). Worst-case image spend is bounded and knowable
in advance — see
[operations.md](operations.md#what-a-run-costs-in-api-calls). Per-episode spend
is still variable *under* that ceiling, which remains the largest single source
of cost variance, so a cache that actually hit would still be worth something;
it is the hit rate, not the ceiling, that this document says is zero.

## What stays true from the first version — and what no longer does

**The seam analysis has been overtaken by the work it argued for.** It said
`create_image` constructs a Google client inline and the only implementation of
the generator interface is a fake in `tests/conftest.py`. Both were true at
`f22155f` and neither is now: `f2597bf` extracted
`core.protocols.ImageFileGenerator` with `media.media_utils.ImagenImageGenerator`
behind it, and `59fd32d` injected it in production — `create_images` forwards
one generator to every `create_image`, resolved once per run by
`WorkflowOrchestrator` and `main.py`. The claim that extracting the adapter was
worth doing on its own merits held up; it is simply no longer a prerequisite
anyone has to schedule.

**The correction that mattered most stays true, and is now load-bearing.** The
two seams have **different shapes**. The extracted one —
`generate_image(prompt, destination) -> str` in `core/protocols.py`, injectable
at `core/visual_coherence_manager.py:56` — returns a path. The content-cache
seam (`ContentCache.get_or_generate_image`, `core/content_cache.py:425`) calls
`generate_image(prompt)` and expects a **dict** payload back; its fake is
deliberately named `FakeImagePayloadSource` for exactly that reason. The
bytes-or-path decision was settled as *path*, and it was settled for the render
seam only. So wiring this cache in still means writing an adapter between two
interfaces that share a method name and nothing else — which is one more reason
the integration is not the small job the first version described.

## Why this document still exists

Deleting it would hide a real finding: a 730-line, well-tested, entirely unused
subsystem whose two lookup paths each defeat its stated purpose in a different
way. That is worth more as a written diagnosis than as a silently abandoned
branch.
