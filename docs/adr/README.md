# Architecture decision records

Short records of the decisions that shaped this repository: the context, what was
decided, and the downside accepted along with it.

They were extracted from commit messages, which is where the reasoning was
originally argued. Each ADR names its commits, so `git show <sha>` is the primary
source and these are the index.

| # | Decision | Status |
|---|---|---|
| [0001](0001-deterministic-eval-rubric.md) | Score generation with a deterministic rubric, not an LLM judge | Accepted |
| [0002](0002-additive-dependency-injection.md) | Inject collaborators additively, with keyword-only `None` defaults | Accepted |
| [0003](0003-scoped-typing-beachhead.md) | Make `core.*` a typing beachhead instead of typing everything | Accepted |
| [0004](0004-delete-rather-than-repair.md) | Delete code that silently does nothing, rather than repair or stub it | Accepted |
| [0005](0005-measure-never-estimate.md) | Report measurements or `null`, never a plausible default | Accepted |
| [0006](0006-async-unresolved.md) | What to do about `async` | **Proposed / open** |

## Format

Context / Decision / Consequences, where **Consequences names the cost that was
accepted**, not just the benefit. An ADR that only lists upsides is marketing.
Where the decision would now be made differently, the record says so rather than
being quietly superseded.

If you read one: [0001](0001-deterministic-eval-rubric.md). The eval gate is the
most load-bearing thing in the repo and it has a hole in it that is worth
understanding before you trust a score.
