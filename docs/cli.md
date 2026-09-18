# CLI reference

Every command below is registered in `main.py` via `subparsers.add_parser(...)`.
There are 27 of them. Invoke them as `python main.py <command>` or, after
`pip install -e .`, as `anime-generator <command>`.

```bash
python main.py --help
python main.py <command> --help
```

## Conventions

| Flag | Unit | Values | Notes |
|---|---|---|---|
| `--duration`, `-d` | minutes | `5`-`15` | `create-season-summary` only; validated before the generator is constructed |
| `--format`, `-f` | string | `standard`, `youtube_shorts`, `tiktok`, `instagram_reels`, `twitter` | Only `standard` writes a file — see [Platform export](#platform-export) |
| `season`, `episode` | integer | `1`, `2`, ... | Positional |
| `--limit` | integer | default varies per command | |
| `--force` | flag | — | Reprocess even if output exists |

Show names are positional strings and should be quoted: `"My Hero Academia"`.

## Episode and season processing

| Command | Positional | Flags |
|---|---|---|
| `process-url` | `url` `show` | — |
| `process-episode` | `show` `season` `episode` | `--title`, `--full` |
| `process-season` | `show` `season` | `--start`, `--end`, `--full` |
| `create-season-summary` | `show` `season` | `--force`, `--duration/-d` (default `5`), `--format/-f` (default `standard`) |
| `view-season-summaries` | — | `--show` |
| `analyze-season` | `show` `season` | — |
| `summarize` | `show` `season` `episode` | — |
| `stats` | — | — |

Without `--full`, `process-episode` and `process-season` stop after transcript
discovery and persistence. `--full` runs content analysis, enrichment, image
generation and render.

```bash
python main.py process-episode "My Hero Academia" 1 4 --full
python main.py process-season "My Hero Academia" 1 --start 1 --end 5 --full
python main.py create-season-summary "My Hero Academia" 1 --duration 10
python main.py view-season-summaries --show "My Hero Academia"
python main.py stats
```

## Transcript discovery and sources

| Command | Positional | Flags |
|---|---|---|
| `test-transcript` | `show` `season` `episode` | — |
| `discover` | `show` | `--season` |
| `discover-sources` | `show` | `--season` |
| `evaluate-source` | `url` `show` | — |
| `recommend-sources` | `show` | `--season` |

`test-transcript` is the fastest way to check whether a show is reachable at all:
it runs discovery and prints the quality score without touching the LLM.

```bash
python main.py test-transcript "My Hero Academia" 1 4
python main.py discover "My Hero Academia" --season 1
python main.py discover-sources "Attack on Titan" --season 3
python main.py evaluate-source "https://example.com/transcript" "My Hero Academia"
python main.py recommend-sources "Demon Slayer" --season 1
```

## Quality

| Command | Positional | Flags |
|---|---|---|
| `analyze-quality` | `show` `season` `episode` | — |
| `validate-quality` | `show` `season` `episode` | `--stage` (`transcript`\|`content`\|`video`\|`discovery`\|`workflow`) |
| `quality-dashboard` | — | — |
| `quality-trends` | — | `--show`, `--days` (default `30`) |

```bash
python main.py validate-quality "My Hero Academia" 1 4 --stage transcript
python main.py quality-trends --show "My Hero Academia" --days 7
```

Thresholds live in `agents/quality_agents/quality_coordinator.py`.

## Vector search over episodes

Requires the optional extras in `requirements-vector.txt`.

| Command | Positional | Flags |
|---|---|---|
| `search-episodes` | `query` | `--limit` (default `10`), `--show`, `--season` |
| `similar-episodes` | `show` `season` `episode` | `--limit` (default `5`) |
| `index-episode` | `show` `season` `episode` | — |
| `vector-stats` | — | — |

```bash
python main.py index-episode "My Hero Academia" 1 4
python main.py search-episodes "character development" --show "My Hero Academia" --limit 5
python main.py similar-episodes "My Hero Academia" 1 4 --limit 3
```

## Character analysis

Requires the optional extras in `requirements-vector.txt`.

| Command | Positional | Flags |
|---|---|---|
| `analyze-characters` | `show` `season` `episode` | — |
| `similar-characters` | `character` | `--show`, `--limit` (default `5`) |
| `character-development` | `character` `show` | — |
| `character-relationships` | `character` | `--show` |
| `search-character-moments` | `query` | `--character`, `--show`, `--limit` (default `10`) |
| `character-stats` | — | — |

```bash
python main.py analyze-characters "My Hero Academia" 1 4
python main.py similar-characters "Deku" --show "My Hero Academia" --limit 3
python main.py character-development "Deku" "My Hero Academia"
python main.py search-character-moments "heroic moment" --character "Deku" --limit 5
```

Pass `--show` wherever it is offered. Vector collections are shared across shows
and `CharacterAnalysisAgent` refuses to write an entry without a show name — see
[architecture.md](architecture.md#show-identity-and-chromadb-metadata).

## Platform export

`--format` on `create-season-summary` selects an exporter in
`media/format_exporters/`. Every exporter declares real constraints (aspect
ratio, max duration, max file size) but `export_video()` raises
`NotImplementedError`; the caller catches it and returns
`{'success': False, 'status': 'skipped_not_implemented'}`. Only
`--format standard` produces a video file today.

## Utilities outside the CLI

Not subcommands — run them directly:

```bash
python scripts/migrate_metadata.py   # backfill ChromaDB show metadata
```
