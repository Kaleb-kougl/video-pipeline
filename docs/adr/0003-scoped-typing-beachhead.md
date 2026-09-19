# ADR 0003 — Make `core.*` a typing beachhead instead of typing everything

**Status:** Accepted · **Date:** 2026-09-18 · **Commit:** `438a58c`

## Context

`pyproject.toml` configured black, isort and mypy with
`disallow_untyped_defs = true`, and nothing ran any of them. It was aspirational
config: applying it globally would have failed on **47 functions** immediately, so
the committed configuration could never have passed. Config that cannot pass is
worse than no config, because it reads as a standard that is being met.

## Decision

Scope the strictness to where it can actually hold. mypy runs with strict
`disallow_untyped_defs` **only** over `core.*`, with a lenient global default —
21 errors to 0. ruff replaced black + flake8 + isort across the whole tree
(1,531 findings to 0).

Where an exclusion was unavoidable it is **named, not narrowed**:
`core.metadata_schemas` and `core.visual_coherence_manager` sit behind
`ignore_errors` with a comment listing the five real type bugs behind the
exclusion. `tests/` is excluded from ruff entirely (300 findings) and that is
stated rather than hidden. Ignores carry `FOLLOW-UP` comments.

CI runs a fast dependency-free lint job and a test matrix on 3.11 and 3.12,
verified green locally first — a workflow that is red on its first push is worse
than no workflow.

## Consequences

Good: the gate is honest. `make typecheck` passing means something narrow and
true, rather than something broad and false. New code in `core/` cannot land
untyped, so the typed surface ratchets outward instead of being declared.

Accepted costs:

- **`agents/`, `main.py` and `utils/` are unchecked**, which is where most of the
  bugs the refactor found actually lived. The beachhead was chosen because it was
  cheap, not because it was where the risk was.
- **Two `core` modules are excluded, hiding five known real type errors** —
  `create()` overrides that violate the base signature, a `cv2.kmeans` overload
  mismatch, and an `Optional[str]` used as a dict key. These need fixes, not
  annotations, and they are still open.

## What I would do differently

`ignore_errors = true` on a module is a blunt instrument: it suppresses the five
known errors *and* every error added to those files afterwards. A per-error
ratchet — a baseline file of accepted errors that fails when the count grows —
would have given the same green build while preventing new drift. I would also
scope the beachhead by *risk* rather than by convenience, which would have
pointed at `agents/` first.
