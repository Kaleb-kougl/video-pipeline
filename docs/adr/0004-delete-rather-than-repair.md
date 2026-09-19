# ADR 0004 — Delete code that silently does nothing, rather than repair or stub it

**Status:** Accepted · **Date:** 2026-09-18 · **Commits:** `7116567`, `d2ac52b`, `2971e15`

## Context

The audit kept finding the same shape: code that was wired in, looked
implemented, and did nothing — or worse, produced a plausible wrong answer. A
crash is a bug report. A feature that silently does nothing is a false claim that
survives review, and it poisons trust in the surrounding code.

## Decision

**When a component does not work and has no caller depending on its behaviour,
delete it and make the resulting gap explicit.** Repair only where a real caller
needs the behaviour today.

Applied three times:

- **`ParallelImageGenerator` (`7116567`).** 513 lines, zero production call
  sites. Broken at its only would-be integration point:
  `core/content_cache.py` called `image_generator.generate_image(prompt)`, a
  method the class never defined — one mismatch that produced 26 of the 33
  baseline failures. It also carried the worst pattern in the repo, production
  code branching on whether it was under test
  (`if hasattr(self.ai_client.models.generate_content, "return_value")`).
  A salvage assessment ran first: the prompt-consistency helper was already
  duplicated in three places, rate limiting is meaningless without a concurrent
  caller, the retry loop should become `tenacity`, and only the metrics block was
  unique — and it measured a batch pipeline that does not exist.

- **Placeholder source checkers (`d2ac52b`).** Four checkers for MyAnimeList,
  AniDB, Anime News Network and Crunchyroll were each a comment plus
  `return None  # Placeholder`, wired into the fan-out — so callers could not
  distinguish "checked, found nothing" from "never checked". The stubs and the
  fan-out step were deleted rather than converted into an extension point that
  raises inside a loop.

- **Dead configuration (`2971e15`).** `known_source_patterns` advertised
  `community_sites` and `streaming_platforms` that nothing ever iterated. Removed
  rather than wired up: the first duplicated `UNSEARCHED_SOURCES`, and the second
  are DRM video services hosting no transcripts, so crawling them would only add
  failing requests.

**A deletion must leave the gap visible.** `UNSEARCHED_SOURCES` names the removed
checkers, the docstring states that their absence means *not checked*, the
completion log says so, and `get_or_generate_image` raises a descriptive
`TypeError` naming the protocol instead of a bare `AttributeError` from deep in
the call.

## Consequences

Good: the test suite stopped lying (26 `AttributeError` failures disappeared with
the class), and the remaining code means what it says. Every deletion is
recoverable with `git show`, which is why importing the tree as-is in `5877d72`
mattered.

Accepted costs:

- **Capability is genuinely gone.** There is no parallel image path at all now.
  If a real concurrent caller appears, the retry/rate-limit/metrics work is
  rebuilt from git rather than extended in place.
- **Some users get fewer results.** Gating the legacy transcript fallback on
  `is_legacy_show()` means shows that previously "found" a URL now correctly find
  none. That is the honest answer, and it is still a regression in apparent
  coverage — the previous behaviour served a My Hero Academia transcript labelled
  as whatever show was requested.
- Deleting rather than stubbing forecloses the cheap "we'll fill it in later"
  path. That is the point, but it does mean the extension point has to be
  designed when it is needed rather than sketched now.
