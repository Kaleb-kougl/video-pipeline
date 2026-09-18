# Transcript Discovery Agent - Usage Guide

## Overview

The `TranscriptDiscoveryAgent` is a powerful tool that automatically searches multiple public sources to find parsable transcripts for any anime episode. It's designed to be robust, respectful to servers, and capable of handling various anime shows and episode formats.

## Key Features

### 🔍 **Multi-Source Search**
- **SubsLikeScript**: Primary transcript source with comprehensive anime coverage
- **Transcripts Wiki**: Fandom-based transcript collections
- **Anime Transcripts**: Specialized anime transcript repositories

### 🎯 **Intelligent URL Generation**
- **Enhanced Pattern Generation**: Handles complex show names with punctuation, subtitles, and special characters
- **Multi-format Slug Creation**: Generates 15+ URL variations per show including:
  - Standard formats (dashes, underscores, concatenated)
  - Subtitle parsing ("Title: Subtitle" → multiple patterns)
  - Acronym generation (first letters of words)
  - Number conversion (1 ↔ one, 2 ↔ two, etc.)
  - Common word filtering (removes "the", "a", "and", etc.)
- **Dynamic Pattern Discovery**: Tests URLs in real-time to find working patterns
- **Predefined Mappings**: Optimized patterns for 12+ popular anime shows
- **Fallback Generation**: Automatic slug creation for any show name

#### Example: "Frieren: Beyond Journey's End" generates:
- `frieren-beyond-journeys-end`
- `frieren-beyond-journey-end` 
- `frieren`
- `beyond-journeys-end`
- `fbje` (acronym)
- `Frieren-Beyond-Journeys-End` (title case)
- And 10+ more variations...

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

```python
from main import TranscriptDiscoveryAgent

# Initialize the agent
agent = TranscriptDiscoveryAgent()

# Find a transcript for a specific episode
result = agent.find_episode_transcript(
    show_name="My Hero Academia",
    season=1,
    episode=4,
    episode_title="Start Line"  # Optional, improves accuracy
)

if result:
    print(f"Found transcript from {result['source']}")
    print(f"Quality Score: {result['quality_score']:.2f}")
    print(f"Content Length: {result['content_length']} characters")
    print(f"URL: {result['url']}")
    
    # Access the actual transcript
    transcript = result['transcript']
    title = result['title']
else:
    print("No transcript found")
```

### Batch Processing with the Orchestrator

```python
from main import WorkflowOrchestrator

# Initialize the complete system
orchestrator = WorkflowOrchestrator()

# Process a single episode (includes transcript discovery + AI processing)
result = orchestrator.process_episode_by_numbers(
    season=1, 
    episode=4, 
    episode_title="Start Line",
    show_name="Attack on Titan"
)

if result['success']:
    episode_data = result['data']
    source_info = result['source_info']
    
    print(f"Successfully processed {episode_data['show']}")
    print(f"Found via: {source_info['source']}")
    print(f"Quality: {source_info['quality_score']:.2f}")
    
    # Generated content is available
    youtube_transcript = episode_data['youtube_transcript']
    plot_points = episode_data['plot_points']
```

## Supported Anime Shows

### Pre-configured Shows (Higher Success Rate)
The agent has optimized URL patterns for these popular anime:

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

### Other Shows
The agent can attempt to find transcripts for any anime show by:
1. Generating URL slugs from the show name
2. Trying multiple formatting patterns
3. Searching across all configured sources

## Advanced Usage

### Custom Source Configuration

```python
agent = TranscriptDiscoveryAgent()

# Add a custom source
agent.sources['custom_site'] = {
    'base_url': 'https://example-transcripts.com',
    'search_patterns': [
        '/{show_slug}/season-{season}/episode-{episode}',
        '/{show_slug}/s{season:02d}e{episode:02d}'
    ],
    'transcript_selector': '.transcript-text',
    'title_selector': 'h1.episode-title'
}

# Search specific source only
result = agent.search_source(
    source_name='subslikescript',
    show_name="Death Note",
    season=1,
    episode=1
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
python test_transcript_agent.py --mode single

# Run batch tests on multiple shows
python test_transcript_agent.py --mode batch

# Show all supported anime shows
python test_transcript_agent.py --mode shows
```

### Custom Tests

```python
# Test specific episodes
test_cases = [
    ("Spirited Away", 1, 1, None),
    ("Princess Mononoke", 1, 1, None),
    ("Your Name", 1, 1, None)
]

for show, season, episode, title in test_cases:
    result = agent.find_episode_transcript(show, season, episode, title)
    print(f"{show}: {'✅' if result else '❌'}")
```

## Testing Complex Show Names

### Enhanced URL Generation Test

```bash
# Test URL generation for complex show names
python test_complex_shows.py --mode generation

# Test dynamic pattern discovery
python test_complex_shows.py --mode discovery  

# Test actual searches (limited to be respectful)
python test_complex_shows.py --mode search

# Run all tests
python test_complex_shows.py --mode all
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
    "Rascal Does Not Dream of Bunny Girl Senpai"
]

agent = TranscriptDiscoveryAgent()
for show in complex_shows:
    slugs = agent.get_show_slugs(show)
    print(f"{show}: {len(slugs)} URL variations generated")
```

### Pattern Discovery in Action

```python
# The agent can dynamically discover working patterns
result = agent.find_episode_transcript(
    "Frieren: Beyond Journey's End", 
    season=1, 
    episode=1,
    use_discovery=True  # Enables dynamic discovery
)

if result:
    print(f"Found via dynamic discovery on {result['source']}")
else:
    print("Even enhanced discovery couldn't find this episode")
```
