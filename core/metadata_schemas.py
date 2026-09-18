#!/usr/bin/env python3
"""
Standardized metadata schemas for ChromaDB storage.
Ensures consistent metadata structure across all vector database operations.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
from datetime import datetime
from .show_registry import show_registry

@dataclass 
class BaseMetadata:
    """
    Base metadata that all ChromaDB entries must include.
    
    Provides standardized metadata structure for all vector database
    entries ensuring consistent identification and searchability.
    """
    show_name: str          # Human-readable show name
    show_id: str           # Canonical show identifier
    season: int            # Season number
    episode: int           # Episode number  
    episode_key: str       # "my_hero_academia_S1E1"
    created_at: str        # ISO timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to ChromaDB metadata dictionary.
        
        Returns:
            Dictionary containing all metadata fields for ChromaDB storage
        """
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
        """
        Create validated base metadata.
        
        Args:
            show_name: Show name to validate and canonicalize
            season: Season number
            episode: Episode number
            
        Returns:
            Validated BaseMetadata instance with canonical naming
        """
        canonical_name = show_registry.validate_show_name(show_name)
        show_id = show_registry.get_show_id(show_name)
        episode_key = f"{show_id}_S{season}E{episode}"
        
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
    """
    Metadata for character profile entries.
    
    Extends BaseMetadata with character-specific information including
    dialogue statistics and personality trait data for character analysis.
    """
    character_name: str
    canonical_character_name: str
    dialogue_count: int
    personality_traits: str  # JSON string
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to ChromaDB metadata dictionary with character fields.
        
        Returns:
            Dictionary containing base and character-specific metadata fields
        """
        base = super().to_dict()
        base.update({
            "character_name": self.character_name,
            "canonical_character_name": self.canonical_character_name,
            "dialogue_count": self.dialogue_count,
            "personality_traits": self.personality_traits
        })
        return base
    
    @classmethod
    def create(cls, show_name: str, season: int, episode: int, 
               character_name: str, dialogue_count: int, personality_traits: List[str]) -> 'CharacterMetadata':
        """
        Create validated character metadata.
        
        Args:
            show_name: Show name to validate and canonicalize
            season: Season number
            episode: Episode number
            character_name: Name of the character
            dialogue_count: Number of dialogue lines for this character
            personality_traits: List of personality trait descriptions
            
        Returns:
            Validated CharacterMetadata instance
        """
        base = BaseMetadata.create(show_name, season, episode)
        
        return cls(
            show_name=base.show_name,
            show_id=base.show_id,
            season=base.season,
            episode=base.episode,
            episode_key=base.episode_key,
            created_at=base.created_at,
            character_name=character_name,
            canonical_character_name=character_name,  # For now, same as character_name
            dialogue_count=dialogue_count,
            personality_traits=json.dumps(personality_traits)
        )

@dataclass  
class InteractionMetadata(BaseMetadata):
    """
    Metadata for character interaction entries.
    
    Extends BaseMetadata with interaction-specific information including
    characters involved, interaction type, and significance scoring.
    """
    characters: str          # JSON list of character names
    interaction_type: str    # dialogue, conflict, cooperation
    emotional_tone: str      # positive, negative, neutral
    significance_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to ChromaDB metadata dictionary with interaction fields.
        
        Returns:
            Dictionary containing base and interaction-specific metadata fields
        """
        base = super().to_dict()
        base.update({
            "characters": self.characters,
            "interaction_type": self.interaction_type,
            "emotional_tone": self.emotional_tone,
            "significance_score": self.significance_score
        })
        return base
    
    @classmethod
    def create(cls, show_name: str, season: int, episode: int,
               characters: List[str], interaction_type: str, emotional_tone: str, 
               significance_score: float) -> 'InteractionMetadata':
        """
        Create validated interaction metadata.
        
        Args:
            show_name: Show name to validate and canonicalize
            season: Season number
            episode: Episode number
            characters: List of character names involved in interaction
            interaction_type: Type of interaction (dialogue, conflict, cooperation)
            emotional_tone: Emotional tone (positive, negative, neutral)
            significance_score: Significance score for the interaction
            
        Returns:
            Validated InteractionMetadata instance
        """
        base = BaseMetadata.create(show_name, season, episode)
        
        return cls(
            show_name=base.show_name,
            show_id=base.show_id,
            season=base.season,
            episode=base.episode,
            episode_key=base.episode_key,
            created_at=base.created_at,
            characters=json.dumps(characters),
            interaction_type=interaction_type,
            emotional_tone=emotional_tone,
            significance_score=significance_score
        )
