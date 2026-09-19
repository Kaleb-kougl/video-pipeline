# Character Analysis with ChromaDB Vector Database

> **Audited 2026-09-19 against the current source.** Three Python examples and
> one CLI example were calling APIs that do not work as shown: all three query
> methods (`find_similar_characters`, `get_character_relationships`,
> `search_character_moments`) require `show_name`, and `_chunk_transcript()` was
> never defined. Every signature and command below was re-checked against
> `agents/character_analysis_agent.py` and `main.py`.

This document describes the advanced character analysis capabilities powered by ChromaDB vector database integration.

## 🎭 Overview

The Character Analysis Agent provides sophisticated character understanding through:

- **Vector-based Character Profiling**: Each character gets semantic embeddings based on their dialogue and personality
- **Relationship Mapping**: Automatic detection and analysis of character interactions
- **Character Development Tracking**: Evolution of personality traits across episodes
- **Semantic Search**: Find specific character moments using natural language queries
- **Cross-Show Lookup**: Find same-named characters in other series
  (`include_same_show=False`). Comparison *by personality* across shows is not
  implemented — see [Cross-Show Character Analysis](#cross-show-character-analysis).

> **Every query method requires `show_name`.** `find_similar_characters`,
> `get_character_relationships` and `search_character_moments` each raise
> `ValueError: show_name is required to prevent cross-show contamination` when it
> is missing. The three ChromaDB collections are shared across shows, so an
> unattributed query would read another show's rows.

## 🔧 Setup

### Dependencies

Install the required vector database dependencies:

```bash
pip install -r requirements-vector.txt
```

Key dependencies:
- `chromadb>=0.4.0` - Vector database for character embeddings
- `sentence-transformers>=2.2.0` - Semantic embeddings for character analysis
- `numpy>=1.21.0` - Numerical computations

### Initialization

The character analysis agent is automatically initialized when ChromaDB dependencies are available:

```python
from main import AnimeVideoGenerator

generator = AnimeVideoGenerator()
# Character analysis agent available at generator.character_agent
```

## 🎬 Features

### 1. Character Profile Analysis

Analyze characters in any episode to extract:
- Personality traits from dialogue patterns
- Dialogue frequency and patterns
- Character relationships within scenes
- Semantic embeddings for similarity comparison

```bash
# Analyze characters in a specific episode
python main.py analyze-characters "My Hero Academia" 1 1
```

Example output:
```
Character Analysis for My Hero Academia S1E1:
Total Characters: 4

📖 Izuku:
   Dialogue Count: 8
   Personality Traits: determined, kind, anxious
   Relationships: Bakugo, All Might
   First Appearance: S1E1

📖 Bakugo:
   Dialogue Count: 5
   Personality Traits: hot-tempered, confident, stubborn
   Relationships: Izuku
   First Appearance: S1E1
```

### 2. Character Similarity Search

Find characters with similar personality traits and dialogue patterns:

```bash
# Find characters similar to Izuku
python main.py similar-characters "Izuku" --show "My Hero Academia" --limit 5
```

The system uses semantic embeddings to compare:
- Personality trait patterns
- Dialogue style and content
- Character motivations and goals
- Behavioral patterns

### 3. Character Development Analysis

Track how characters evolve across episodes:

```bash
# Analyze character development
python main.py character-development "Izuku" "My Hero Academia"
```

Development analysis includes:
- **Dialogue Growth**: Changes in speaking frequency
- **Personality Evolution**: How traits develop over time
- **Development Score**: Overall character growth metric (0-1)
- **Arc Analysis**: Key development phases

Example output:
```
Character Development Analysis for Izuku:
Show: My Hero Academia
Total Episodes: 12
Development Score: 0.75

First Appearance: S1E1
Latest Appearance: S1E12

Personality Evolution:
  determined: increasing (early: 0.30, recent: 0.80)
  confident: increasing (early: 0.10, recent: 0.60)
  anxious: stable (early: 0.70, recent: 0.65)
```

### 4. Character Relationship Mapping

Analyze relationships between characters:

```bash
# Get relationship map for a character
python main.py character-relationships "Izuku" --show "My Hero Academia"
```

Relationship analysis includes:
- **Interaction Frequency**: How often characters interact
- **Relationship Strength**: Semantic similarity of interactions
- **Interaction Types**: dialogue, conflict, cooperation, etc.
- **Emotional Tone**: positive, negative, neutral, tense

Example output:
```
Character Relationships for Izuku:
Total Relationships: 5

🤝 Bakugo:
   Interaction Count: 15
   Relationship Strength: 0.75
   Primary Interaction: conflict
   Emotional Tone: tense
   Episodes: S1E1, S1E2, S1E4, S1E5, S1E8

🤝 All Might:
   Interaction Count: 8
   Relationship Strength: 0.85
   Primary Interaction: dialogue
   Emotional Tone: positive
   Episodes: S1E1, S1E3, S1E7, S1E12
```

### 5. Semantic Character Moment Search

Search for specific character moments using natural language:

```bash
# Search for character moments. --show is required in practice: argparse marks it
# optional, but the agent raises ValueError without it (see the note below).
python main.py search-character-moments "heroic determination" \
    --show "My Hero Academia" --limit 10
```

Search capabilities:
- **Natural Language Queries**: "heroic moments", "character growth", "emotional scenes"
- **Character-Specific Search**: Filter by specific characters
- **Show-Specific Search**: Filter by specific anime series
- **Relevance Scoring**: Results ranked by semantic similarity

Example output:
```
Character Moments for Query: 'heroic determination'

1. Izuku - My Hero Academia S1E4
   Relevance Score: 0.892
   Personality Traits: determined, kind, brave
   Preview: Character: Izuku "I want to become a hero who can save everyone with a smile..."

2. All Might - My Hero Academia S1E1
   Relevance Score: 0.845
   Personality Traits: brave, confident, kind
   Preview: Character: All Might "Being a hero means more than just having power..."
```

### 6. Character Database Statistics

Get overview of the character analysis database:

```bash
# Show character database statistics
python main.py character-stats
```

Statistics include:
- Total character profiles analyzed
- Number of character interactions recorded
- Unique characters and shows in database
- Processing coverage metrics

## 🧠 Technical Architecture

### Vector Database Structure

The character analysis system uses three ChromaDB collections:

1. **Character Profiles Collection** (`character_profiles`)
   - Stores character embeddings and metadata
   - Includes personality traits, dialogue patterns
   - Enables similarity search across characters

2. **Character Interactions Collection** (`character_interactions`)
   - Records interactions between characters
   - Tracks interaction types and emotional tones
   - Powers relationship analysis

3. **Character Development Collection** (`character_development`)
   - Tracks character changes over time
   - Stores episode-by-episode trait evolution
   - Enables development arc analysis

All three collections are shared across shows, so every write must carry show
identity. Build entry metadata through `BaseMetadata.create()` in
`core/metadata_schemas.py`, which canonicalizes the show name via
`core/show_registry.py` and derives `episode_key` as
`{show_id}_S{season}E{episode}`. Calling the analysis methods without a show
name raises `ValueError: show_name is required to prevent cross-show
contamination` rather than writing an unattributable row.

### Embedding Strategy

Characters are embedded using a multi-faceted approach:

Embeddings are produced by the `all-MiniLM-L6-v2` sentence-transformer
(`agents/character_analysis_agent.py`). If `sentence-transformers` is not
installed the agent logs a warning and disables embeddings; the CLI commands
below then return nothing rather than failing.

- **Dialogue Embeddings**: Semantic representation of character speech
- **Personality Embeddings**: Trait-based character representation
- **Context Embeddings**: Character behavior in different situations
- **Relationship Embeddings**: How characters interact with others

### Character Extraction Pipeline

1. **Dialogue Parsing**: Extract character speech from transcripts
2. **Name Normalization**: `_canonicalize_character_name()` performs
   *surface-form* canonicalization — strips bracketed stage directions, leading
   titles and trailing honorifics (with a required separator, so "Susan"
   survives), then normalizes case. `CharacterProfile.canonical_name` holds the
   result and `aliases` holds the other spellings that folded into it
   (`["Iida-Kun", "Iida Sensei"]` → `Iida`). Franchise-level identity
   ("Deku" → "Izuku Midoriya") needs a per-show character registry the pipeline
   does not have; the boundary is documented on the dataclass.
3. **Trait Extraction**: Identify personality traits from dialogue patterns
4. **Interaction Analysis**: Detect character interactions and relationships
5. **Vector Generation**: Create semantic embeddings for search
6. **Database Storage**: Store profiles and relationships in ChromaDB

## 📊 Analysis Capabilities

### Personality Trait Detection

The system recognizes these personality traits through dialogue analysis:

- **determined**: "never give up", "won't quit", "persistent"
- **kind**: "caring", "gentle", "compassionate", "helpful"
- **brave**: "courageous", "fearless", "heroic", "bold"
- **intelligent**: "smart", "clever", "brilliant", "analytical"
- **stubborn**: "headstrong", "obstinate", "refuses to"
- **loyal**: "faithful", "devoted", "stands by", "supports"
- **confident**: "self-assured", "believes in", "certain"
- **anxious**: "worried", "nervous", "uncertain", "doubts"
- **hot-tempered**: "angry", "explosive", "rage", "furious"
- **calm**: "composed", "peaceful", "serene", "collected"

### Interaction Types

Character interactions are classified as:

- **dialogue**: Regular conversation between characters
- **conflict**: Disagreements, fights, or tension
- **cooperation**: Working together or supporting each other
- **mentorship**: Teaching or guidance relationships

### Emotional Tone Analysis

Interactions are analyzed for emotional context:

- **positive**: Happy, supportive, friendly interactions
- **negative**: Angry, hostile, or sad interactions  
- **neutral**: Factual or casual interactions
- **tense**: Serious, worried, or uncertain interactions

## 🚀 Advanced Usage

### Character Arc Analysis

```python
from agents.character_analysis_agent import CharacterAnalysisAgent

agent = CharacterAnalysisAgent()

# Analyze character development across multiple episodes
development = agent.analyze_character_development("Izuku", "My Hero Academia")
print(f"Development Score: {development['development_score']:.2f}")
```

### Custom Character Searches

```python
# Search for specific character traits.
# show_name is a required positional parameter, not an optional filter.
moments = agent.search_character_moments(
    "determined hero never give up",
    character_name="Izuku",
    show_name="My Hero Academia",
    limit=5,
)

# Find character relationships (show_name is required here too)
relationships = agent.get_character_relationships("Izuku", "My Hero Academia")
```

### Cross-Show Character Analysis

Cross-show search is **not** expressed by omitting the show. `show_name` is
required — passing `None` raises `ValueError` — because it identifies the
character's *own* show, which is then used as the exclusion filter:

```python
# Find characters in OTHER shows that match this character's name/profile.
# show_name names Izuku's own show; include_same_show=False excludes it.
similar = agent.find_similar_characters(
    "Izuku", show_name="My Hero Academia", limit=10, include_same_show=False
)
```

With `include_same_show=True` (the default) the query is filtered to that show
and returns similar characters from within it.

Note that the `include_same_show=False` branch also filters on
`character_name == "Izuku"`, so it finds *same-named* characters in other shows
rather than personality-similar ones. Cross-show comparison by personality is not
implemented today.

## 🎯 Use Cases

### Content Analysis
- Identify key character development moments
- Track personality changes across story arcs
- Find emotionally significant scenes

### Character Comparison
- Compare protagonists across different series
- Find archetypal character patterns
- Analyze character relationship dynamics

### Story Development
- Understand character interaction patterns
- Identify character growth opportunities
- Track narrative arc progression

### Fan Analysis
- Deep dive into character psychology
- Compare fan-favorite characters
- Analyze character popularity factors

## 🔍 Example Workflows

### Analyzing a New Series

1. **Process Episodes**: Use the main system to process episode transcripts
2. **Character Analysis**: Analyze characters in each episode
3. **Relationship Mapping**: Track character interactions
4. **Development Tracking**: Monitor character growth over time
5. **Cross-Series Comparison**: Compare to characters from other shows

### Character Research

1. **Search Character Moments**: Find specific scenes or traits
2. **Similarity Analysis**: Find similar characters
3. **Relationship Analysis**: Understand character connections
4. **Development Study**: Track character evolution

### Comparative Analysis

1. **Multi-Show Analysis**: Process multiple anime series
2. **Character Clustering**: Group similar character types
3. **Trait Evolution**: Track how traits develop differently
4. **Relationship Patterns**: Compare interaction styles

## 🛠️ Customization

### Adding New Personality Traits

Extend the personality detection by adding new trait keywords:

```python
# In character_analysis_agent.py
self.personality_keywords.update(
    {
        "mysterious": ["mysterious", "enigmatic", "secretive", "hidden"],
        "cheerful": ["cheerful", "upbeat", "optimistic", "joyful"],
        "sarcastic": ["sarcastic", "witty", "ironic", "mocking"],
    }
)
```

### Custom Interaction Types

Add new interaction type detection:

```python
# Custom interaction classification
if any(word in context_text.lower() for word in ["teach", "explain", "lesson"]):
    interaction_type = "mentorship"
elif any(word in context_text.lower() for word in ["romance", "love", "affection"]):
    interaction_type = "romantic"
```

### Advanced Embedding Models

Use more sophisticated models for better analysis:

```python
# Use larger, more capable models
from sentence_transformers import SentenceTransformer

encoder = SentenceTransformer("all-mpnet-base-v2")  # More accurate but slower
```

## 📈 Performance Considerations

### Scaling

The system is designed to scale with your anime database:

- **Efficient Chunking**: Large episodes are split into manageable chunks
- **Batch Processing**: Multiple episodes can be processed efficiently
- **Incremental Updates**: New episodes add to existing character profiles
- **Memory Management**: ChromaDB handles large-scale vector operations

### Performance Tips

1. **Process in Batches**: Analyze multiple episodes together for efficiency
2. **Use Filters**: Specify show/character filters to speed up searches
3. **Limit Results**: Use reasonable limits for search operations
4. **Regular Cleanup**: Remove outdated or incorrect character data

### Resource Usage

- **Disk Space**: ChromaDB creates persistent storage for embeddings
- **Memory**: Sentence transformers use GPU if available
- **CPU**: Character analysis is CPU-intensive for large datasets

## 🐛 Troubleshooting

### Common Issues

**ChromaDB Installation Issues**
```bash
# If you encounter installation problems
pip install --upgrade chromadb
# or
conda install -c conda-forge chromadb
```

**Memory Issues with Large Datasets**

There is no transcript-chunking knob. `analyze_episode_characters()` splits a
transcript by speaker via `_extract_character_dialogues_with_aliases()`, so
memory scales with the number of distinct speakers and their dialogue, not with a
configurable chunk size. To reduce peak memory, analyse fewer episodes per
process rather than tuning a parameter that does not exist.

**Embedding Model Download Issues**  
```python
# Pre-download models
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")  # Downloads model
```

### Performance Issues

**Slow Character Analysis**
- Use GPU acceleration if available
- Reduce embedding dimensions
- Process fewer episodes at once

**High Memory Usage**
- Clear ChromaDB cache periodically
- Use smaller embedding models
- Process episodes individually

### Debugging

Enable debug logging for detailed analysis:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

This will show detailed information about character extraction, embedding generation, and database operations.
