# Transcript Discovery Agent - Usage Guide

> **Audited 2026-09-19 against the current source.** The orchestrator example was
> subscripting a Pydantic model, the custom-source example used a schema the
> parser does not read, and the "15+ URL variations" claim was wrong — slug counts
> below are measured. Signatures re-checked against `agents/transcript_agent.py`
> and `agents/workflow_orchestrator.py`.

## Overview

The `TranscriptDiscoveryAgent` is a powerful tool that automatically searches multiple public sources to find parsable transcripts for any anime episode. It's designed to be robust, respectful to servers, and capable of handling various anime shows and episode formats.

## Key Features

### 🔍 **Multi-Source Search**
- **SubsLikeScript**: Primary transcript source with comprehensive anime coverage
- **Transcripts Wiki**: Fandom-based transcript collections
- **Anime Transcripts**: Specialized anime transcript repositories

### 🎯 **Intelligent URL Generation**
- **Enhanced Pattern Generation**: Handles complex show names with punctuation, subtitles, and special characters
- **Predefined Mappings**: 13 shows have hand-written slugs in `agent.show_mappings`
- **Fallback Generation**: For any other show, slugs are derived from the name:
  - Standard formats (dashes, underscores, concatenated, title case)
  - Subtitle parsing ("Title: Subtitle" → the full name plus each half)
  - Acronym generation (first letters of words, lower and upper case)
  - Number conversion (`86` → `8six`, `eight6`, `eighty-6`, …)
  - Common word filtering (drops "the", "a", "on", "and", …)

**`get_show_slugs()` short-circuits on the predefined mappings.** A show listed in
`show_mappings` returns only its mapped slugs; the variation machinery runs only
for shows that are *not* listed. Measured against the current source:

| Show | In `show_mappings`? | Slugs returned |
|---|---|---|
| `My Hero Academia` | yes | 4 — `my-hero-academia`, `boku-no-hero-academia`, `mha`, `My_Hero_Academia-5626028` |
| `Frieren: Beyond Journey's End` | yes | 2 — `Frieren_Beyond_Journeys_End-22248376`, `frieren-beyond-journeys-end` |
| `KonoSuba: God's Blessing on This Wonderful World!` | no | 11, including `konosuba`, `kgbotww`, `KGBOTWW` |
| `Re:Zero - Starting Life in Another World` | no | 13, including `r-sliaw`, `rezero-startinglifeinanotherworld` |
| `86: Eighty-Six` | no | 16, including `8e`, `eight6-eighty-six`, `86-eighty-6` |

Reproduce with:

```python
from agents.transcript_agent import TranscriptDiscoveryAgent

agent = TranscriptDiscoveryAgent()
print(agent.get_show_slugs("86: Eighty-Six"))
```

### ⭐ **Content Quality Assessment**
- Validates transcript length (minimum character count)
- Detects dialogue patterns (colons, quotes, speech indicators)
- Identifies narrative structure elements
- Assesses character name density

### 🔒 **Respectful Scraping**
- Random delays between requests (1-3 seconds)
- Exponential backoff on failures
- Proper User-Agent headers
- Retry logic with limits

## Basic Usage

### Simple Episode Search

`find_episode_transcript()` is marked **deprecated** in the source: it fuses
discovery and parsing into one call. New code should use the two-step form —
`EpisodeDiscoveryAgent.search_episode_enhanced()` to find a URL, then
`TranscriptDiscoveryAgent.parse_discovered_url(url, source_name)` to parse it.
The single-call form below still works and is what the CLI uses.

```python
from agents.transcript_agent import TranscriptDiscoveryAgent

# Initialize the agent
agent = TranscriptDiscoveryAgent()

# Find a transcript for a specific episode
result = agent.find_episode_transcript(
    show_name="My Hero Academia",
    season=1,
    episode=4,
    episode_title="Start Line",  # Optional, improves accuracy
)

if result:
    print(f"Found transcript from {result['source']}")
    print(f"Quality Score: {result['quality_score']:.2f}")
    print(f"Content Length: {result['content_length']} characters")
    print(f"URL: {result['url']}")

    # Access the actual transcript
    transcript = result["transcript"]
    title = result["title"]
else:
    print("No transcript found")
```

### Batch Processing with the Orchestrator

`WorkflowOrchestrator.process_episode_complete()` is a coroutine and takes the
show name first. It returns a `ProcessingResult` (`core/schemas.py`), not a
plain dict.

```python
import asyncio
from agents.workflow_orchestrator import WorkflowOrchestrator

# Initialize the complete system
orchestrator = WorkflowOrchestrator()

# Process a single episode (includes transcript discovery + AI processing)
result = asyncio.run(
    orchestrator.process_episode_complete(
        show_name="Attack on Titan",
        season=1,
        episode=4,
        episode_title="Start Line",
    )
)

if result.success:
    episode_data = result.data  # dict | None
    source_info = result.source_info  # TranscriptResult | None

    print(f"Successfully processed {episode_data['show']}")
    if source_info is not None:
        print(f"Found via: {source_info.source}")
        print(f"Quality: {source_info.quality_score:.2f}")

    # Generated content is available
    youtube_transcript = episode_data["youtube_transcript"]
    plot_points = episode_data["plot_points"]
else:
    print(f"Failed: {result.error}")
```

`ProcessingResult` and `TranscriptResult` are Pydantic models, so their fields are
attributes (`result.success`), not keys. Only `result.data` is a plain `dict` and
is subscripted.

## Supported Anime Shows

### Pre-configured Shows (Higher Success Rate)
The 13 keys of `agent.show_mappings`. These bypass slug generation entirely and
use their hand-written patterns:

- **My Hero Academia** / Boku no Hero Academia
- **Attack on Titan** / Shingeki no Kyojin  
- **Demon Slayer** / Kimetsu no Yaiba
- **One Piece**
- **Naruto** / Naruto Shippuden
- **Dragon Ball** series
- **Death Note**
- **Fullmetal Alchemist**
- **Hunter x Hunter**
- **Tokyo Ghoul**
- **Jujutsu Kaisen**
- **Chainsaw Man**
- **Frieren: Beyond Journey's End**

### Other Shows
The agent can attempt to find transcripts for any anime show by:
1. Generating URL slugs from the show name
2. Trying multiple formatting patterns
3. Searching across all configured sources

## Advanced Usage

### Custom Source Configuration

```python
agent = TranscriptDiscoveryAgent()

# Add a custom source. Entries in `agent.sources` must match the shape the
# parser reads: `base_url`, a `selectors` dict whose four keys each hold a list
# of CSS selectors tried in order, and `quality_indicators`.
agent.sources["custom_site"] = {
    "base_url": "https://example-transcripts.com",
    "selectors": {
        "transcript": [".transcript-text", "main .content"],
        "title": ["h1.episode-title", "h1", "title"],
        "search_results": ['a[href*="/episode/"]'],
        "metadata": [".episode-info"],
    },
    "quality_indicators": ["dialogue", "episode transcript"],
}

# Search specific source only
result = agent.search_source(
    source_name="subslikescript", show_name="Death Note", season=1, episode=1
)
```

### Quality Assessment Details

The quality score (0.0 - 1.0) is calculated based on:

- **Length** (0.2-0.3 points): Longer transcripts score higher
- **Dialogue Indicators** (0.3 points): Presence of colons, quotes, speech patterns
- **Narrative Structure** (0.2 points): Scene transitions, directional cues
- **Character Names** (0.2 points): Density of capitalized words (character names)

### Error Handling

```python
try:
    result = agent.find_episode_transcript("Rare Anime", 1, 1)
    if result:
        # Process successful result
        process_transcript(result)
    else:
        # Handle no transcript found
        print("Try checking episode number or show name")
except Exception as e:
    # Handle network or parsing errors
    print(f"Search failed: {e}")
```

## Testing

### Run the Test Script

```bash
# Test a single episode
python tests/test_transcript_agent.py --mode single

# Run batch tests on multiple shows
python tests/test_transcript_agent.py --mode batch

# Show all supported anime shows
python tests/test_transcript_agent.py --mode shows
```

### Custom Tests

```python
# Test specific episodes
test_cases = [
    ("Spirited Away", 1, 1, None),
    ("Princess Mononoke", 1, 1, None),
    ("Your Name", 1, 1, None),
]

for show, season, episode, title in test_cases:
    result = agent.find_episode_transcript(show, season, episode, title)
    print(f"{show}: {'✅' if result else '❌'}")
```

## Testing Complex Show Names

### Enhanced URL Generation Test

```bash
# Test URL generation for complex show names
python tests/test_complex_shows.py --mode generation

# Test dynamic pattern discovery
python tests/test_complex_shows.py --mode discovery  

# Test actual searches (limited to be respectful)
python tests/test_complex_shows.py --mode search

# Run all tests
python tests/test_complex_shows.py --mode all
```

### Examples of Complex Shows Handled

The enhanced agent can now handle challenging show names like:

```python
complex_shows = [
    "Frieren: Beyond Journey's End",
    "86: Eighty-Six",
    "Re:Zero - Starting Life in Another World",
    "That Time I Got Reincarnated as a Slime",
    "Is It Wrong to Try to Pick Up Girls in a Dungeon?",
    "KonoSuba: God's Blessing on This Wonderful World!",
    "Rascal Does Not Dream of Bunny Girl Senpai",
]

agent = TranscriptDiscoveryAgent()
for show in complex_shows:
    slugs = agent.get_show_slugs(show)
    print(f"{show}: {len(slugs)} URL variations generated")
```

### A note on `use_discovery`

`find_episode_transcript()` accepts a `use_discovery` parameter, but **it is
never read** — the body iterates `self.sources` unconditionally. Its own
docstring marks it "kept for compatibility". Passing it changes nothing:

```python
# `use_discovery` has no effect; these two calls are identical.
result = agent.find_episode_transcript("Frieren: Beyond Journey's End", 1, 1)

if result:
    print(f"Found on {result['source']}")
else:
    print("No transcript found on any of the three sources")
```

Every search fans out across all three configured sources and
`_select_best_result()` picks the highest-scoring hit. Returning `None` means no
source yielded a parsable transcript — which, after `d2ac52b`, is reported
honestly rather than being papered over with another show's transcript.
