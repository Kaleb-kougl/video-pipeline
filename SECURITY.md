# Security

## Reporting

Email **kalebkougl@gmail.com** with "SECURITY" in the subject. If it is not
sensitive, a GitHub issue is fine and faster.

This is a single-maintainer project with **no published release and no
versioned distribution**, so there is nothing deployed to report a vulnerability
*against*. What is worth reporting is a defect in this source tree that would
harm someone who runs it: a credential leak path, a command or path injection in
the CLI or the scrapers, or an unsafe deserialization. Expect a reply within a
week. There is no bounty and no formal disclosure timeline.

## What this project handles that is worth knowing about

### Live third-party credentials in `.env`

`GOOGLE_API_KEY` is a real, billable Google AI Studio key, and optionally
`LANGSMITH_API_KEY`. They are read from `.env` at the repository root.

`.env` is gitignored (`.gitignore` line 26) and is not tracked — only
`.env.example`, which ships empty values, is. **Verify this before your first
commit** if you have edited the ignore file:

```bash
git check-ignore -v .env      # must print the .gitignore rule
git ls-files | grep '\.env'   # must print .env.example and nothing else
```

Two related things to know: `make eval` explicitly unsets `LANGSMITH_API_KEY`
and forces tracing off before importing LangChain, because an "offline" eval was
otherwise opening connections to `api.smith.langchain.com`. And there is no
secret scanning in CI — a key committed here would only be caught by review.

### The pipeline scrapes third-party sites

Transcript discovery fetches pages from sites the project does not own. The
legal position on scraping is unsettled and jurisdiction-dependent, and this
project makes no claim that any particular fetch is permitted. If you run it:
you are the one making the request, the terms of service of the target site
apply to you, and rate limiting is your responsibility. The scrapers back off
between requests but are not polite by any formal standard, and they do not read
`robots.txt`.

The live-network test suites hit these sites for real. They are deselected by
default for exactly this reason; see [CONTRIBUTING.md](CONTRIBUTING.md#tests).

### Generated media derives from copyrighted source material

Summaries, narration and frames are produced from transcripts and descriptions
of copyrighted television. The MIT license on this repository covers **the
code** and nothing else. It says nothing about the output, which may be
derivative of material neither this project nor you have rights to. Generated
output directories are gitignored, so nothing derived is checked in — that is a
hygiene measure, not a legal clearance. Do not publish or monetize output
without deciding that question for yourself.

### Untrusted input reaches a model and a renderer

Scraped page content is fed to an LLM and its output drives image prompts and
file paths. Prompt injection from a scraped page is a plausible attack this
project does not defend against. Run it against shows you chose, not against
arbitrary URLs.

## Not in scope

Dependency CVEs reported by a scanner, with no path to exploitation through this
code. Dependencies are pinned in `requirements.txt` and updated when something
needs updating; a bare advisory ID is not a report.
