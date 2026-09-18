#!/usr/bin/env python3
"""
Metadata Quality Agent for validating ChromaDB metadata consistency.
"""

import chromadb
import logging
from typing import Dict, List
from core.show_registry import show_registry

logger = logging.getLogger(__name__)

class MetadataQualityAgent:
    """Agent for validating metadata consistency across ChromaDB collections."""
    
    def __init__(self):
        """Initialize metadata quality agent."""
        try:
            self.client = chromadb.PersistentClient(path="data/databases/character_db")
            self.characters_collection = self.client.get_collection("character_profiles")
            self.interactions_collection = self.client.get_collection("character_interactions")
        except Exception as e:
            logger.warning(f"ChromaDB not available for metadata validation: {e}")
            self.client = None
    
    def validate_metadata_consistency(self) -> Dict:
        """Validate metadata consistency across all collections."""
        if not self.client:
            return {
                'missing_show_names': 0,
                'inconsistent_names': 0,
                'canonical_violations': 0,
                'total_issues': 0
            }
        
        try:
            # Check character profiles
            char_results = self.characters_collection.get(include=["metadatas"])
            interaction_results = self.interactions_collection.get(include=["metadatas"])
            
            missing_show_names = 0
            inconsistent_names = 0
            canonical_violations = 0
            
            # Check interactions for missing show_name
            if interaction_results['metadatas'] is not None and len(interaction_results['metadatas']) > 0:
                for metadata in interaction_results['metadatas']:
                    if 'show_name' not in metadata:
                        missing_show_names += 1
                    elif metadata.get('show_name'):
                        # Check if name matches canonical
                        show_name = metadata['show_name']
                        canonical = show_registry.validate_show_name(show_name)
                        if canonical != show_name:
                            canonical_violations += 1
            
            # Check character profiles for consistency
            if char_results['metadatas'] is not None and len(char_results['metadatas']) > 0:
                for metadata in char_results['metadatas']:
                    if 'show_name' not in metadata:
                        missing_show_names += 1
                    elif metadata.get('show_name'):
                        show_name = metadata['show_name']
                        canonical = show_registry.validate_show_name(show_name)
                        if canonical != show_name:
                            canonical_violations += 1
            
            total_issues = missing_show_names + inconsistent_names + canonical_violations
            
            return {
                'missing_show_names': missing_show_names,
                'inconsistent_names': inconsistent_names,
                'canonical_violations': canonical_violations,
                'total_issues': total_issues
            }
            
        except Exception as e:
            logger.error(f"Metadata validation failed: {e}")
            return {
                'missing_show_names': 0,
                'inconsistent_names': 0,
                'canonical_violations': 0,
                'total_issues': 0,
                'error': str(e)
            }
