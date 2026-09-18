#!/usr/bin/env python3
"""
Migration script to fix existing ChromaDB metadata.
Adds missing show_name fields and canonicalizes existing show names.
"""

import sys
from pathlib import Path
import chromadb
import json
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.show_registry import show_registry
from core.metadata_schemas import InteractionMetadata

logger = logging.getLogger(__name__)

def migrate_interaction_metadata():
    """Add missing show_name to existing character interactions.
    
    This function migrates existing character interaction metadata by adding
    missing show_name fields and canonicalizing existing show names using
    the show registry.
    
    Returns:
        dict: Migration result containing success status and count of migrated records.
            - success (bool): True if migration completed successfully
            - migrated_count (int): Number of interactions migrated
            - error (str, optional): Error message if migration failed
    """
    
    try:
        # Connect to existing database
        client = chromadb.PersistentClient(path="data/databases/character_db")
        interactions_collection = client.get_collection("character_interactions")
        
        # Get all existing interactions
        all_interactions = interactions_collection.get(include=["metadatas", "documents"])
        
        if all_interactions['metadatas'] is None or len(all_interactions['metadatas']) == 0:
            logger.info("No interactions found to migrate")
            return {"success": True, "migrated_count": 0}
        
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
        return {"success": True, "migrated_count": migrated_count}
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return {"success": False, "migrated_count": 0, "error": str(e)}

def canonicalize_show_names():
    """Standardize all show names in existing data.
    
    This function updates all character profiles to use canonical show names
    as defined in the show registry. This ensures consistency across the
    database and prevents issues with show name variations.
    
    Returns:
        None
        
    Raises:
        Exception: If canonicalization fails due to database or registry errors.
    """
    
    try:
        client = chromadb.PersistentClient(path="data/databases/character_db")
        characters_collection = client.get_collection("character_profiles")
        
        # Get all character profiles
        all_characters = characters_collection.get(include=["metadatas"])
        
        if all_characters['metadatas'] is None or len(all_characters['metadatas']) == 0:
            logger.info("No character profiles found to canonicalize")
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
        
    except Exception as e:
        logger.error(f"Canonicalization failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting metadata migration...")
    
    migrate_interaction_metadata()
    canonicalize_show_names()
    
    logger.info("Metadata migration completed!")
