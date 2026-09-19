---
name: Feature
about: Something it should do and does not
labels: enhancement
---

**What should it do, and for whom?**

**What do you do today instead?**

**Why belongs here** — this project deletes code that does nothing rather than
keeping it around (see docs/adr/0004-delete-rather-than-repair.md), so a feature
needs a caller that will actually use it.

**Known gaps before you file:** platform export raises `NotImplementedError`,
`ContentCache` and `generate_consistent_image()` are built but unwired, and the
async question is open (docs/adr/0006-async-unresolved.md). If your request is
one of those, say so — that is a useful vote, not a duplicate.
