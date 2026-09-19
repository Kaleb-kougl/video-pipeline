## What and why

<!-- What changed, and what problem it solves. The "why" matters more: the ADRs
in docs/adr/ were extracted from commit messages, so this text is the record. -->

## How it was verified

<!-- Commands run and what they printed. Not "tested locally". If something
could not be verified, say which and why - see ADR 0005. -->

## Checklist

- [ ] `make lint` passes
- [ ] `make typecheck` passes (strict over `core.*`; new code in `core/` is annotated)
- [ ] `make test` passes
- [ ] `make eval` passes, and if a prompt changed, the before/after aggregate is in this PR
- [ ] **Documentation updated in this PR, or confirmed that none needed changing.**
      Docs drifting from code is this repo's recurring failure — it has been
      caught five times. `tests/test_documentation.py` will fail the build if
      the README links to a missing file, exceeds 400 lines, or if the README
      or `docs/cli.md` names a command `main.py` does not register (or omits
      one it does). It cannot check prose, which is what this box is for.
- [ ] Commit messages follow conventional commits (`feat:`, `fix:`, `docs:`,
      `test:`, `refactor:`, `style:`, `build:`)
- [ ] No new network calls in the default test path — live-network tests carry
      `pytestmark = pytest.mark.network`
- [ ] No credentials, keys or generated media in the diff

## Cost accepted

<!-- What this makes worse, or what it leaves undone. A PR with no downside is
usually one where the downside has not been found yet. Delete if genuinely
none. -->
