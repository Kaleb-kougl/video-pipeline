# Releasing

Short by design. One maintainer, no published package, no downstream consumers.
Everything below exists because the repository already contradicted itself about
its own version, not because a solo project needs release engineering.

## What the version number means here

Nothing is installed from an index and nobody's build breaks when this changes,
so the version is not a compatibility promise to a third party. It is a summary
for the next person to read the changelog — usually the author six months later,
or a reviewer trying to work out what state the project is in.

It still follows semver, because the useful part is being forced to ask "did I
remove something" before shipping.

| Bump | Trigger |
|---|---|
| Major | Documented surface removed or renamed, a command's behaviour changes in a way that would surprise an existing script, or the SQLite schema migrates |
| Minor | New capability, nothing existing broken |
| Patch | Fixes only |

"Documented surface" means the subcommands in [cli.md](cli.md), the constructors
and methods described in `docs/` and the README, and the on-disk schema in
[data-model.md](data-model.md). Nothing else carries a stability contract.
Internals change without notice, and that is stated here rather than implied.

## Why the current version is 3.0.0

`pyproject.toml` declared `1.0.0` while the changelog's newest entry was 2.1.0.
Both cannot be right, and they were resolved in the changelog's favour:

- The changelog is the historical record a reader actually sees. The 2.x entries
  describe work that shipped. The `pyproject.toml` field was set once and never
  maintained — it was stale metadata, not a competing claim.
- Renumbering down to a pre-1.0 series would have been the more honest
  description of the project's stability, but it would contradict a published
  record of 2.0.0 and 2.1.0 for no gain. You cannot un-ship a version number.
- From 2.1.0, the refactor is unambiguously a major bump, not a patch: a public
  class and four source checkers were deleted, platform export now raises where
  it used to return a success dict, discovery returns nothing where it used to
  return another show's transcript, `--target-minutes` changes generated output,
  and the database migrates on open.

So: 3.0.0, and the number lives in exactly one place, the `version` field in
`pyproject.toml`.

## Deprecation policy

The pre-1.0 regime — delete freely, explain afterwards — does not apply. This
project has been numbered above 1.0 since before the refactor that deleted
`ParallelImageGenerator` and the four transcript source checkers, so those
removals were already outside it. They are recorded as breaking in the 3.0.0
changelog entry rather than retroactively justified.

From 3.0.0 onward:

- Removing documented surface requires a major bump and an entry under
  **Removed** that names the replacement, or states plainly that there is none.
- **No deprecation cycle is required while there are no consumers.** A
  `DeprecationWarning` whose only observer is the person who raised it is
  ceremony. The major bump plus the changelog entry is the entire signal, and
  that is a deliberate choice, not an oversight.
- **If a consumer ever appears** — a second contributor, an installed copy
  elsewhere, a published package — the rule changes to one minor release
  carrying a `DeprecationWarning` and a documented replacement before any
  removal. That is the line at which the cheap regime stops being defensible.

## Hand-written changelog, not generated

The commit messages here are detailed and conventional-commit shaped, so
generating the changelog from them is tempting. It is still the wrong trade.

A generator emits subject lines, and the subject is the least informative part
of every commit in this history — the reasoning is in the body. It would also
emit one bullet per commit, including entries like "add the season-length probe
tests missed in an earlier commit", which is meaningful to the author and noise
to a reader. The 3.0.0 entry covers 32 commits in roughly 40 grouped bullets
organised by what changed for a user, which is not a transformation any
subject-line parser can perform.

The real cost of hand-writing is that it gets forgotten. That is mitigated by
making it a step in the checklist below rather than by automating away the
judgement.

## Cutting a release

1. `git log --oneline <last tag>..HEAD` and read the bodies, not the subjects.
   There are no tags yet, so the first release reads the whole history.
2. Decide the bump from the table above. If anything documented was removed or
   changed behaviour, it is major.
3. Move the `Unreleased` content in `CHANGELOG.md` into a dated entry, grouped
   Added / Changed / Deprecated / Removed / Fixed, with breaking items marked.
   Group by what changed for a reader, not by commit.
4. Update `version` in `pyproject.toml`. It is the only place the number lives —
   there is no `__version__` and no `--version` flag, deliberately, because a
   second copy is a second thing to get wrong.
5. `make lint`, `make typecheck`, `make test`, `make eval`, `make demo`.
6. Commit, then `git tag -a v<version> -m "v<version>"`.

## Deliberately not done

- **No release automation.** No version-bump tool, no tag-triggered workflow, no
  artifact publishing. There is nothing to publish to and one person to remember.
- **No `__version__` attribute or `--version` flag.** Both would have to be kept
  in step with `pyproject.toml` by hand; the contradiction this document exists
  to fix was caused by exactly that kind of duplication.
- **No release branches or backports.** There is one line of history.
