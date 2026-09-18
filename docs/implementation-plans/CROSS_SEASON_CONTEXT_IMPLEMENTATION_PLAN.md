# Cross-Season Context and Vector Storage Implementation Plan

## 📋 Overview

This document outlines the Test-Driven Development (TDD) implementation plan for adding cross-season character development tracking and vector storage capabilities to the Anime Video Generator system. This enhancement will enable Season 2+ videos to reference and build upon character development from previous seasons, creating more cohesive and contextually aware content.

## 🎯 Current State vs. Desired State

### Current State ❌

- Season summaries generated in isolation without previous season context
- Character development data stored in ChromaDB but not retrieved for cross-season analysis
- No historical character arc references in new season content
- Season analysis stored in `development_collection` but never queried for continuity

### Desired State ✅

- Season 2+ summaries reference character development from Season 1
- Automatic retrieval of relevant cross-season character arcs for context
- Semantic search for similar character development patterns across seasons
- AI prompts enhanced with historical character development context
- Vector-based storage and retrieval of season-to-season narrative continuity

## 🧪 TDD Implementation Plan

### Phase 1: Test Design and Specification

#### 1.1 Cross-Season Context Retrieval Tests (Write First)

**File**: `tests/test_cross_season_context.py`

```python
#!/usr/bin/env python3
"""
Test suite for cross-season context retrieval and vector storage functionality.
Following TDD - these tests should FAIL initially.

Uses pytest with ChromaDB fixtures for comprehensive vector database testing.
"""

import pytest
from typing import Dict, List, Any
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path

from main_refactored import AnimeVideoGenerator
from agents.character_analysis_agent import CharacterAnalysisAgent
from core.schemas import CrossSeasonContext, CharacterContinuity

class TestCrossSeasonContextRetrieval:
    
    @pytest.fixture
    def temp_character_db(self):
        """Fixture providing a temporary ChromaDB instance for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir) / "test_character_db"
    
    @pytest.fixture 
    def character_agent(self, temp_character_db):
        """Fixture providing a CharacterAnalysisAgent with temporary database."""
        return CharacterAnalysisAgent(persist_directory=str(temp_character_db))
    
    def test_retrieve_previous_season_analysis_from_vector_db(self, character_agent):
        """Test retrieving previous season analysis data from ChromaDB development collection."""
        # Setup: Store Season 1 analysis in vector database
        season1_analysis = {
            'show_name': 'Test Show',
            'season': 1,
            'total_episodes': 13,
            'character_development': {
                'Protagonist': {'growth_score': 0.8, 'key_traits': ['brave', 'determined']},
                'Rival': {'growth_score': 0.6, 'key_traits': ['competitive', 'proud']}
            },
            'dominant_themes': ['friendship', 'perseverance'],
            'pivotal_moments': ['rival confrontation', 'first victory']
        }
        character_agent._store_season_analysis(season1_analysis)
        
        # Test: Retrieve Season 1 context for Season 2 generation
        context = character_agent.get_previous_season_context('Test Show', 2)
        
        assert context is not None
        assert len(context['documents']) > 0
        assert 'Test Show' in context['documents'][0]
        assert 'Season 1' in context['documents'][0]
        assert context['metadatas'][0]['season'] == 1
    
    def test_get_character_historical_development_across_seasons(self, character_agent):
        """Test retrieving character development history across multiple seasons."""
        # Setup: Store character data for multiple seasons
        for season in [1, 2]:
            character_agent.store_character_profile({
                'name': 'Protagonist',
                'show_name': 'Test Show',
                'season': season,
                'episode': 1,
                'traits': ['brave', 'determined'] if season == 1 else ['brave', 'confident', 'leader'],
                'development_score': 0.5 if season == 1 else 0.8
            })
        
        # Test: Get character development across seasons
        development = character_agent.get_character_historical_development('Protagonist', 'Test Show')
        
        assert len(development) >= 2  # Should have data from both seasons
        assert development[0]['season'] < development[1]['season']  # Chronological order
        assert 'leader' in development[1]['traits']  # Season 2 trait evolution
        assert development[1]['development_score'] > development[0]['development_score']
    
    def test_semantic_search_for_similar_character_arcs(self, character_agent):
        """Test semantic search for similar character development patterns."""
        # Setup: Store various character arc patterns
        arc_patterns = [
            "Character grows from coward to hero through trials",
            "Rival becomes ally after understanding friendship", 
            "Mentor sacrifices themselves for student growth",
            "Student surpasses teacher through dedication"
        ]
        
        for i, pattern in enumerate(arc_patterns):
            character_agent._store_character_arc_pattern(f"Pattern_{i}", pattern)
        
        # Test: Search for similar character arcs
        query = "Character transformation from enemy to friend"
        similar_arcs = character_agent.find_similar_character_arcs(query, n_results=2)
        
        assert len(similar_arcs['documents']) == 2
        assert any('rival' in doc.lower() for doc in similar_arcs['documents'])
    
    def test_cross_season_prompt_enhancement(self):
        """Test that Season 2+ prompts include Season 1 character context."""
        generator = AnimeVideoGenerator()
        
        # Mock previous season context
        previous_context = {
            'character_arcs': ['Protagonist learned courage', 'Rival discovered friendship'],
            'unresolved_plots': ['mysterious villain identity', 'hidden power awakening'],
            'relationship_evolution': ['enemies to allies', 'mentor to equal']
        }
        
        # Generate Season 2 prompt with historical context
        prompt = generator._generate_cross_season_prompt(
            'Test Show', 2, {}, 10, previous_context
        )
        
        # Verify Season 1 context is referenced
        assert 'Season 1' in prompt
        assert 'previous season' in prompt.lower()
        assert 'character development from' in prompt.lower()
        assert len(prompt) > 1000  # Should be longer with added context

class TestCrossSeasonVectorStorage:
    
    def test_season_analysis_vector_embedding_quality(self, character_agent):
        """Test that season analysis is properly embedded in vector format."""
        analysis = {
            'show_name': 'Test Show',
            'season': 1,
            'character_development': {'Hero': {'growth': 'significant'}},
            'themes': ['friendship', 'courage']
        }
        
        # Store and verify embedding creation
        character_agent._store_season_analysis(analysis)
        
        # Query to verify it was stored with proper embeddings
        results = character_agent.development_collection.query(
            query_texts=['Test Show Season 1 character development'],
            n_results=1
        )
        
        assert len(results['documents']) > 0
        assert 'Test Show' in results['documents'][0]
    
    def test_temporal_metadata_filtering(self, character_agent):
        """Test filtering by temporal metadata for season ordering."""
        # Store multiple seasons
        for season in [1, 2, 3]:
            analysis = {
                'show_name': 'Test Show',
                'season': season,
                'themes': [f'season_{season}_theme']
            }
            character_agent._store_season_analysis(analysis)
        
        # Test querying only previous seasons (< current season)
        previous_seasons = character_agent.development_collection.query(
            query_texts=['Test Show character development'],
            where={'$and': [
                {'show_name': {'$eq': 'Test Show'}},
                {'season': {'$lt': 3}}  # Only seasons before Season 3
            ]},
            n_results=10
        )
        
        assert len(previous_seasons['metadatas']) == 2  # Should get seasons 1 and 2
        seasons_found = [meta['season'] for meta in previous_seasons['metadatas']]
        assert 1 in seasons_found and 2 in seasons_found
        assert 3 not in seasons_found
```

#### 1.2 Character Continuity Integration Tests

**File**: `tests/test_character_continuity_integration.py`

```python
#!/usr/bin/env python3
"""
Integration tests for character continuity across seasons.
Tests the complete workflow from Season 1 storage to Season 2 context retrieval.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from main_refactored import AnimeVideoGenerator
from agents.character_analysis_agent import CharacterAnalysisAgent

class TestCharacterContinuityIntegration:
    
    @pytest.fixture
    def full_generator_with_temp_db(self):
        """Fixture providing a complete generator with temporary character database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('agents.character_analysis_agent.CharacterAnalysisAgent') as mock_agent:
                mock_instance = Mock()
                mock_agent.return_value = mock_instance
                generator = AnimeVideoGenerator()
                generator.character_agent = CharacterAnalysisAgent(persist_directory=temp_dir)
                yield generator
    
    @patch('main_refactored.AnimeVideoGenerator._create_voice_recording')
    @patch('main_refactored.AnimeVideoGenerator._generate_season_images')
    def test_season_2_includes_season_1_character_context(self, mock_images, mock_voice, full_generator_with_temp_db):
        """Test that Season 2 processing includes Season 1 character development context."""
        generator = full_generator_with_temp_db
        
        # Mock dependencies
        mock_voice.return_value = "test_audio.wav"
        mock_images.return_value = None
        
        # Process Season 1 first to establish character baseline
        season1_result = generator.process_season("Test Show", 1, target_minutes=8)
        assert season1_result.success
        
        # Process Season 2 with cross-season context
        season2_result = generator.process_season("Test Show", 2, target_minutes=8)
        
        # Verify Season 2 result includes cross-season context
        assert season2_result.success
        assert 'cross_season_context' in season2_result.data
        assert season2_result.data['cross_season_context']['previous_seasons'] == [1]
        assert 'character_continuity' in season2_result.data['cross_season_context']
    
    def test_character_development_tracking_across_seasons(self, full_generator_with_temp_db):
        """Test that character development properly tracks across multiple seasons."""
        generator = full_generator_with_temp_db
        
        # Simulate character evolution across 3 seasons
        seasons_data = [
            {'season': 1, 'traits': ['naive', 'brave'], 'development': 0.3},
            {'season': 2, 'traits': ['confident', 'brave', 'strategic'], 'development': 0.7},
            {'season': 3, 'traits': ['confident', 'brave', 'strategic', 'leader'], 'development': 0.9}
        ]
        
        # Store character development for each season
        for season_data in seasons_data:
            generator.character_agent.store_character_development_milestone(
                'Protagonist', 'Test Show', season_data['season'], 
                season_data['traits'], season_data['development']
            )
        
        # Test cross-season development analysis
        development_arc = generator.character_agent.analyze_character_development_arc(
            'Protagonist', 'Test Show', seasons=[1, 2, 3]
        )
        
        assert development_arc['total_seasons'] == 3
        assert development_arc['development_trajectory'] == 'ascending'
        assert 'leader' in development_arc['final_traits']
        assert development_arc['growth_rate'] > 0.0
```

### Phase 2: Enhanced Vector Storage Architecture

#### 2.1 Cross-Season Context Schema

**File**: `core/schemas.py` (additions)

```python
from datetime import datetime
from typing import Optional, List, Dict

class CrossSeasonContext(BaseModel):
    """Schema for cross-season character and story context."""
    show_name: str = Field(description="Name of the show")
    current_season: int = Field(description="Current season being processed")
    previous_seasons: List[int] = Field(description="List of previous seasons with data")
    character_continuity: Dict[str, Any] = Field(description="Character development continuity data")
    unresolved_plots: List[str] = Field(description="Unresolved plot threads from previous seasons")
    recurring_themes: List[str] = Field(description="Themes that span multiple seasons") 
    relationship_evolution: Dict[str, Any] = Field(description="How relationships evolved across seasons")
    world_building_elements: List[str] = Field(description="World-building context from previous seasons")

class CharacterContinuity(BaseModel):
    """Schema for character development continuity across seasons."""
    character_name: str = Field(description="Name of the character")
    development_arc: List[Dict] = Field(description="Development milestones across seasons")
    personality_evolution: Dict[str, List[str]] = Field(description="Personality traits by season")
    relationship_changes: Dict[str, str] = Field(description="How relationships changed over time")
    unresolved_character_plots: List[str] = Field(description="Unresolved character storylines")
    
class SeasonAnalysisEmbedding(BaseModel):
    """Schema for season analysis vector embeddings."""
    season_id: str = Field(description="Unique season identifier")
    embedding_vector: List[float] = Field(description="Dense vector representation")
    metadata: Dict[str, Any] = Field(description="Season metadata for filtering")
    content_summary: str = Field(description="Human-readable season summary")
    created_at: datetime = Field(description="Timestamp of creation")
```

#### 2.2 Enhanced Character Analysis Agent Methods

**File**: `agents/character_analysis_agent.py` (new methods)

```python
def get_previous_season_context(self, show_name: str, current_season: int) -> Dict[str, Any]:
    """
    Retrieve comprehensive previous season context from ChromaDB development collection.
    
    Uses semantic search to find relevant character development, themes, and plot elements
    from previous seasons that should inform the current season's content generation.
    
    Args:
        show_name: Name of the show
        current_season: Current season being processed
        
    Returns:
        Dictionary containing cross-season context data
    """
    try:
        # Query development collection for previous seasons
        results = self.development_collection.query(
            query_texts=[
                f"{show_name} character development themes relationships plot progression",
                f"{show_name} season character arcs story elements"
            ],
            where={
                "$and": [
                    {"show_name": {"$eq": show_name}},
                    {"season": {"$lt": current_season}},
                    {"analysis_type": {"$eq": "season_analysis"}}
                ]
            },
            n_results=current_season - 1,  # Get all previous seasons
            include=["documents", "metadatas", "distances"]
        )
        
        if not results['documents'] or not results['documents'][0]:
            logger.info(f"No previous season context found for {show_name} Season {current_season}")
            return self._create_empty_context(show_name, current_season)
        
        # Parse and structure the context
        return self._parse_previous_season_context(results, show_name, current_season)
        
    except Exception as e:
        logger.error(f"Failed to retrieve previous season context: {e}")
        return self._create_empty_context(show_name, current_season)

def get_character_historical_development(self, character_name: str, show_name: str, 
                                       seasons: List[int] = None) -> List[Dict]:
    """
    Retrieve character development history across specified seasons.
    
    Uses vector similarity search to find character development patterns and evolution
    across multiple seasons for continuity analysis.
    
    Args:
        character_name: Name of the character to analyze
        show_name: Name of the show
        seasons: Optional list of specific seasons (default: all available)
        
    Returns:
        List of character development data ordered chronologically
    """
    try:
        # Build query for character-specific development
        query_text = f"{character_name} character development personality growth {show_name}"
        
        # Build where clause for season filtering
        where_clause = {
            "$and": [
                {"character_name": {"$eq": character_name}},
                {"show_name": {"$eq": show_name}}
            ]
        }
        
        if seasons:
            where_clause["$and"].append({"season": {"$in": seasons}})
        
        # Query character profiles collection
        results = self.characters_collection.query(
            query_texts=[query_text],
            where=where_clause,
            n_results=100,  # Get all character instances
            include=["documents", "metadatas", "distances"]
        )
        
        # Sort by season/episode chronologically
        character_data = []
        for meta in results['metadatas'][0]:
            character_data.append({
                'season': meta['season'],
                'episode': meta['episode'],
                'traits': json.loads(meta.get('personality_traits', '[]')),
                'development_score': meta.get('development_score', 0.0),
                'dialogue_count': meta.get('dialogue_count', 0)
            })
        
        # Sort chronologically
        character_data.sort(key=lambda x: (x['season'], x['episode']))
        return character_data
        
    except Exception as e:
        logger.error(f"Failed to get character historical development: {e}")
        return []

def find_similar_character_arcs(self, query_description: str, 
                               n_results: int = 5) -> Dict[str, Any]:
    """
    Find character arcs similar to the provided description using semantic search.
    
    Args:
        query_description: Natural language description of character arc
        n_results: Number of similar arcs to return
        
    Returns:
        Similar character development patterns
    """
    try:
        # Search development collection for similar patterns
        results = self.development_collection.query(
            query_texts=[query_description],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        return {
            'query': query_description,
            'similar_arcs': results['documents'][0] if results['documents'] else [],
            'similarity_scores': results['distances'][0] if results['distances'] else [],
            'source_metadata': results['metadatas'][0] if results['metadatas'] else []
        }
        
    except Exception as e:
        logger.error(f"Failed to find similar character arcs: {e}")
        return {'query': query_description, 'similar_arcs': [], 'similarity_scores': [], 'source_metadata': []}

def _parse_previous_season_context(self, results: Dict, show_name: str, current_season: int) -> Dict:
    """Parse ChromaDB results into structured cross-season context."""
    context = {
        'show_name': show_name,
        'current_season': current_season,
        'previous_seasons': [],
        'character_continuity': {},
        'dominant_themes': [],
        'unresolved_plots': [],
        'relationship_evolution': [],
        'key_events': []
    }
    
    # Extract information from each previous season
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        season_num = meta['season']
        context['previous_seasons'].append(season_num)
        
        # Parse character development from document
        if 'Character Development Score' in doc:
            # Extract character information using simple text parsing
            # In production, could use more sophisticated NLP parsing
            char_info = self._extract_character_info_from_text(doc)
            context['character_continuity'][f'season_{season_num}'] = char_info
        
        # Extract themes and plot elements
        context['dominant_themes'].extend(self._extract_themes_from_text(doc))
        context['key_events'].extend(self._extract_events_from_text(doc))
    
    # Remove duplicates and sort
    context['previous_seasons'] = sorted(list(set(context['previous_seasons'])))
    context['dominant_themes'] = list(set(context['dominant_themes']))
    
    return context

def _create_empty_context(self, show_name: str, current_season: int) -> Dict:
    """Create empty context structure for first season or when no data exists."""
    return {
        'show_name': show_name,
        'current_season': current_season,
        'previous_seasons': [],
        'character_continuity': {},
        'dominant_themes': [],
        'unresolved_plots': [],
        'relationship_evolution': [],
        'key_events': [],
        'is_first_season': current_season == 1
    }
```

### Phase 3: Enhanced Season Processing with Cross-Season Context

#### 3.1 Cross-Season Prompt Generation

**File**: `main_refactored.py` (new method)

```python
def _generate_cross_season_prompt(self, show_name: str, season: int, 
                                season_analysis: Dict, target_minutes: int,
                                previous_context: Dict = None) -> str:
    """
    Generate AI prompt with cross-season character development context.
    
    Args:
        show_name: Name of the show
        season: Current season number
        season_analysis: Current season analysis data
        target_minutes: Target video length in minutes
        previous_context: Previous season context from vector database
        
    Returns:
        Enhanced prompt with cross-season character continuity
    """
    # Get base prompt structure
    base_prompt = self._generate_length_adaptive_prompt(
        show_name, season, season_analysis, target_minutes
    )
    
    # If no previous context (Season 1), return base prompt
    if not previous_context or season == 1:
        return base_prompt
    
    # Enhance prompt with cross-season context
    cross_season_context = f"""
    
    IMPORTANT: Include Cross-Season Character Development Context
    
    This is Season {season} of {show_name}. Please reference character development from previous seasons:
    
    Previous Season Character Development:
    """
    
    # Add character continuity information
    for season_key, char_data in previous_context.get('character_continuity', {}).items():
        cross_season_context += f"\n    {season_key}: {char_data}"
    
    # Add unresolved plot threads
    if previous_context.get('unresolved_plots'):
        cross_season_context += f"""
        
    Unresolved Plot Threads from Previous Seasons:
    {', '.join(previous_context['unresolved_plots'])}
    
    Please address how Season {season} builds upon or resolves these elements.
        """
    
    # Add recurring themes
    if previous_context.get('dominant_themes'):
        cross_season_context += f"""
        
    Recurring Themes to Reference:
    {', '.join(previous_context['dominant_themes'])}
    
    Show how these themes evolve or are explored differently in Season {season}.
        """
    
    # Add relationship evolution context
    if previous_context.get('relationship_evolution'):
        cross_season_context += f"""
        
    Character Relationship Evolution from Previous Seasons:
    {', '.join(previous_context['relationship_evolution'])}
    
    Reference how relationships have changed and continue to develop in Season {season}.
        """
    
    return base_prompt + cross_season_context

def _enhanced_process_season_with_context(self, show_name: str, season: int, 
                                        force_reprocess: bool = False,
                                        target_minutes: int = None) -> ProcessingResult:
    """
    Enhanced season processing that includes cross-season character context.
    
    This replaces the current process_season method to add cross-season continuity.
    """
    logger.info(f"🎬 Starting cross-season aware processing for {show_name} Season {season}")
    
    if target_minutes:
        logger.info(f"🎯 Target video length: {target_minutes} minutes")
    
    try:
        # Calculate video structure
        video_config = self._calculate_video_structure(target_minutes)
        
        # Get cross-season context if available
        previous_context = None
        if season > 1 and self.character_agent:
            logger.info("🔍 Retrieving cross-season character context...")
            previous_context = self.character_agent.get_previous_season_context(show_name, season)
        
        # [Continue with existing season processing logic...]
        # [But use _generate_cross_season_prompt instead of regular prompt]
        
        # Enhanced summary generation with cross-season context
        target_min = target_minutes or 5
        logger.info(f"📝 Generating {target_min}-minute summary with cross-season context...")
        season_summary = self._generate_season_summary_with_cross_season_context(
            show_name, season, season_analysis, target_min, previous_context
        )
        
        # [Rest of processing remains the same...]
        
        return ProcessingResult(
            success=True,
            data={
                "show_name": show_name,
                "season": season,
                "video_config": video_config,
                "target_duration_minutes": target_min,
                "cross_season_context": previous_context,  # Include context in result
                "character_continuity_enabled": season > 1 and previous_context is not None,
                # [Other existing data...]
            }
        )
        
    except Exception as e:
        logger.error(f"Cross-season processing failed for {show_name} S{season}: {e}")
        return ProcessingResult(success=False, error=str(e))
```

#### 3.2 Enhanced Character Analysis Storage

**File**: `agents/character_analysis_agent.py` (enhanced methods)

```python
def store_character_development_milestone(self, character_name: str, show_name: str,
                                        season: int, traits: List[str], 
                                        development_score: float) -> None:
    """
    Store character development milestones for cross-season tracking.
    
    Creates rich embeddings that capture character evolution patterns for
    semantic retrieval in future season processing.
    """
    try:
        milestone_id = f"{show_name}_{character_name}_S{season}_milestone"
        
        # Create rich document for character development
        document = f"""
        Character Development Milestone: {character_name} in {show_name} Season {season}
        
        Character Traits: {', '.join(traits)}
        Development Score: {development_score:.2f}
        Season Context: Season {season} character evolution
        
        This character has developed the following traits by Season {season}: {', '.join(traits)}.
        Character growth level: {development_score:.2f} out of 1.0.
        
        Previous traits evolution and personality development patterns for {character_name}.
        """
        
        metadata = {
            'character_name': character_name,
            'show_name': show_name,
            'season': season,
            'development_score': development_score,
            'trait_count': len(traits),
            'analysis_type': 'character_milestone',
            'created_at': str(datetime.now())
        }
        
        # Store in development collection for cross-season retrieval
        self.development_collection.upsert(
            ids=[milestone_id],
            documents=[document.strip()],
            metadatas=[metadata]
        )
        
        logger.info(f"Stored character milestone for {character_name} Season {season}")
        
    except Exception as e:
        logger.error(f"Failed to store character development milestone: {e}")

def analyze_character_development_arc(self, character_name: str, show_name: str,
                                    seasons: List[int]) -> Dict[str, Any]:
    """
    Analyze character development arc across multiple specified seasons.
    
    Uses vector similarity to track character evolution patterns and identify
    development trajectories for cross-season continuity analysis.
    """
    try:
        # Get historical character development
        historical_data = self.get_character_historical_development(character_name, show_name)
        
        # Filter for specified seasons
        if seasons:
            historical_data = [data for data in historical_data if data['season'] in seasons]
        
        if len(historical_data) < 2:
            return {'error': 'Insufficient data for character arc analysis'}
        
        # Analyze development trajectory
        development_scores = [data['development_score'] for data in historical_data]
        trait_evolution = self._analyze_trait_evolution(historical_data)
        
        # Determine trajectory pattern
        trajectory = self._determine_development_trajectory(development_scores)
        
        return {
            'character_name': character_name,
            'show_name': show_name,
            'total_seasons': len(historical_data),
            'development_trajectory': trajectory,  # 'ascending', 'descending', 'stable', 'fluctuating'
            'initial_traits': historical_data[0]['traits'],
            'final_traits': historical_data[-1]['traits'],
            'growth_rate': (development_scores[-1] - development_scores[0]) / len(development_scores),
            'trait_evolution': trait_evolution,
            'season_range': f"Season {min(seasons)} to Season {max(seasons)}"
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze character development arc: {e}")
        return {'error': str(e)}

def _store_character_arc_pattern(self, pattern_id: str, pattern_description: str) -> None:
    """Store character arc patterns for similarity matching."""
    try:
        metadata = {
            'pattern_id': pattern_id,
            'analysis_type': 'character_arc_pattern',
            'created_at': str(datetime.now())
        }
        
        self.development_collection.upsert(
            ids=[pattern_id],
            documents=[pattern_description],
            metadatas=[metadata]
        )
        
    except Exception as e:
        logger.error(f"Failed to store character arc pattern: {e}")

def _extract_character_info_from_text(self, text: str) -> Dict:
    """Extract character information from season analysis text."""
    # Simple implementation - could be enhanced with NLP
    char_info = {}
    
    # Look for character development patterns in text
    if 'Character Development Score' in text:
        # Extract score using regex or simple parsing
        import re
        score_match = re.search(r'Character Development Score: ([\d.]+)', text)
        if score_match:
            char_info['development_score'] = float(score_match.group(1))
    
    # Extract character names mentioned
    if 'Key Characters:' in text:
        chars_match = re.search(r'Key Characters: ([^\\n]+)', text)
        if chars_match:
            char_info['key_characters'] = [c.strip() for c in chars_match.group(1).split(',')]
    
    return char_info

def _extract_themes_from_text(self, text: str) -> List[str]:
    """Extract themes from season analysis text."""
    themes = []
    if 'Dominant Themes:' in text:
        import re
        themes_match = re.search(r'Dominant Themes: ([^\\n]+)', text)
        if themes_match:
            themes = [t.strip() for t in themes_match.group(1).split(',')]
    return themes

def _extract_events_from_text(self, text: str) -> List[str]:
    """Extract key events from season analysis text."""
    events = []
    if 'Top Pivotal Moments:' in text:
        import re
        events_match = re.search(r'Top Pivotal Moments: (\\d+)', text)
        if events_match:
            events = [f"Season pivotal moment {i+1}" for i in range(int(events_match.group(1)))]
    return events

def _analyze_trait_evolution(self, historical_data: List[Dict]) -> Dict:
    """Analyze how character traits evolved across seasons."""
    evolution = {
        'new_traits_by_season': {},
        'persistent_traits': [],
        'lost_traits': []
    }
    
    all_traits = set()
    for data in historical_data:
        all_traits.update(data['traits'])
        
        # Track new traits for each season
        if historical_data.index(data) > 0:
            previous_traits = set(historical_data[historical_data.index(data) - 1]['traits'])
            new_traits = set(data['traits']) - previous_traits
            evolution['new_traits_by_season'][f'season_{data["season"]}'] = list(new_traits)
    
    # Find persistent traits (appear in all seasons)
    first_traits = set(historical_data[0]['traits'])
    last_traits = set(historical_data[-1]['traits'])
    evolution['persistent_traits'] = list(first_traits.intersection(last_traits))
    evolution['lost_traits'] = list(first_traits - last_traits)
    
    return evolution

def _determine_development_trajectory(self, scores: List[float]) -> str:
    """Determine character development trajectory pattern."""
    if len(scores) < 2:
        return 'insufficient_data'
    
    # Calculate trend
    overall_change = scores[-1] - scores[0]
    
    if overall_change > 0.2:
        return 'ascending'
    elif overall_change < -0.2:
        return 'descending'
    elif max(scores) - min(scores) > 0.3:
        return 'fluctuating'
    else:
        return 'stable'
```

### Phase 4: CLI Integration for Cross-Season Features

#### 4.1 Enhanced CLI Commands

**File**: `main_refactored.py` (CLI additions)

```python
# Add new CLI command for cross-season analysis
cross_season_parser = subparsers.add_parser('analyze-cross-season',
                                           help='Analyze character development across multiple seasons')
cross_season_parser.add_argument('show', help='Show name')
cross_season_parser.add_argument('character', help='Character name')
cross_season_parser.add_argument('--seasons', nargs='+', type=int, 
                                help='Specific seasons to analyze (default: all)')

# Add cross-season context flag to create-season-summary
season_summary_parser.add_argument('--include-context', action='store_true',
                                  help='Include previous season context in summary generation')

# CLI handler for cross-season analysis
elif args.command == 'analyze-cross-season':
    if not generator.character_agent:
        print("❌ Character analysis not available (missing ChromaDB dependencies)")
        return
    
    print(f"🔍 Analyzing {args.character} development across seasons in {args.show}...")
    
    arc_analysis = generator.character_agent.analyze_character_development_arc(
        args.character, args.show, args.seasons
    )
    
    if 'error' in arc_analysis:
        print(f"❌ Analysis failed: {arc_analysis['error']}")
    else:
        print("✅ Character Development Arc Analysis:")
        print(f"   Character: {arc_analysis['character_name']}")
        print(f"   Seasons Analyzed: {arc_analysis['total_seasons']}")
        print(f"   Development Trajectory: {arc_analysis['development_trajectory']}")
        print(f"   Growth Rate: {arc_analysis['growth_rate']:.2f}")
        print(f"   Trait Evolution: {len(arc_analysis['trait_evolution']['new_traits_by_season'])} seasons with new traits")
```

### Phase 5: Advanced Vector Search Optimization

#### 5.1 Sentence Transformers Integration Enhancement

**File**: `agents/character_analysis_agent.py` (enhanced embeddings)

```python
def _create_enhanced_season_embedding(self, season_analysis: Dict) -> List[float]:
    """
    Create enhanced embeddings for season analysis using multiple semantic dimensions.
    
    Uses Sentence Transformers to create rich, multi-faceted embeddings that capture:
    - Character development themes
    - Plot progression patterns  
    - Relationship dynamics
    - Thematic elements
    """
    try:
        # Create comprehensive text representation
        embedding_text = f"""
        {season_analysis['show_name']} Season {season_analysis['season']} Analysis:
        
        Character Development: {self._format_character_development(season_analysis.get('character_development', {}))}
        
        Dominant Themes: {', '.join([theme for theme, _ in season_analysis.get('thematic_evolution', {}).get('dominant_season_themes', [])])}
        
        Key Relationships: {self._format_relationship_data(season_analysis.get('relationship_evolution', {}))}
        
        Plot Elements: {len(season_analysis.get('pivotal_moments', []))} pivotal moments with major story developments
        
        Character Focus: {self._format_character_focus(season_analysis.get('character_focus_distribution', {}))}
        """
        
        # Use SentenceTransformers for enhanced embedding
        if self.encoder:
            embedding = self.encoder.encode(embedding_text.strip())
            return embedding.tolist()
        else:
            # Fallback to simple hash-based embedding
            return self._create_simple_embedding(embedding_text)
            
    except Exception as e:
        logger.error(f"Failed to create enhanced season embedding: {e}")
        return [0.0] * 384  # Return zero vector as fallback

def _format_character_development(self, char_dev: Dict) -> str:
    """Format character development data for embedding text."""
    if not char_dev:
        return "No character development data"
    
    formatted = []
    for char_name, dev_data in char_dev.items():
        growth_score = dev_data.get('character_growth_score', 0.0)
        formatted.append(f"{char_name} (growth: {growth_score:.2f})")
    
    return ', '.join(formatted)

def _format_relationship_data(self, relationships: Dict) -> str:
    """Format relationship evolution data for embedding text."""
    if not relationships:
        return "No relationship data"
    
    formatted = []
    for rel_key, rel_data in relationships.items():
        if isinstance(rel_data, dict) and 'relationship_strength' in rel_data:
            strength = rel_data['relationship_strength']
            formatted.append(f"{rel_key} (strength: {strength:.2f})")
    
    return ', '.join(formatted)

def _format_character_focus(self, focus_data: Dict) -> str:
    """Format character focus distribution for embedding text."""
    if not focus_data or 'main_characters' not in focus_data:
        return "No character focus data"
    
    main_chars = focus_data['main_characters'][:5]  # Top 5 characters
    return ', '.join([f"{char} ({score:.2f})" for char, score in main_chars])

def query_similar_seasons(self, season_analysis: Dict, n_results: int = 3) -> Dict:
    """
    Find seasons with similar character development patterns using vector similarity.
    
    Uses Sentence Transformers cosine similarity to find seasons across different
    shows that have similar character development themes and patterns.
    """
    try:
        # Create query embedding from current season
        query_embedding = self._create_enhanced_season_embedding(season_analysis)
        
        # Search for similar seasons in development collection
        results = self.development_collection.query(
            query_embeddings=[query_embedding],
            where={"analysis_type": {"$eq": "season_analysis"}},
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        return {
            'similar_seasons': results['documents'][0] if results['documents'] else [],
            'similarity_scores': results['distances'][0] if results['distances'] else [],
            'metadata': results['metadatas'][0] if results['metadatas'] else []
        }
        
    except Exception as e:
        logger.error(f"Failed to query similar seasons: {e}")
        return {'similar_seasons': [], 'similarity_scores': [], 'metadata': []}
```

### Phase 6: Testing and Validation (TDD)

#### 6.1 Test Execution Order

1. **Run initial tests** (should FAIL initially)

   ```bash
   python3 -m pytest tests/test_cross_season_context.py -v
   ```

2. **Implement cross-season context retrieval** to make basic tests pass

3. **Run character continuity integration tests**

   ```bash
   python3 -m pytest tests/test_character_continuity_integration.py -v
   ```

4. **Implement enhanced vector storage and prompt generation**

5. **Test complete cross-season workflow**

   ```bash
   python3 -m pytest tests/test_cross_season_context.py tests/test_character_continuity_integration.py -v
   ```

#### 6.2 Manual Testing Commands

```bash
# Test cross-season character analysis
python3 main_refactored.py analyze-cross-season "My Hero Academia" "Izuku" --seasons 1 2

# Create Season 1 summary (establishes baseline)
python3 main_refactored.py create-season-summary "My Hero Academia" 1 --duration 10

# Create Season 2 summary with cross-season context
python3 main_refactored.py create-season-summary "My Hero Academia" 2 --duration 10 --include-context

# Compare Season 1 vs Season 2 character development
python3 main_refactored.py character-development "Izuku" "My Hero Academia"

# Test vector similarity for character arcs
python3 main_refactored.py similar-characters "Izuku" --show "My Hero Academia"
```

## 📊 Implementation Checklist

### Phase 1: Foundation Tests ✅

- [ ] Write failing tests for previous season context retrieval
- [ ] Write failing tests for character historical development
- [ ] Write failing tests for semantic character arc search
- [ ] Write failing tests for cross-season prompt enhancement
- [ ] Write failing integration tests for character continuity

### Phase 2: Vector Storage Enhancement ✅

- [ ] Add CrossSeasonContext and CharacterContinuity schemas
- [ ] Implement get_previous_season_context() method
- [ ] Implement get_character_historical_development() method
- [ ] Implement find_similar_character_arcs() method
- [ ] Enhance _store_season_analysis() with richer embeddings

### Phase 3: Cross-Season Prompt Generation ✅

- [ ] Implement _generate_cross_season_prompt() method
- [ ] Create _enhanced_process_season_with_context() method
- [ ] Add character development milestone storage
- [ ] Integrate previous season context into AI prompts
- [ ] Update process_season() to use cross-season context

### Phase 4: CLI Integration ✅

- [ ] Add analyze-cross-season CLI command
- [ ] Add --include-context flag to create-season-summary
- [ ] Add cross-season analysis CLI handlers
- [ ] Update help text and documentation

### Phase 5: Advanced Vector Features ✅

- [ ] Implement enhanced season embeddings with SentenceTransformers
- [ ] Add semantic similarity search for character patterns
- [ ] Create character development trajectory analysis
- [ ] Add similar season discovery functionality

### Phase 6: Testing & Validation ✅

- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Cross-season continuity verified
- [ ] Manual testing with real show data
- [ ] Performance testing with multiple seasons

## 🎯 Library Integration Strategies

### 🧬 ChromaDB Advanced Vector Operations (`/chroma-core/chroma`)

**Enhanced Query Capabilities**:

```python
# Cross-season temporal filtering using ChromaDB metadata
results = collection.query(
    query_texts=["character development progression themes"],
    where={
        "$and": [
            {"show_name": {"$eq": show_name}},
            {"season": {"$lt": current_season}},  # Previous seasons only
            {"analysis_type": {"$eq": "season_analysis"}}
        ]
    },
    n_results=current_season - 1,
    include=["documents", "metadatas", "distances"]
)

# Character-specific historical queries
character_history = collection.query(
    query_texts=[f"{character_name} personality traits dialogue development"],
    where={
        "$and": [
            {"character_name": {"$eq": character_name}},
            {"show_name": {"$eq": show_name}}
        ]
    },
    n_results=100,
    include=["documents", "metadatas", "embeddings"]
)

# Semantic similarity search for character arc patterns
similar_arcs = collection.query(
    query_texts=["character transformation enemy to friend redemption"],
    where={"analysis_type": {"$eq": "character_arc_pattern"}},
    n_results=5,
    include=["documents", "distances"]
)
```

### 🔤 Sentence Transformers Semantic Enhancement (`/ukplab/sentence-transformers`)

**Multi-Dimensional Character Embeddings**:

```python
from sentence_transformers import SentenceTransformer, util

class EnhancedCharacterEmbedding:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def create_character_arc_embedding(self, character_data: Dict) -> List[float]:
        """Create rich embeddings for character development patterns."""
        
        # Multi-faceted embedding text
        embedding_text = f"""
        Character: {character_data['name']}
        Personality Evolution: {' -> '.join(character_data['trait_progression'])}
        Relationship Dynamics: {character_data['relationship_changes']}
        Growth Pattern: {character_data['development_trajectory']}
        Key Moments: {', '.join(character_data['pivotal_moments'])}
        Dialogue Themes: {character_data['dialogue_themes']}
        """
        
        return self.model.encode(embedding_text.strip()).tolist()
    
    def calculate_character_similarity(self, char1_embedding: List[float], 
                                     char2_embedding: List[float]) -> float:
        """Calculate semantic similarity between character development patterns."""
        similarity = util.cos_sim(char1_embedding, char2_embedding)
        return float(similarity[0][0])
    
    def find_character_development_patterns(self, query_pattern: str,
                                          character_embeddings: List[List[float]]) -> List[Dict]:
        """Find characters with similar development patterns using semantic search."""
        query_embedding = self.model.encode(query_pattern)
        
        similarities = util.cos_sim(query_embedding, character_embeddings)
        
        # Return top matches with similarity scores
        results = []
        for i, similarity in enumerate(similarities[0]):
            results.append({
                'character_index': i,
                'similarity_score': float(similarity),
                'pattern_match': similarity > 0.7  # Threshold for strong match
            })
        
        return sorted(results, key=lambda x: x['similarity_score'], reverse=True)
```

### 🧪 Enhanced Testing with Pytest and ChromaDB

**Advanced Test Fixtures**:

```python
@pytest.fixture(scope="session")
def persistent_character_db():
    """Session-scoped fixture for testing cross-season persistence."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_character_db"
        
        # Initialize with test data
        agent = CharacterAnalysisAgent(persist_directory=str(db_path))
        
        # Seed with test character data across multiple seasons
        test_characters = [
            {'name': 'Hero', 'season': 1, 'traits': ['naive', 'brave']},
            {'name': 'Hero', 'season': 2, 'traits': ['confident', 'brave', 'strategic']},
            {'name': 'Rival', 'season': 1, 'traits': ['arrogant', 'skilled']},
            {'name': 'Rival', 'season': 2, 'traits': ['humble', 'friendly', 'skilled']}
        ]
        
        for char_data in test_characters:
            agent.store_character_development_milestone(
                char_data['name'], 'Test Show', char_data['season'],
                char_data['traits'], 0.5 + char_data['season'] * 0.2
            )
        
        yield agent

@pytest.mark.parametrize("current_season,expected_previous_seasons", [
    (2, [1]), (3, [1, 2]), (4, [1, 2, 3])
])
def test_previous_season_context_scaling(persistent_character_db, current_season, expected_previous_seasons):
    """Test that previous season context scales correctly with season number."""
    context = persistent_character_db.get_previous_season_context('Test Show', current_season)
    
    assert context['current_season'] == current_season
    assert context['previous_seasons'] == expected_previous_seasons
    assert len(context['character_continuity']) >= len(expected_previous_seasons)
```

## 🚀 Advanced Implementation Features

### 📈 Character Development Trajectory Prediction

```python
def predict_character_development_trajectory(self, character_name: str, show_name: str,
                                           target_season: int) -> Dict:
    """
    Predict likely character development for future seasons based on historical patterns.
    
    Uses vector similarity with existing character arcs to predict development trends.
    """
    historical_data = self.get_character_historical_development(character_name, show_name)
    
    if len(historical_data) < 2:
        return {'prediction': 'insufficient_data'}
    
    # Analyze development velocity and direction
    recent_scores = [data['development_score'] for data in historical_data[-3:]]
    development_velocity = (recent_scores[-1] - recent_scores[0]) / len(recent_scores)
    
    # Predict future development score
    predicted_score = min(1.0, recent_scores[-1] + development_velocity)
    
    # Find similar character arcs for trait prediction
    current_pattern = f"Character with traits {', '.join(historical_data[-1]['traits'])} showing {development_velocity:.2f} development velocity"
    similar_arcs = self.find_similar_character_arcs(current_pattern, n_results=3)
    
    return {
        'character_name': character_name,
        'predicted_season': target_season,
        'predicted_development_score': predicted_score,
        'development_velocity': development_velocity,
        'confidence': min(0.8, len(historical_data) * 0.2),  # Higher confidence with more data
        'similar_character_patterns': similar_arcs['similar_arcs'][:2]
    }
```

### 🎭 Cross-Show Character Pattern Analysis

```python
def find_cross_show_character_patterns(self, character_archetype: str, 
                                     n_results: int = 5) -> Dict:
    """
    Find similar character development patterns across different anime shows.
    
    Uses semantic embeddings to identify character archetypes and development patterns
    that transcend individual shows, enabling broader narrative analysis.
    """
    try:
        # Search across all shows for similar character patterns
        results = self.development_collection.query(
            query_texts=[f"{character_archetype} character development personality traits growth"],
            where={"analysis_type": {"$in": ["character_milestone", "season_analysis"]}},
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        # Group by show to show cross-show patterns
        cross_show_patterns = {}
        for doc, meta, distance in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
            show = meta['show_name']
            if show not in cross_show_patterns:
                cross_show_patterns[show] = []
            
            cross_show_patterns[show].append({
                'season': meta.get('season', 'unknown'),
                'character': meta.get('character_name', 'unknown'),
                'similarity': 1.0 - distance,  # Convert distance to similarity
                'development_preview': doc[:200] + "..."
            })
        
        return {
            'archetype_query': character_archetype,
            'cross_show_patterns': cross_show_patterns,
            'total_matches': len(results['documents'][0]) if results['documents'] else 0
        }
        
    except Exception as e:
        logger.error(f"Failed to find cross-show character patterns: {e}")
        return {'archetype_query': character_archetype, 'cross_show_patterns': {}, 'total_matches': 0}
```

## 🎯 Success Criteria

1. **Cross-Season Context Retrieval** working via ChromaDB vector search
2. **Character Development Continuity** tracked across seasons automatically  
3. **Enhanced AI Prompts** include previous season character context
4. **Vector Storage Optimization** using Sentence Transformers for rich embeddings
5. **CLI Integration** for cross-season character analysis commands
6. **Performance Acceptable** for multi-season context retrieval (<2 seconds)
7. **TDD Methodology** followed with all tests passing before implementation
8. **Backward Compatibility** maintained for single-season processing

## 🔧 Technical Implementation Notes

### ChromaDB Collection Strategy

- **Reuse existing `development_collection`** for season analysis storage
- **Enhance metadata structure** with temporal and relationship fields
- **Add character milestone collection** for fine-grained development tracking
- **Implement semantic querying** with `$lt`, `$gt` for temporal filtering

### SentenceTransformers Optimization

- **Multi-faceted embeddings** combining character, plot, and theme data
- **Cosine similarity** for character development pattern matching
- **Semantic search** for cross-show character archetype analysis
- **Vector caching** for performance optimization with repeated queries

### Database Integration Strategy

- **ChromaDB for semantic search** (character patterns, similar arcs)
- **SQLite for structured data** (season summaries, metadata)
- **Hybrid approach** leveraging strengths of both storage types
- **Migration compatibility** with existing season summary data

## 📚 Library-Specific Implementation Details

### ChromaDB Advanced Querying (`/chroma-core/chroma`)

- **Temporal Metadata Filtering**: Use `{"season": {"$lt": current_season}}` for previous seasons
- **Multi-Collection Search**: Query both `character_profiles` and `development_collection`
- **Embedding Similarity**: Leverage ChromaDB's built-in cosine similarity for character pattern matching
- **Batch Operations**: Use `upsert` for efficient character milestone storage

### Sentence Transformers Semantic Analysis (`/ukplab/sentence-transformers`)

- **Model**: Continue using `all-MiniLM-L6-v2` for consistency with existing system
- **Multi-dimensional Embeddings**: Create embeddings for character traits, plot elements, and themes
- **Similarity Calculation**: Use `util.cos_sim()` for character development pattern comparison
- **Semantic Search**: Enable natural language queries for character development patterns

## 🎬 Expected Output Enhancement

### Before (Season 2 without context)

```
"Season 2 of My Hero Academia begins with Izuku at UA High School..."
```

### After (Season 2 with Season 1 context)

```
"Season 2 of My Hero Academia continues Izuku's journey from the timid, quirkless boy we met in Season 1 who has now grown into a confident UA student. Building on his Season 1 character development where he learned to harness One For All and gained the courage to face challenges, Season 2 shows how his relationship with Bakugo has evolved from pure antagonism to grudging respect..."
```

## 🚀 Future Enhancements

- **Cross-Show Character Archetype Analysis**: Find similar character types across different anime
- **Predictive Character Development**: Predict likely character arcs for future seasons
- **Relationship Network Evolution**: Track relationship networks across seasons
- **Thematic Continuity Analysis**: Identify recurring themes and their evolution
- **Multi-Modal Context**: Include visual and audio elements in cross-season context

---

**Estimated Implementation Time**: 3-4 days following TDD methodology
**Risk Level**: Medium (complex vector operations but solid foundation)
**Breaking Changes**: None (purely additive functionality)
**Library Dependencies**: Existing ChromaDB and Sentence Transformers (already in use)
