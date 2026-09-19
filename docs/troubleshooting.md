# Troubleshooting

Failure modes that have actually happened, each as **symptom → cause → action**.
Every one was checked against the source at `689c889`; where the behaviour is
surprising the file and function that produces it is named so you can confirm it
yourself.

<!-- verified: 689c889 sources: main.py, agents/transcript_source_agent.py, agents/character_analysis_agent.py, agents/workflow_orchestrator.py, media/media_utils.py, pyproject.toml -->

For normal operation see [runbook.md](runbook.md).

---

## Discovery and sources

### "Found no transcript sources" — but was anything actually searched?

**Symptom.** `discover-sources` or a `--full` run reports few or no sources, or
the log says `Web-search leg UNAVAILABLE`.

**Cause.** The web-search leg is a scrape of `google.com`, which blocks scripted
clients. `TranscriptSourceDiscoveryAgent._search_with_google` therefore raises
`WebSearchUnavailable` — never returns `[]` — for a failed request, a non-200,
a `/sorry/` or captcha interstitial, and markup with no `/url?q=` links. The
distinction is load-bearing: an empty list from a search that *ran* means "not
out there"; an empty list from a search that *did not run* means nothing at all.

**Action.** Read `last_web_search_status` (also in `last_discovery_report`),
which is one of four values:

| Value | Meaning |
|---|---|
| `disabled` | The leg is opt-in and was not enabled. No web search happened |
| `not_run` | Discovery has not reached it, or no query completed |
| `unavailable` | Google refused or changed shape. **Nothing was learned** |
| `ok` | At least one query completed, so an empty list really is "found nothing" |

The leg is **off by default** (`TranscriptSourceDiscoveryAgent(enable_web_search=False)`)
because scraping Google fails in the field; the known-pattern search over Fandom
wikis and transcript databases runs regardless. Opt in only if you accept that
it may be blocked:

```python
from agents.transcript_source_agent import TranscriptSourceDiscoveryAgent

agent = TranscriptSourceDiscoveryAgent(enable_web_search=True)
sources = agent.discover_sources_for_show("My Hero Academia", season=1)
print(agent.last_web_search_status, len(sources))
```

Separately, `UNSEARCHED_SOURCES` (MyAnimeList, AniDB, Anime News Network,
Crunchyroll) are never queried — no client exists. Their absence means "not
checked".

### `process-season` prints "No run was started"

**Symptom.** Nothing happens; no `runs` row is created.

**Cause.** `EpisodeConfigs.get_season_episodes` returned `None`, so the season
length is unknown and `process_season_batch` returns `None` before touching the
database. `config/settings.py` knows three shows: *My Hero Academia* (seasons
1–7), *Attack on Titan* (1–4) and *Frieren: Beyond Journey's End* (1). This is
deliberate; the code used to invent a length.

**Action.** Add the show to `EpisodeConfigs.DEFAULT_CONFIGS`, or drive
individual episodes with `process-episode`, which takes the episode number from
you.

---

## Environment

### Every CLI command dies with `ImportError: ChromaDB not available`

**Symptom.** `python main.py stats` — or any other subcommand — raises before it
does anything.

**Cause.** `AnimeVideoGenerator.__init__` catches the `ImportError` from
`CharacterAnalysisAgent()` and sets `self.character_agent = None`, then passes
that `None` straight to `WorkflowOrchestrator(character_analysis_agent=None)` —
whose `None` branch constructs `CharacterAnalysisAgent()` again, uncaught.
Verified by forcing `agents.character_analysis_agent.CHROMA_AVAILABLE = False`
and constructing `AnimeVideoGenerator()`: it raises. The graceful degradation
the first `try` intends does not currently reach the orchestrator.

**Action.** Install the extras — `pip install -r requirements.txt`, or
`pip install -r requirements-vector.txt` for ChromaDB and sentence-transformers
alone. `make install-demo` and the Docker image deliberately omit them (over 1 GB
of wheels), which is why `make demo` patches `CharacterAnalysisAgent` out
entirely and works without them.

### `make test` says a dev tool is missing

**Symptom.** `ERROR: 'pytest' is not installed in .venv`.

**Cause.** The venv was built from `requirements-demo.txt`, which omits the dev
tooling on purpose.

**Action.** `make install`. (The bare `No module named pytest` this replaced
told a newcomer nothing.)

### The venv exists but has no interpreter

**Symptom.** `make demo` or `make install` fails with "no such file or
directory" for `.venv/bin/python`, or `.venv/bin/python` is a dangling symlink.

**Cause.** The `.venv` was built on another machine (or against a Python that
has since been upgraded or removed). A plain `python -m venv .venv` will not
repoint those symlinks, so the bootstrap "succeeds" and still has no
interpreter.

**Action.** Nothing — the `$(BIN)/python` bootstrap rule in the `Makefile` now
uses `venv --clear`, which recreates the directory. If you are not going through
`make`, delete `.venv` and rebuild it.

### Wheels will not install

**Symptom.** pip fails building `pydantic-core`, `numpy` or `opencv`, or torch
has no candidate.

**Cause.** A Python outside 3.11–3.12. 3.9/3.10 fail on numpy and 3.14 has no
torch wheels.

**Action.** The `Makefile` checks this before creating a venv and tells you what
to do:

```bash
make demo PYTHON=python3.12
make docker-demo          # skip the host toolchain entirely
```

### ffmpeg

**Symptom.** The `video_encode` stage fails, or MoviePy cannot find an
executable.

**Cause.** MoviePy shells out to ffmpeg. The binary normally used is the static
build inside the pinned `imageio-ffmpeg` wheel, so a plain install already has
one; the Docker image symlinks it onto `PATH` and sets `FFMPEG_BINARY`
explicitly.

**Action.** Run `make demo` first. Its first step renders the branding intro
clip through a real MoviePy encode specifically so that a broken ffmpeg fails
there, in two seconds, rather than at the end of a paid run. If the demo
renders, ffmpeg is fine.

### A full run fails at `video_encode` with a missing intro clip

**Symptom.** A production `--full` run gets through images and audio, then dies
opening `<show>/tldr_mha_intro.mp4`.

**Cause.** `mp4_file_enhanced` opens that branding clip unconditionally
(`media/media_utils.py`). In production it is a hand-made asset; no binary is
committed to the repo. `scripts/demo.py::render_branding_intro` generates one
for the demo only.

**Action.** Put an MP4 at `<show name>/tldr_mha_intro.mp4` relative to the
working directory before a full run.

---

## Paid path

### Quota exhaustion and rate limiting

**Symptom.** A season batch keeps going but episodes land as `failed`, with a
quota or rate-limit message in `last_error`.

**Cause.** `process_episode_by_numbers` wraps everything in `except Exception`
and returns `ProcessingResult(success=False, error=str(e))`; the batch then
records `EpisodeStatus.FAILED` with that string and moves to the next episode.
Nothing backs off across episodes beyond the 2–5 s politeness sleep, and
`utils/retry.py` retries HTTP only — not the model client.

**Action.** Read the reasons, then resume once quota is back:

```bash
python main.py stats --run <run_id>
python main.py process-season "My Hero Academia" 1 --full --resume
```

Failed episodes are retried; succeeded ones are not paid for again.

### Images are captioned title cards and the audio is silent

**Symptom.** The MP4 renders, but the frames are placeholders and there is no
narration. `🖼️ Using FREE PLACEHOLDER IMAGE` / `🎤 Using FREE SILENT AUDIO` in
the output.

**Cause.** `create_image` and `wave_file` catch every exception and fall back.
Three cases are distinguished in the printed message: no `GOOGLE_API_KEY`, a
`billed users` / `INVALID_ARGUMENT` response (Imagen and Gemini TTS require a
billing-enabled project), or any other failure.

**Action.** Read the printed line — it says which. Note the pipeline still
reports the episode as **succeeded**: the fallback is a deliberate degradation,
not a failure, so the run's `succeeded` count is not evidence that real artwork
or narration was produced.

### `--format tiktok` (or any non-standard format) produces no file

**Symptom.** `⚠️ tiktok export SKIPPED - platform export is not implemented.`

**Cause.** By design. Every exporter in `media/format_exporters/` declares real
constraints but its `export_video()` raises `NotImplementedError`.
`export_video_format` catches it and returns
`{"success": False, "status": "skipped_not_implemented", "output_path": None}`.
The database then records `export_format: "standard"` with the request kept
separately in `requested_export_format`, so no row claims a file that does not
exist — the fix in `bf53dd6`.

**Action.** Use `--format standard`. Nothing is broken; the stage is
unimplemented and says so.

---

## Tests

### The test suite hangs

**Symptom.** `pytest` sits on a network-facing module, or a test times out at
120 s.

**Cause.** Eight modules perform live network I/O and are marked
`pytestmark = pytest.mark.network`:

```
tests/test_agents_fixed.py            tests/test_fandom_search.py
tests/test_complete_discovery.py      tests/test_season_processing.py
tests/test_complex_shows.py           tests/test_transcript_agent.py
tests/test_transcript_source_agent.py tests/test_video_length_integration.py
```

`addopts` in `pyproject.toml` carries `-m 'not network'` and `--timeout=120`, so
`make test` never runs them.

**Action.** If you ran them on purpose, expect scraping latency and live-site
flakiness. If you did not, you overrode `-m`; drop the override. A new module
that touches the network gets the marker — and if you add one to the regression
manifest, `tests/test_regression_suite.py` fails, because a network-marked
module is deselected by a default run and so guards nothing.
