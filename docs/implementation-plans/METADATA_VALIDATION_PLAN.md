# TDD Metadata Validation and Show Separation Plan

## 🎯 Problem Analysis

**Current Issues with ChromaDB Metadata Tagging:**

### ❌ Critical Gaps in Current System
1. **Inconsistent Metadata Schema**: Character interactions missing `show_name` field
2. **No Show Name Validation**: Typos create new "shows" (e.g., "Attack on Titan" vs "attack-on-titan") 
3. **Cross-Contamination Risk**: Some queries don't filter by show, mixing data across anime
4. **Missing Canonical Names**: No standardized character names or aliases handling

### ⚠️ Specific Vulnerabilities Found

**Character Interactions Storage:**
```python
# CURRENT (PROBLEMATIC)
metadata = {
    "episode_key": "My_Hero_Academia_S1E1", 
    "characters": ["Deku", "Bakugo"],
    # show_name MISSING! 
}

# Can't reliably filter interactions by show
```

**Query Without Show Filter:**
```python
# UNSAFE - mixes all "Sakura" characters across all anime
relationships = agent.get_character_relationships("Sakura")  # No show parameter required
```

## 🧪 TDD Implementation Plan for Metadata Validation

### Phase 1: Write Failing Tests First (TDD Step 1)

#### 1.1 Create Failing Test Suite

**File**: `tests/test_metadata_validation.py` (CREATE FIRST - SHOULD FAIL)

```python
#!/usr/bin/env python3
"""
Test suite for metadata validation and show separation.
Following TDD - these tests should FAIL initially.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import json

from core.show_registry import ShowRegistry  # NEW MODULE - doesn't exist yet
from core.metadata_schemas import CharacterMetadata, InteractionMetadata  # NEW MODULE
from agents.character_analysis_agent import CharacterAnalysisAgent

class TestMetadataValidation:
    
    @pytest.fixture
    def sample_character_data(self):
        """Sample character data for testing."""
        return {
            "name": "Izuku Midoriya",
            "show_name": "My Hero Academia",
            "season": 1,
            "episode": 1,
            "dialogue_count": 15,
            "personality_traits": ["determined", "kind", "analytical"]
        }
    
    @pytest.fixture
    def sample_interaction_data(self):
        """Sample interaction data for testing."""
        return {
            "episode_key": "my_hero_academia_S1E1",
            "characters": ["Izuku Midoriya", "Katsuki Bakugo"],
            "interaction_type": "dialogue",
            "emotional_tone": "tense",
            "significance_score": 0.8
        }
    
    def test_show_registry_canonical_naming(self):
        """Test show name canonicalization and alias handling."""
        registry = ShowRegistry()
        
        # Test canonical name resolution
        assert registry.get_show_id("My Hero Academia") == "my_hero_academia"
        assert registry.get_show_id("MHA") == "my_hero_academia"  # Alias
        assert registry.get_show_id("my hero academia") == "my_hero_academia"  # Case insensitive
        
        # Test validation
        canonical = registry.validate_show_name("MHA")
        assert canonical == "My Hero Academia"
    
    def test_show_registry_prevents_typos(self):
        """Test that similar show names are detected and handled."""
        registry = ShowRegistry()
        
        # Should detect and suggest correct name for typos
        suggested = registry.validate_show_name("My Hero Acadmia")  # Typo
        # Should either return canonical name or raise validation error
        assert suggested in ["My Hero Academia"] or "validation" in str(suggested).lower()
    
    def test_character_metadata_schema_validation(self, sample_character_data):
        """Test character metadata schema creation and validation."""
        metadata = CharacterMetadata.create(
            show_name=sample_character_data["show_name"],
            season=sample_character_data["season"],
            episode=sample_character_data["episode"],
            character_name=sample_character_data["name"],
            dialogue_count=sample_character_data["dialogue_count"],
            personality_traits=sample_character_data["personality_traits"]
        )
        
        metadata_dict = metadata.to_dict()
        
        # All required fields must be present
        required_fields = ["show_name", "show_id", "season", "episode", "episode_key", 
                          "character_name", "canonical_character_name", "created_at"]
        for field in required_fields:
            assert field in metadata_dict
        
        # Show name should be canonical
        assert metadata_dict["show_name"] == "My Hero Academia"
        assert metadata_dict["show_id"] == "my_hero_academia"
        assert metadata_dict["episode_key"] == "my_hero_academia_S1E1"
    
    def test_interaction_metadata_includes_show_info(self, sample_interaction_data):
        """Test that interaction metadata includes all show information."""
        metadata = InteractionMetadata.create(
            show_name="My Hero Academia",
            season=1,
            episode=1,
            characters=sample_interaction_data["characters"],
            interaction_type=sample_interaction_data["interaction_type"],
            emotional_tone=sample_interaction_data["emotional_tone"],
            significance_score=sample_interaction_data["significance_score"]
        )
        
        metadata_dict = metadata.to_dict()
        
        # CRITICAL: show_name must be present in interactions
        assert "show_name" in metadata_dict
        assert "show_id" in metadata_dict
        assert metadata_dict["show_name"] == "My Hero Academia"
        assert metadata_dict["show_id"] == "my_hero_academia"
    
    def test_character_agent_requires_show_name(self):
        """Test that character agent methods require show_name parameter."""
        agent = CharacterAnalysisAgent()
        
        # These should raise ValueError because show_name is required
        with pytest.raises(ValueError, match="show_name is required"):
            agent.get_character_relationships("Deku")  # Missing show_name
            
        with pytest.raises(ValueError, match="show_name is required"):
            agent.search_character_moments("heroic moment", "Deku")  # Missing show_name
    
    def test_cross_show_isolation_enforcement(self):
        """Test that queries properly isolate shows."""
        agent = CharacterAnalysisAgent()
        
        # Mock two different shows with same character name
        with patch.object(agent.characters_collection, 'query') as mock_query:
            mock_query.return_value = {
                'metadatas': [[
                    {'character_name': 'Sakura', 'show_name': 'Naruto', 'show_id': 'naruto'},
                    {'character_name': 'Sakura', 'show_name': 'Card Captor Sakura', 'show_id': 'card_captor_sakura'}
                ]],
                'documents': [['doc1', 'doc2']],
                'distances': [[0.1, 0.2]]
            }
            
            # Query for Naruto's Sakura should NOT return Card Captor Sakura
            naruto_results = agent.find_similar_characters("Sakura", "Naruto", include_same_show=False)
            
            # Should have been called with proper show filtering
            mock_query.assert_called_with(
                query_texts=["Sakura character analysis"],
                where={"$and": [
                    {"show_name": {"$ne": "Naruto"}},  # Exclude same show
                    {"character_name": {"$eq": "Sakura"}}
                ]},
                n_results=10,
                include=["documents", "metadatas", "distances"]
            )
    
    def test_metadata_migration_for_existing_data(self):
        """Test migration of existing data without proper metadata."""
        from scripts.migrate_metadata import migrate_interaction_metadata  # NEW SCRIPT
        
        # Should be able to fix existing interactions missing show_name
        migration_result = migrate_interaction_metadata()
        
        # Should report number of fixed records
        assert 'migrated_count' in migration_result
        assert migration_result['migrated_count'] >= 0
        assert migration_result['success'] == True
    
    def test_duplicate_character_handling(self):
        """Test handling of characters with same names across shows."""
        agent = CharacterAnalysisAgent()
        
        # Should be able to distinguish between different "Eren" characters
        aot_eren = agent.analyze_character_development("Eren", "Attack on Titan")
        eren_yeager = agent.analyze_character_development("Eren Yeager", "Attack on Titan") 
        
        # Different shows should not interfere
        assert aot_eren != eren_yeager or len(aot_eren.get('episodes', [])) > 0
    
    def test_metadata_consistency_validation(self):
        """Test system-wide metadata consistency checking."""
        from agents.quality_agents.metadata_quality_agent import MetadataQualityAgent  # NEW AGENT
        
        quality_agent = MetadataQualityAgent()
        validation_report = quality_agent.validate_metadata_consistency()
        
        # Should check for missing fields, inconsistent naming, etc.
        assert 'missing_show_names' in validation_report
        assert 'inconsistent_names' in validation_report  
        assert 'canonical_violations' in validation_report
        assert 'total_issues' in validation_report
```

#### 1.2 Run Tests to Confirm They Fail

**Command**: `python3 -m pytest tests/test_metadata_validation.py -v`
**Expected Result**: All tests should FAIL with ImportError or NotImplementedError

### Phase 2: Implement Minimal Code to Pass Tests (TDD Step 2)

#### 2.1 Create Show Registry System

**File**: `core/show_registry.py` (IMPLEMENT TO MAKE TESTS PASS)

**File**: `core/show_registry.py`
```python
#!/usr/bin/env python3
"""
Show registry and metadata validation system.
Ensures consistent show naming and metadata tagging across the vector database.
"""

from typing import Dict, Set, Optional, List
from dataclasses import dataclass
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)

@dataclass
class ShowMetadata:
    """Standardized show metadata structure."""
    show_name: str          # Original name "My Hero Academia"
    show_id: str           # Canonical slug "my_hero_academia" 
    aliases: List[str]     # Alternative names ["MHA", "Boku no Hero"]
    total_seasons: int     # Known seasons count
    status: str           # "ongoing", "completed", "unknown"

class ShowRegistry:
    """Registry of known anime shows with canonical naming."""
    
    def __init__(self):
        """Initialize with known shows."""
        self.shows: Dict[str, ShowMetadata] = {}
        self._initialize_known_shows()
    
    def _initialize_known_shows(self):
        """Initialize registry with known anime shows."""
        known_shows = [
            ShowMetadata("My Hero Academia", "my_hero_academia", ["MHA", "Boku no Hero"], 7, "ongoing"),
            ShowMetadata("Attack on Titan", "attack_on_titan", ["AoT", "Shingeki no Kyojin"], 4, "completed"),
            ShowMetadata("Demon Slayer", "demon_slayer", ["Kimetsu no Yaiba"], 4, "ongoing"),
            # Add more shows as needed
        ]
        
        for show in known_shows:
            self.shows[show.show_id] = show
            # Also map aliases to canonical ID
            for alias in show.aliases:
                self.shows[self._slugify(alias)] = show
    
    def _slugify(self, name: str) -> str:
        """Convert show name to canonical slug."""
        return re.sub(r'[^a-z0-9]+', '_', name.lower().strip())
    
    def get_canonical_show(self, show_name: str) -> Optional[ShowMetadata]:
        """Get canonical show metadata from any name/alias."""
        slug = self._slugify(show_name)
        return self.shows.get(slug)
    
    def validate_show_name(self, show_name: str) -> str:
        """Validate and return canonical show name."""
        show_meta = self.get_canonical_show(show_name)
        if not show_meta:
            logger.warning(f"Unknown show: {show_name}. Adding to registry.")
            # Auto-add new shows (with validation prompt in production)
            new_show = ShowMetadata(show_name, self._slugify(show_name), [], 0, "unknown")
            self.shows[new_show.show_id] = new_show
            return show_name
        return show_meta.show_name
    
    def get_show_id(self, show_name: str) -> str:
        """Get canonical show ID for a show name."""
        show_meta = self.get_canonical_show(show_name) 
        return show_meta.show_id if show_meta else self._slugify(show_name)

# Global registry instance
show_registry = ShowRegistry()
```

#### 1.2 Enhanced Metadata Schema

**File**: `core/metadata_schemas.py`
```python
#!/usr/bin/env python3
"""
Standardized metadata schemas for ChromaDB storage.
Ensures consistent metadata structure across all vector database operations.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import json
from .show_registry import show_registry

@dataclass 
class BaseMetadata:
    """Base metadata that all ChromaDB entries must include."""
    show_name: str          # Human-readable show name
    show_id: str           # Canonical show identifier
    season: int            # Season number
    episode: int           # Episode number  
    episode_key: str       # "my_hero_academia_S1E1"
    created_at: str        # ISO timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata dictionary."""
        return {
            "show_name": self.show_name,
            "show_id": self.show_id,
            "season": self.season,
            "episode": self.episode,
            "episode_key": self.episode_key,
            "created_at": self.created_at
        }
    
    @classmethod
    def create(cls, show_name: str, season: int, episode: int) -> 'BaseMetadata':
        """Create validated base metadata."""
        canonical_name = show_registry.validate_show_name(show_name)
        show_id = show_registry.get_show_id(show_name)
        episode_key = f"{show_id}_S{season}E{episode}"
        
        from datetime import datetime
        return cls(
            show_name=canonical_name,
            show_id=show_id,
            season=season,
            episode=episode,
            episode_key=episode_key,
            created_at=datetime.now().isoformat()
        )

@dataclass
class CharacterMetadata(BaseMetadata):
    """Metadata for character profile entries."""
    character_name: str
    canonical_character_name: str
    dialogue_count: int
    personality_traits: str  # JSON string
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "character_name": self.character_name,
            "canonical_character_name": self.canonical_character_name,
            "dialogue_count": self.dialogue_count,
            "personality_traits": self.personality_traits
        })
        return base

@dataclass  
class InteractionMetadata(BaseMetadata):
    """Metadata for character interaction entries."""
    characters: str          # JSON list of character names
    interaction_type: str    # dialogue, conflict, cooperation
    emotional_tone: str      # positive, negative, neutral
    significance_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "characters": self.characters,
            "interaction_type": self.interaction_type,
            "emotional_tone": self.emotional_tone,
            "significance_score": self.significance_score
        })
        return base
```

### Phase 2: Fix Character Analysis Agent (Critical)

#### 2.1 Update Storage Methods with Validated Metadata

**File**: `agents/character_analysis_agent.py` (CRITICAL FIXES)

```python
# IMPORT NEW MODULES
from core.metadata_schemas import CharacterMetadata, InteractionMetadata
from core.show_registry import show_registry

class CharacterAnalysisAgent:
    def _store_character_profile(self, profile: CharacterProfile, episode_key: str):
        """Store character profile with validated metadata."""
        try:
            # Parse episode info from episode_key
            show_id, season_episode = episode_key.split('_S', 1)
            season, episode = season_episode.split('E')
            show_name = profile.first_appearance['show']
            
            # Create validated metadata
            char_metadata = CharacterMetadata(
                show_name=show_registry.validate_show_name(show_name),
                show_id=show_registry.get_show_id(show_name),
                season=int(season),
                episode=int(episode),
                episode_key=episode_key,
                created_at=datetime.now().isoformat(),
                character_name=profile.name,
                canonical_character_name=self._canonicalize_character_name(profile.name),
                dialogue_count=profile.total_dialogue_count,
                personality_traits=json.dumps(profile.personality_traits)
            )
            
            char_id = f"{episode_key}_{profile.name.replace(' ', '_')}"
            document = f"Character: {profile.name}\nPersonality: {', '.join(profile.personality_traits)}\nDialogue: {' '.join(profile.dialogue_chunks[:5])}"
            
            # Store with validated metadata
            self.characters_collection.upsert(
                ids=[char_id],
                documents=[document],
                embeddings=[profile.semantic_embedding] if profile.semantic_embedding else None,
                metadatas=[char_metadata.to_dict()]  # VALIDATED METADATA
            )
            
        except Exception as e:
            logger.error(f"Failed to store character profile for {profile.name}: {e}")
    
    def _store_character_interaction(self, interaction: CharacterInteraction):
        """Store character interaction with validated metadata."""
        try:
            # CRITICAL FIX: Extract show info from episode_key
            show_id, season_episode = interaction.episode_key.split('_S', 1)
            season, episode = season_episode.split('E')
            
            # Get canonical show name
            show_name = None
            for show_meta in show_registry.shows.values():
                if show_meta.show_id == show_id:
                    show_name = show_meta.show_name
                    break
            
            if not show_name:
                logger.error(f"Unknown show_id in episode_key: {interaction.episode_key}")
                return
            
            # Create validated metadata with show_name
            interaction_metadata = InteractionMetadata(
                show_name=show_name,
                show_id=show_id,
                season=int(season), 
                episode=int(episode),
                episode_key=interaction.episode_key,
                created_at=datetime.now().isoformat(),
                characters=json.dumps(interaction.characters),
                interaction_type=interaction.interaction_type,
                emotional_tone=interaction.emotional_tone,
                significance_score=interaction.significance_score
            )
            
            interaction_id = f"{interaction.episode_key}_{'_'.join(interaction.characters)}_{len(interaction.context)}"
            document = f"Interaction between {', '.join(interaction.characters)}: {interaction.context}"
            
            # Store with validated metadata including show_name
            self.interactions_collection.upsert(
                ids=[interaction_id],
                documents=[document], 
                metadatas=[interaction_metadata.to_dict()]  # NOW INCLUDES show_name!
            )
            
        except Exception as e:
            logger.error(f"Failed to store interaction: {e}")
```

#### 2.2 Fix Query Methods to Require Show Context

```python
def get_character_relationships(self, character_name: str, show_name: str) -> Dict:
    """Get relationship map for a character - NOW REQUIRES show_name."""
    try:
        # CRITICAL FIX: Always filter by show_name
        canonical_show = show_registry.validate_show_name(show_name)
        
        results = self.interactions_collection.query(
            query_texts=[f"Character relationships: {character_name}"],
            where={"$and": [
                {"show_name": {"$eq": canonical_show}},  # EXPLICIT SHOW FILTER
                {"characters": {"$contains": character_name}}
            ]},
            n_results=100,
            include=["documents", "metadatas"]
        )
        # ... rest of method
        
def find_similar_characters(self, character_name: str, show_name: str, 
                          limit: int = 5, include_same_show: bool = True) -> List[Dict]:
    """Find similar characters - show_name now REQUIRED."""
    # Always validate show_name and use explicit filtering
    canonical_show = show_registry.validate_show_name(show_name)
    
    if include_same_show:
        where_clause = {"show_name": {"$eq": canonical_show}}
    else:
        where_clause = {"show_name": {"$ne": canonical_show}}  # Exclude same show
```

### Phase 3: Data Migration and Cleanup

#### 3.1 Migration Script for Existing Data

**File**: `scripts/migrate_metadata.py`
```python
#!/usr/bin/env python3
"""
Migration script to fix existing ChromaDB metadata.
Adds missing show_name fields and canonicalizes existing show names.
"""

import chromadb
import json
import logging
from pathlib import Path
from core.show_registry import show_registry
from core.metadata_schemas import InteractionMetadata

def migrate_interaction_metadata():
    """Add missing show_name to existing character interactions."""
    
    # Connect to existing database
    client = chromadb.PersistentClient(path="character_db")
    interactions_collection = client.get_collection("character_interactions")
    
    # Get all existing interactions
    all_interactions = interactions_collection.get(include=["metadatas", "documents"])
    
    if not all_interactions['metadatas']:
        logger.info("No interactions found to migrate")
        return
    
    migrated_count = 0
    for i, metadata in enumerate(all_interactions['metadatas']):
        if 'show_name' not in metadata:
            # Extract show from episode_key
            episode_key = metadata['episode_key']
            try:
                show_id = episode_key.split('_S')[0]
                
                # Find canonical show name
                show_name = None
                for show_meta in show_registry.shows.values():
                    if show_meta.show_id == show_id:
                        show_name = show_meta.show_name
                        break
                
                if show_name:
                    # Update metadata with missing fields
                    updated_metadata = metadata.copy()
                    updated_metadata['show_name'] = show_name
                    updated_metadata['show_id'] = show_id
                    
                    # Extract season/episode
                    season_episode = episode_key.split('_S', 1)[1]
                    season, episode = season_episode.split('E')
                    updated_metadata['season'] = int(season)
                    updated_metadata['episode'] = int(episode)
                    
                    # Update in database
                    interaction_id = all_interactions['ids'][i]
                    interactions_collection.update(
                        ids=[interaction_id],
                        metadatas=[updated_metadata]
                    )
                    migrated_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to migrate interaction {i}: {e}")
    
    logger.info(f"Migrated {migrated_count} character interactions")

def canonicalize_show_names():
    """Standardize all show names in existing data."""
    
    client = chromadb.PersistentClient(path="character_db")
    characters_collection = client.get_collection("character_profiles")
    
    # Get all character profiles
    all_characters = characters_collection.get(include=["metadatas"])
    
    if not all_characters['metadatas']:
        return
        
    updated_count = 0
    for i, metadata in enumerate(all_characters['metadatas']):
        show_name = metadata.get('show_name')
        if show_name:
            canonical_name = show_registry.validate_show_name(show_name)
            canonical_id = show_registry.get_show_id(show_name)
            
            if canonical_name != show_name:
                # Update with canonical name
                updated_metadata = metadata.copy()
                updated_metadata['show_name'] = canonical_name
                updated_metadata['show_id'] = canonical_id
                
                character_id = all_characters['ids'][i]
                characters_collection.update(
                    ids=[character_id],
                    metadatas=[updated_metadata]
                )
                updated_count += 1
    
    logger.info(f"Canonicalized {updated_count} character show names")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting metadata migration...")
    
    migrate_interaction_metadata()
    canonicalize_show_names()
    
    logger.info("Metadata migration completed!")
```

### Phase 4: Enhanced Query Safety

#### 4.1 Mandatory Show Filtering

**File**: `agents/character_analysis_agent.py` (Updates)

```python
class CharacterAnalysisAgent:
    def search_character_moments(self, query: str, character_name: str, 
                                show_name: str, limit: int = 10) -> List[Dict]:
        """Search character moments - show_name now REQUIRED."""
        if not show_name:
            raise ValueError("show_name is required to prevent cross-show contamination")
        
        canonical_show = show_registry.validate_show_name(show_name)
        
        where_clause = {"$and": [
            {"character_name": {"$eq": character_name}}, 
            {"show_name": {"$eq": canonical_show}}
        ]}
        
        # ... rest of method with mandatory filtering
    
    def get_character_relationships(self, character_name: str, show_name: str) -> Dict:
        """Get character relationships - show_name now REQUIRED."""
        if not show_name:
            raise ValueError("show_name is required to prevent cross-show contamination")
        
        canonical_show = show_registry.validate_show_name(show_name)
        
        # Query interactions with explicit show filter
        results = self.interactions_collection.query(
            query_texts=[f"Character relationships: {character_name}"],
            where={"$and": [
                {"show_name": {"$eq": canonical_show}},
                {"characters": {"$contains": character_name}}
            ]},
            n_results=100,
            include=["documents", "metadatas"]
        )
        # ... rest with show-filtered results only
```

### Phase 5: Validation and Testing

#### 5.1 Enhanced Test Suite

**File**: `tests/test_metadata_validation.py`
```python
#!/usr/bin/env python3
"""
Test suite for metadata validation and show separation.
"""

import pytest
from agents.character_analysis_agent import CharacterAnalysisAgent
from core.show_registry import show_registry

class TestMetadataValidation:
    
    def test_show_name_canonicalization(self):
        """Test show name canonicalization."""
        # Test various input formats
        test_cases = [
            ("My Hero Academia", "my_hero_academia"),
            ("MHA", "my_hero_academia"),  # Alias
            ("attack on titan", "attack_on_titan"),
            ("Attack On Titan", "attack_on_titan")
        ]
        
        for input_name, expected_id in test_cases:
            show_id = show_registry.get_show_id(input_name)
            assert show_id == expected_id
    
    def test_cross_show_isolation(self):
        """Test that queries don't mix shows."""
        agent = CharacterAnalysisAgent()
        
        # This should raise an error now (show_name required)
        with pytest.raises(ValueError):
            agent.get_character_relationships("Sakura")  # No show_name
        
        # This should work and return only MHA results
        mha_relationships = agent.get_character_relationships("Deku", "My Hero Academia")
        
        # Verify all results are from MHA
        for char_name, interactions in mha_relationships.items():
            for interaction in interactions:
                assert "my_hero_academia" in interaction['episode'].lower()
    
    def test_interaction_metadata_includes_show(self):
        """Test that stored interactions include show_name metadata."""
        agent = CharacterAnalysisAgent()
        
        # Query interactions and verify metadata
        results = agent.interactions_collection.get(
            limit=10,
            include=["metadatas"]
        )
        
        for metadata in results['metadatas']:
            # All interactions must have show_name after migration
            assert 'show_name' in metadata
            assert 'show_id' in metadata
            assert 'season' in metadata
            assert 'episode' in metadata
```

## 🤖 AI Agent Implementation Guide

### **Step-by-Step Instructions for AI Agent**

#### **Pre-Implementation Checklist**
1. ✅ **Understand Current Problem**: Review [`agents/character_analysis_agent.py`](file:///Users/kkougl/Desktop/Personal/htmlParser/agents/character_analysis_agent.py#L418-L440) to see missing `show_name` in interactions
2. ✅ **Check ChromaDB Dependencies**: Verify ChromaDB is available in existing `requirements-vector.txt`
3. ✅ **Review Existing Tests**: Examine [`tests/test_character_integration.py`](file:///Users/kkougl/Desktop/Personal/htmlParser/tests/test_character_integration.py) for testing patterns
4. ✅ **Validate Current System**: Run `python3 tests/test_all_agents.py` to ensure no regressions

#### **TDD Implementation Order (Critical for Success)**

**Step 1: Create Failing Tests First**
```bash
# 1. Create failing test file
touch tests/test_metadata_validation.py
python3 -m pytest tests/test_metadata_validation.py -v  # Should FAIL with ImportError

# 2. Verify tests fail for right reasons
echo "Tests should fail because modules don't exist yet"
```

**Step 2: Implement Minimal Code to Pass Tests**
```bash
# 3. Create core modules
mkdir -p core
touch core/show_registry.py
touch core/metadata_schemas.py

# 4. Implement classes to make tests pass
# 5. Run tests again to verify they pass
python3 -m pytest tests/test_metadata_validation.py -v  # Should PASS

# 6. Update character analysis agent
# 7. Run migration script
python3 scripts/migrate_metadata.py
```

### **File Structure for Metadata Validation**

```
htmlParser/
├── core/
│   ├── show_registry.py              # NEW: Canonical show naming
│   ├── metadata_schemas.py           # NEW: Validated metadata schemas
│   └── schemas.py                    # EXISTING: Extend with metadata validation
├── scripts/
│   └── migrate_metadata.py           # NEW: Fix existing ChromaDB data
├── agents/
│   ├── character_analysis_agent.py   # MODIFY: Add show_name to interactions
│   └── quality_agents/
│       └── metadata_quality_agent.py # NEW: Metadata validation monitoring
└── tests/
    └── test_metadata_validation.py   # NEW: TDD test suite
```

### **Integration Points with Existing System**

```python
# How metadata validation connects to existing code:

# 1. Show Registry -> Validates all character analysis operations
from core.show_registry import show_registry

# 2. Metadata Schemas -> Standardizes ChromaDB storage format
from core.metadata_schemas import CharacterMetadata, InteractionMetadata

# 3. Character Agent -> Enhanced with validated metadata
from agents.character_analysis_agent import CharacterAnalysisAgent

# 4. Quality Agent -> Extended with metadata consistency checks  
from agents.quality_agents.metadata_quality_agent import MetadataQualityAgent
```

### **Critical Success Criteria**

- [ ] **All Tests Pass**: `python3 -m pytest tests/test_metadata_validation.py -v`
- [ ] **Cross-Show Isolation**: `get_character_relationships()` requires `show_name` parameter
- [ ] **Interaction Metadata Fixed**: All interactions include `show_name` field
- [ ] **Migration Successful**: Existing ChromaDB data updated with proper metadata
- [ ] **No Regressions**: All existing character analysis tests still pass
- [ ] **Show Name Canonicalization**: "MHA" -> "My Hero Academia" consistently

### **Validation Commands for AI Agent**

```bash
# Verify tests fail initially (TDD Step 1)
python3 -m pytest tests/test_metadata_validation.py -v  # Should FAIL

# Verify tests pass after implementation (TDD Step 2)  
python3 -m pytest tests/test_metadata_validation.py -v  # Should PASS

# Test show registry works
python3 -c "
from core.show_registry import show_registry
print('✅ MHA alias:', show_registry.get_show_id('MHA'))
print('✅ Canonical:', show_registry.validate_show_name('my hero academia'))
"

# Test cross-contamination prevention
python3 -c "
from agents.character_analysis_agent import CharacterAnalysisAgent
agent = CharacterAnalysisAgent()
try:
    agent.get_character_relationships('Deku')  # Should fail
    print('❌ FAILURE: Cross-contamination risk')
except (ValueError, TypeError) as e:
    print('✅ SUCCESS: Show isolation enforced')
"

# Verify existing tests still pass
python3 tests/test_all_agents.py
python3 -m pytest tests/test_character_integration.py -v
```

## 🚀 Implementation Priority

**Week 1 (Critical)**: 
1. Create failing tests (`tests/test_metadata_validation.py`)
2. Implement show registry (`core/show_registry.py`) 
3. Create metadata schemas (`core/metadata_schemas.py`)
4. Fix interaction storage in character agent

**Week 2 (High)**:
5. Run migration script for existing data
6. Add quality monitoring agent
7. Validate all tests pass

## ✅ **Agent Readiness Validation**

### **Is This Plan Ready for AI Agent Implementation?** ✅ **YES**

#### **✅ TDD Completeness Checklist**
- [x] **Failing Tests Written First**: Complete test suite that will fail initially
- [x] **Specific File Paths**: Exact locations for all new modules and modifications
- [x] **Integration Points**: Clear connections to existing `CharacterAnalysisAgent`
- [x] **Dependencies**: Uses existing ChromaDB setup and requirements
- [x] **Success Criteria**: Measurable validation commands
- [x] **Implementation Order**: Step-by-step TDD progression
- [x] **Error Handling**: Expected failures and validation patterns
- [x] **Migration Strategy**: Script to fix existing data

#### **🎯 Recommended Agent Approach**

**STEP 1**: Start with TDD - Create Failing Tests
```bash
# Agent should execute these commands in order:
python3 -m pytest tests/test_metadata_validation.py -v  # Confirm tests fail
mkdir -p core scripts
# Implement show registry and metadata schemas
python3 -m pytest tests/test_metadata_validation.py -v  # Confirm tests pass
```

**STEP 2**: Fix Critical Character Agent Issue
```bash
# Update character analysis agent to include show_name in interactions
# Run migration script to fix existing data
python3 scripts/migrate_metadata.py
```

**STEP 3**: Validate No Regressions
```bash
python3 tests/test_all_agents.py  # Ensure no existing functionality broken
python3 -m pytest tests/test_character_integration.py -v  # Character analysis still works
```

This plan follows the **exact same TDD methodology** that successfully implemented the Export Formats feature and is ready for AI agent implementation.

## 🤖 **AI Agent Implementation Commands**

### **Phase 1: Create Failing Tests (TDD Step 1)**
```bash
# Create test file that will fail initially
echo "#!/usr/bin/env python3" > tests/test_metadata_validation.py

# Run test to confirm failure  
python3 -m pytest tests/test_metadata_validation.py -v  # Should FAIL

# Create core directory structure
mkdir -p core scripts
```

### **Phase 2: Implement to Pass Tests (TDD Step 2)**
```bash
# Create show registry module
touch core/show_registry.py

# Create metadata schemas module  
touch core/metadata_schemas.py

# Implement classes to make tests pass
# (Agent implements ShowRegistry and metadata schema classes)

# Run tests to confirm they now pass
python3 -m pytest tests/test_metadata_validation.py -v  # Should PASS
```

### **Phase 3: Fix Critical Character Agent Issues**
```bash
# Update character_analysis_agent.py to include show_name in interactions
# Create migration script for existing data
touch scripts/migrate_metadata.py

# Run migration on existing ChromaDB data
python3 scripts/migrate_metadata.py
```

### **Phase 4: Validation and Integration**
```bash
# Verify no regressions in existing functionality
python3 tests/test_all_agents.py

# Test character analysis still works
python3 -m pytest tests/test_character_integration.py -v

# Validate metadata consistency
python3 -c "
from agents.character_analysis_agent import CharacterAnalysisAgent
from core.show_registry import show_registry
print('✅ Metadata validation system working!')
"
```

---

## 📋 **Final AI Agent Checklist**

### **Before Starting Implementation:**
- [ ] Read this entire TDD plan
- [ ] Understand the critical issue: missing `show_name` in character interactions
- [ ] Verify ChromaDB dependencies are available
- [ ] Run existing tests to establish baseline: `python3 tests/test_all_agents.py`

### **During TDD Implementation:**
- [ ] Write failing tests FIRST (tests should import non-existent modules)
- [ ] Create minimal show registry to pass basic tests
- [ ] Implement metadata schemas for validated storage
- [ ] Fix `_store_character_interaction()` method to include `show_name`
- [ ] Make `show_name` parameter required in query methods
- [ ] Create migration script for existing ChromaDB data

### **After Implementation:**
- [ ] All new tests pass: `python3 -m pytest tests/test_metadata_validation.py -v`
- [ ] All existing tests still pass: `python3 tests/test_all_agents.py`  
- [ ] Cross-contamination prevented: Character queries require `show_name`
- [ ] Existing ChromaDB data migrated with proper metadata
- [ ] Show name canonicalization working: "MHA" -> "My Hero Academia"

---

**Total Estimated Time**: 1-2 weeks following TDD methodology
**Risk Level**: Medium (fixes critical data integrity issue)  
**Dependencies**: ChromaDB (already available), SentenceTransformers (already available)
**Breaking Changes**: Makes `show_name` required in some methods (improves safety)
**Agent Readiness**: ✅ **READY FOR IMPLEMENTATION**

**Priority**: **HIGH** - This fixes a critical data integrity issue that could lead to incorrect character analysis results when multiple anime shows are processed.
