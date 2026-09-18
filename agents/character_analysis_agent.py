#!/usr/bin/env python3
"""
Character Analysis Agent using Chroma Vector Database

This agent provides advanced character analysis capabilities by leveraging
Chroma's vector database for semantic character understanding, relationship
mapping, and character development tracking across episodes.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
import json

try:
    import chromadb
    from chromadb.config import Settings
    from core.metadata_schemas import CharacterMetadata, InteractionMetadata
    from core.show_registry import show_registry
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CharacterProfile:
    """Represents a character's profile with vector embeddings."""
    name: str
    canonical_name: str  # Standardized name (e.g., "Midoriya Izuku" instead of "Deku")
    aliases: List[str]  # Alternative names/nicknames
    dialogue_chunks: List[str]  # Character's dialogue excerpts
    personality_traits: List[str]  # Extracted personality traits
    relationships: Dict[str, float]  # Character relationships with similarity scores
    character_arc: List[Dict]  # Character development over episodes
    first_appearance: Dict  # First episode appearance
    total_dialogue_count: int
    shows: Set[str]  # Shows this character appears in
    semantic_embedding: Optional[List[float]] = None  # Vector representation


@dataclass
class CharacterInteraction:
    """Represents an interaction between characters."""
    episode_key: str  # "ShowName_S1E1"
    characters: List[str]
    interaction_type: str  # dialogue, conflict, cooperation, etc.
    context: str  # Surrounding text context
    emotional_tone: str  # positive, negative, neutral, tense, etc.
    significance_score: float  # 0-1, how important this interaction is


class CharacterAnalysisAgent:
    """
    Advanced character analysis using Chroma vector database.
    
    This agent provides:
    - Character extraction and profiling from transcripts
    - Character relationship mapping using semantic similarity
    - Character development tracking across episodes
    - Personality analysis using dialogue patterns
    - Character arc visualization and insights
    """
    
    def __init__(self, persist_directory: str = "data/databases/character_db"):
        """
        Initialize the character analysis agent.
        
        Sets up ChromaDB collections, sentence transformers for embeddings,
        character extraction patterns, and personality analysis keywords.
        
        Args:
            persist_directory (str): Directory path for ChromaDB persistence
            
        Raises:
            ImportError: If ChromaDB is not available
        """
        if not CHROMA_AVAILABLE:
            raise ImportError("ChromaDB not available. Install with: pip install chromadb")
        
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(exist_ok=True)
        
        # Initialize sentence transformer for embeddings
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        else:
            logger.warning("SentenceTransformers not available. Character embeddings disabled.")
            self.encoder = None
        
        # Initialize ChromaDB collections
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Collections for different aspects of character analysis
        self._initialize_collections()
        
        # Character name patterns for extraction
        self.character_patterns = [
            re.compile(r'^([A-Z][A-Za-z\s\-\'\.]+?)(?:\s*\([^)]*\))?\s*:', re.MULTILINE),  # Dialogue
            re.compile(r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\b'),  # Names in text
            re.compile(r'(?:[\[\(]([A-Z][A-Za-z\s]+?)[\]\)])')  # Names in brackets/parentheses
        ]
        
        # Common false positives to filter out
        self.false_positives = {
            'SCENE', 'CUT TO', 'FADE IN', 'FADE OUT', 'INT', 'EXT', 'NARRATOR',
            'VOICE', 'FLASHBACK', 'TITLE CARD', 'OPENING', 'ENDING', 'CREDITS',
            'EPISODE', 'MHA', 'BNHA', 'PRESENT', 'PAST', 'ALL', 'ONE', 'FOR',
            'MY', 'HERO', 'ACADEMIA', 'ATTACK', 'TITAN', 'DEMON', 'SLAYER'
        }
        
        # Personality trait keywords for analysis
        self.personality_keywords = {
            'determined': ['determined', 'persistent', 'never give up', 'won\'t quit'],
            'kind': ['kind', 'caring', 'gentle', 'compassionate', 'helpful'],
            'brave': ['brave', 'courageous', 'fearless', 'heroic', 'bold'],
            'intelligent': ['smart', 'clever', 'brilliant', 'genius', 'analytical'],
            'stubborn': ['stubborn', 'headstrong', 'obstinate', 'refuses to'],
            'loyal': ['loyal', 'faithful', 'devoted', 'stands by', 'supports'],
            'confident': ['confident', 'self-assured', 'believes in', 'certain'],
            'anxious': ['worried', 'nervous', 'anxious', 'uncertain', 'doubts'],
            'hot-tempered': ['angry', 'explosive', 'rage', 'furious', 'heated'],
            'calm': ['calm', 'composed', 'peaceful', 'serene', 'collected']
        }
        
        logger.info("Character Analysis Agent initialized with ChromaDB backend")
    
    def _initialize_collections(self):
        """
        Initialize ChromaDB collections for character analysis.
        
        Creates and configures collections for character profiles, interactions,
        and character development tracking.
        
        Raises:
            Exception: If collection initialization fails
        """
        try:
            # Character profiles collection
            self.characters_collection = self.client.get_or_create_collection(
                name="character_profiles",
                metadata={"description": "Character profiles with dialogue and personality embeddings"}
            )
            
            # Character interactions collection
            self.interactions_collection = self.client.get_or_create_collection(
                name="character_interactions",
                metadata={"description": "Character interactions and relationships"}
            )
            
            # Character development collection (tracks changes over time)
            self.development_collection = self.client.get_or_create_collection(
                name="character_development",
                metadata={"description": "Character development arcs across episodes"}
            )
            
            logger.info("ChromaDB collections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB collections: {e}")
            raise
    
    def analyze_episode_characters(self, show_name: str, season: int, episode: int, 
                                 transcript: str) -> Dict[str, CharacterProfile]:
        """
        Analyze characters in a specific episode.
        
        Args:
            show_name: Name of the show
            season: Season number
            episode: Episode number
            transcript: Episode transcript text
            
        Returns:
            Dictionary mapping character names to their profiles
        """
        episode_key = f"{show_name}_S{season}E{episode}"
        logger.info(f"Analyzing characters for {episode_key}")
        
        # Extract character dialogues
        character_dialogues = self._extract_character_dialogues(transcript)
        
        # Create character profiles
        character_profiles = {}
        for char_name, dialogues in character_dialogues.items():
            profile = self._create_character_profile(
                char_name, dialogues, show_name, season, episode
            )
            character_profiles[char_name] = profile
            
            # Store in vector database
            self._store_character_profile(profile, episode_key)
        
        # Analyze character interactions
        interactions = self._analyze_character_interactions(
            character_dialogues, transcript, episode_key
        )
        
        # Store interactions in database
        for interaction in interactions:
            self._store_character_interaction(interaction)
        
        # Update character relationships
        self._update_character_relationships(character_profiles, interactions)
        
        logger.info(f"Analyzed {len(character_profiles)} characters and {len(interactions)} interactions")
        return character_profiles
    
    def _extract_character_dialogues(self, transcript: str) -> Dict[str, List[str]]:
        """
        Extract dialogue by character from transcript.
        
        Parses the transcript to identify character names and their associated
        dialogue lines, filtering out false positives and cleaning character names.
        
        Args:
            transcript (str): Raw episode transcript text
            
        Returns:
            Dict[str, List[str]]: Dictionary mapping character names to their dialogue lines
        """
        character_dialogues = defaultdict(list)
        
        # Split transcript into lines
        lines = transcript.split('\n')
        current_speaker = None
        current_dialogue = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line starts with a character name
            dialogue_match = self.character_patterns[0].match(line)
            if dialogue_match:
                # Save previous dialogue if exists
                if current_speaker and current_dialogue:
                    dialogue_text = ' '.join(current_dialogue).strip()
                    if len(dialogue_text) > 10:  # Filter out very short dialogues
                        character_dialogues[current_speaker].append(dialogue_text)
                
                # Start new dialogue
                current_speaker = dialogue_match.group(1).strip()
                current_dialogue = [line[len(dialogue_match.group(0)):].strip()]
            else:
                # Continue current dialogue
                if current_speaker:
                    current_dialogue.append(line)
        
        # Don't forget the last dialogue
        if current_speaker and current_dialogue:
            dialogue_text = ' '.join(current_dialogue).strip()
            if len(dialogue_text) > 10:
                character_dialogues[current_speaker].append(dialogue_text)
        
        # Filter out false positives and clean names
        cleaned_dialogues = {}
        for char_name, dialogues in character_dialogues.items():
            cleaned_name = self._clean_character_name(char_name)
            if cleaned_name and cleaned_name not in self.false_positives:
                cleaned_dialogues[cleaned_name] = dialogues
        
        return cleaned_dialogues
    
    def _clean_character_name(self, name: str) -> Optional[str]:
        """
        Clean and standardize character names.
        
        Removes brackets, parentheses, titles, and validates that the name
        is likely a character name rather than a stage direction.
        
        Args:
            name (str): Raw character name to clean
            
        Returns:
            Optional[str]: Cleaned character name or None if invalid
        """
        if not name:
            return None
        
        # Remove common prefixes/suffixes
        name = re.sub(r'\(.*?\)', '', name).strip()
        name = re.sub(r'\[.*?\]', '', name).strip()
        
        # Remove titles
        name = re.sub(r'^(Mr|Mrs|Dr|Professor|Principal|Teacher|Student)\s+', '', name)
        
        # Check if it's likely a character name
        if len(name) < 2 or len(name) > 50:
            return None
        
        if not re.match(r'^[A-Za-z\s\-\'\.]+$', name):
            return None
        
        return name.title()
    
    def _create_character_profile(self, name: str, dialogues: List[str], 
                                show_name: str, season: int, episode: int) -> CharacterProfile:
        """Create a character profile from their dialogues."""
        # Combine all dialogues for analysis
        all_dialogue = ' '.join(dialogues)
        
        # Extract personality traits
        personality_traits = self._extract_personality_traits(all_dialogue)
        
        # Generate semantic embedding
        embedding = None
        if self.encoder:
            # Combine character name with dialogue for context-aware embedding
            embedding_text = f"{name}: {all_dialogue[:1000]}"  # Limit for efficiency
            embedding = self.encoder.encode(embedding_text).tolist()
        
        return CharacterProfile(
            name=name,
            canonical_name=name,  # TODO: Implement name standardization
            aliases=[],  # TODO: Detect aliases
            dialogue_chunks=dialogues,
            personality_traits=personality_traits,
            relationships={},
            character_arc=[],
            first_appearance={'show': show_name, 'season': season, 'episode': episode},
            total_dialogue_count=len(dialogues),
            shows={show_name},
            semantic_embedding=embedding
        )
    
    def _extract_personality_traits(self, dialogue: str) -> List[str]:
        """Extract personality traits from character dialogue."""
        traits = []
        dialogue_lower = dialogue.lower()
        
        for trait, keywords in self.personality_keywords.items():
            score = sum(dialogue_lower.count(keyword) for keyword in keywords)
            if score > 0:
                traits.append(trait)
        
        return traits
    
    def _analyze_character_interactions(self, character_dialogues: Dict[str, List[str]], 
                                      transcript: str, episode_key: str) -> List[CharacterInteraction]:
        """Analyze interactions between characters."""
        interactions = []
        
        # Find scenes where multiple characters speak
        lines = transcript.split('\n')
        scene_characters = []
        scene_context = []
        
        for line in lines:
            line = line.strip()
            if not line:
                # Scene break - analyze accumulated characters
                if len(scene_characters) > 1:
                    interaction = self._create_interaction(
                        scene_characters, scene_context, episode_key
                    )
                    if interaction:
                        interactions.append(interaction)
                
                scene_characters = []
                scene_context = []
                continue
            
            # Check if line has character dialogue
            dialogue_match = self.character_patterns[0].match(line)
            if dialogue_match:
                char_name = self._clean_character_name(dialogue_match.group(1))
                if char_name and char_name not in self.false_positives:
                    if char_name not in scene_characters:
                        scene_characters.append(char_name)
            
            scene_context.append(line)
        
        return interactions
    
    def _create_interaction(self, characters: List[str], context: List[str], 
                          episode_key: str) -> Optional[CharacterInteraction]:
        """Create a character interaction from scene context."""
        if len(characters) < 2:
            return None
        
        context_text = ' '.join(context)
        
        # Determine interaction type (simple heuristics)
        interaction_type = "dialogue"
        if any(word in context_text.lower() for word in ['fight', 'battle', 'attack', 'punch']):
            interaction_type = "conflict"
        elif any(word in context_text.lower() for word in ['help', 'support', 'together', 'team']):
            interaction_type = "cooperation"
        
        # Determine emotional tone
        emotional_tone = "neutral"
        if any(word in context_text.lower() for word in ['angry', 'mad', 'furious', 'rage']):
            emotional_tone = "negative"
        elif any(word in context_text.lower() for word in ['happy', 'smile', 'laugh', 'joy']):
            emotional_tone = "positive"
        elif any(word in context_text.lower() for word in ['tense', 'serious', 'worried']):
            emotional_tone = "tense"
        
        # Calculate significance score (length and keyword-based)
        significance_score = min(1.0, len(context_text) / 1000.0)
        if interaction_type != "dialogue":
            significance_score += 0.3
        
        return CharacterInteraction(
            episode_key=episode_key,
            characters=characters,
            interaction_type=interaction_type,
            context=context_text[:500],  # Limit length
            emotional_tone=emotional_tone,
            significance_score=significance_score
        )
    
    def _store_character_profile(self, profile: CharacterProfile, episode_key: str):
        """Store character profile in ChromaDB."""
        try:
            char_id = f"{episode_key}_{profile.name.replace(' ', '_')}"
            
            # Prepare metadata
            metadata = {
                "character_name": profile.name,
                "episode_key": episode_key,
                "show_name": profile.first_appearance['show'],
                "season": profile.first_appearance['season'],
                "episode": profile.first_appearance['episode'],
                "dialogue_count": profile.total_dialogue_count,
                "personality_traits": json.dumps(profile.personality_traits)
            }
            
            # Combine dialogues for document
            document = f"Character: {profile.name}\nPersonality: {', '.join(profile.personality_traits)}\nDialogue: {' '.join(profile.dialogue_chunks[:5])}"
            
            # Store in collection
            self.characters_collection.upsert(
                ids=[char_id],
                documents=[document],
                embeddings=[profile.semantic_embedding] if profile.semantic_embedding else None,
                metadatas=[metadata]
            )
            
        except Exception as e:
            logger.error(f"Failed to store character profile for {profile.name}: {e}")
    
    def _store_character_interaction(self, interaction: CharacterInteraction):
        """Store character interaction in ChromaDB."""
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
            interaction_metadata = InteractionMetadata.create(
                show_name=show_name,
                season=int(season), 
                episode=int(episode),
                characters=interaction.characters,
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
    
    def _update_character_relationships(self, profiles: Dict[str, CharacterProfile], 
                                      interactions: List[CharacterInteraction]):
        """Update character relationships based on interactions."""
        for interaction in interactions:
            characters = interaction.characters
            
            # Calculate relationship score based on interaction
            base_score = interaction.significance_score
            
            # Adjust based on interaction type and tone
            if interaction.interaction_type == "cooperation":
                base_score += 0.2
            elif interaction.interaction_type == "conflict":
                base_score -= 0.1
            
            if interaction.emotional_tone == "positive":
                base_score += 0.1
            elif interaction.emotional_tone == "negative":
                base_score -= 0.1
            
            # Update relationships between all character pairs
            for i, char1 in enumerate(characters):
                for char2 in characters[i+1:]:
                    if char1 in profiles:
                        profiles[char1].relationships[char2] = profiles[char1].relationships.get(char2, 0) + base_score
                    if char2 in profiles:
                        profiles[char2].relationships[char1] = profiles[char2].relationships.get(char1, 0) + base_score
    
    def find_similar_characters(self, character_name: str, show_name: str, 
                               limit: int = 5, include_same_show: bool = True) -> List[Dict]:
        """Find characters similar to the given character using vector similarity."""
        if not show_name:
            raise ValueError("show_name is required to prevent cross-show contamination")
        
        try:
            canonical_show = show_registry.validate_show_name(show_name)
            
            # Build where clause based on include_same_show
            if include_same_show:
                where_clause = {"show_name": {"$eq": canonical_show}}
            else:
                where_clause = {"$and": [
                    {"show_name": {"$ne": canonical_show}},  # Exclude same show
                    {"character_name": {"$eq": character_name}}
                ]}
            
            # Search for similar characters
            results = self.characters_collection.query(
                query_texts=[f"{character_name} character analysis"],
                where=where_clause,
                n_results=limit + 5,  # Get extra to filter out the same character
                include=["documents", "metadatas", "distances"]
            )
            
            similar_chars = []
            if results['documents'] is not None and len(results['documents']) > 0 and results['documents'][0]:
                for doc, meta, distance in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                    # Skip the same character
                    if meta['character_name'] == character_name and (not show_name or meta['show_name'] == show_name):
                        continue
                    
                    similar_chars.append({
                        'character_name': meta['character_name'],
                        'show_name': meta['show_name'],
                        'similarity_score': 1 - distance,
                        'personality_traits': json.loads(meta.get('personality_traits', '[]')),
                        'dialogue_count': meta['dialogue_count']
                    })
            
            return similar_chars[:limit]
            
        except Exception as e:
            logger.error(f"Failed to find similar characters for {character_name}: {e}")
            return []
    
    def analyze_character_development(self, character_name: str, show_name: str) -> Dict:
        """Analyze how a character develops across episodes."""
        try:
            # Get all episodes featuring this character
            results = self.characters_collection.query(
                query_texts=[f"Character: {character_name}"],
                where={"$and": [{"character_name": {"$eq": character_name}}, {"show_name": {"$eq": show_name}}]},
                n_results=100,
                include=["documents", "metadatas"]
            )
            
            if results['metadatas'] is None or len(results['metadatas']) == 0 or not results['metadatas'][0]:
                return {'error': 'Character not found'}
            
            # Sort by episode order
            episodes = []
            for meta in results['metadatas'][0]:
                episodes.append({
                    'season': meta['season'],
                    'episode': meta['episode'],
                    'dialogue_count': meta['dialogue_count'],
                    'personality_traits': json.loads(meta.get('personality_traits', '[]'))
                })
            
            episodes.sort(key=lambda x: (x['season'], x['episode']))
            
            # Analyze development trends
            development_analysis = {
                'character_name': character_name,
                'show_name': show_name,
                'total_episodes': len(episodes),
                'first_appearance': episodes[0] if episodes else None,
                'latest_appearance': episodes[-1] if episodes else None,
                'dialogue_trend': [ep['dialogue_count'] for ep in episodes],
                'personality_evolution': self._analyze_personality_evolution(episodes),
                'development_score': self._calculate_development_score(episodes)
            }
            
            return development_analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze character development for {character_name}: {e}")
            return {'error': str(e)}
    
    def _analyze_personality_evolution(self, episodes: List[Dict]) -> Dict:
        """Analyze how personality traits change over episodes."""
        trait_timeline = defaultdict(list)
        
        for i, ep in enumerate(episodes):
            traits = ep['personality_traits']
            for trait in self.personality_keywords.keys():
                trait_timeline[trait].append(1 if trait in traits else 0)
        
        # Calculate trait development
        evolution = {}
        for trait, timeline in trait_timeline.items():
            if any(timeline):  # Only include traits that appear
                evolution[trait] = {
                    'first_third': sum(timeline[:len(timeline)//3]) / max(1, len(timeline)//3),
                    'last_third': sum(timeline[-len(timeline)//3:]) / max(1, len(timeline)//3),
                    'trend': 'increasing' if sum(timeline[-len(timeline)//3:]) > sum(timeline[:len(timeline)//3]) else 'stable'
                }
        
        return evolution
    
    def _calculate_development_score(self, episodes: List[Dict]) -> float:
        """Calculate a character development score (0-1)."""
        if len(episodes) < 2:
            return 0.0
        
        # Factors: dialogue growth, personality trait diversity, consistency
        dialogue_growth = (episodes[-1]['dialogue_count'] - episodes[0]['dialogue_count']) / max(1, episodes[0]['dialogue_count'])
        dialogue_growth = max(0, min(1, dialogue_growth))  # Normalize to 0-1
        
        # Trait diversity
        all_traits = set()
        for ep in episodes:
            all_traits.update(ep['personality_traits'])
        trait_diversity = min(1.0, len(all_traits) / 5.0)  # Normalize to 0-1
        
        # Consistency (characters should appear in multiple episodes)
        consistency = min(1.0, len(episodes) / 10.0)  # More episodes = more developed
        
        return (dialogue_growth * 0.3 + trait_diversity * 0.4 + consistency * 0.3)
    
    def get_character_relationships(self, character_name: str, show_name: str) -> Dict:
        """Get relationship map for a character."""
        if not show_name:
            raise ValueError("show_name is required to prevent cross-show contamination")
        
        try:
            canonical_show = show_registry.validate_show_name(show_name)
            
            # Find interactions involving this character with show filtering
            results = self.interactions_collection.query(
                query_texts=[f"Character relationships: {character_name}"],
                where={"$and": [
                    {"show_name": {"$eq": canonical_show}},
                    {"characters": {"$contains": character_name}}
                ]},
                n_results=100,
                include=["documents", "metadatas"]
            )
            
            relationships = defaultdict(list)
            
            if results['metadatas'] is not None and len(results['metadatas']) > 0 and results['metadatas'][0]:
                for meta in results['metadatas'][0]:
                    characters = json.loads(meta['characters'])
                    if character_name in characters:
                        episode_key = meta['episode_key']
                        interaction_type = meta['interaction_type']
                        emotional_tone = meta['emotional_tone']
                        significance = meta['significance_score']
                        
                        # Add relationships with other characters in this interaction
                        for other_char in characters:
                            if other_char != character_name:
                                relationships[other_char].append({
                                    'episode': episode_key,
                                    'type': interaction_type,
                                    'tone': emotional_tone,
                                    'significance': significance
                                })
            
            # Calculate relationship strengths
            relationship_summary = {}
            for other_char, interactions in relationships.items():
                total_significance = sum(i['significance'] for i in interactions)
                avg_significance = total_significance / len(interactions)
                interaction_count = len(interactions)
                
                # Calculate relationship type distribution
                types = Counter(i['type'] for i in interactions)
                tones = Counter(i['tone'] for i in interactions)
                
                relationship_summary[other_char] = {
                    'interaction_count': interaction_count,
                    'relationship_strength': avg_significance,
                    'primary_interaction_type': types.most_common(1)[0][0] if types else 'unknown',
                    'primary_emotional_tone': tones.most_common(1)[0][0] if tones else 'neutral',
                    'episodes': [i['episode'] for i in interactions]
                }
            
            return {
                'character_name': character_name,
                'relationships': relationship_summary,
                'total_relationships': len(relationship_summary)
            }
            
        except Exception as e:
            logger.error(f"Failed to get relationships for {character_name}: {e}")
            return {'error': str(e)}
    
    def search_character_moments(self, query: str, character_name: str, 
                                show_name: str, limit: int = 10) -> List[Dict]:
        """Search for specific character moments using semantic search."""
        if not show_name:
            raise ValueError("show_name is required to prevent cross-show contamination")
        
        try:
            canonical_show = show_registry.validate_show_name(show_name)
            
            # Build where clause with mandatory show filtering
            where_clause = {"$and": [
                {"character_name": {"$eq": character_name}}, 
                {"show_name": {"$eq": canonical_show}}
            ]}
            
            # Search character profiles
            results = self.characters_collection.query(
                query_texts=[query],
                where=where_clause,
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )
            
            moments = []
            if results['documents'] is not None and len(results['documents']) > 0 and results['documents'][0]:
                for doc, meta, distance in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                    moments.append({
                        'character_name': meta['character_name'],
                        'show_name': meta['show_name'],
                        'season': meta['season'],
                        'episode': meta['episode'],
                        'relevance_score': 1 - distance,
                        'content_preview': doc[:200] + "...",
                        'personality_traits': json.loads(meta.get('personality_traits', '[]'))
                    })
            
            return moments
            
        except Exception as e:
            logger.error(f"Failed to search character moments: {e}")
            return []
    
    def get_character_statistics(self) -> Dict:
        """Get overall statistics about the character database."""
        try:
            char_count = self.characters_collection.count()
            interaction_count = self.interactions_collection.count()
            
            # Get sample data for analysis
            char_sample = self.characters_collection.peek(limit=min(100, char_count))
            
            shows = set()
            characters = set()
            
            if char_sample and char_sample.get('metadatas'):
                for meta in char_sample['metadatas']:
                    shows.add(meta['show_name'])
                    characters.add(meta['character_name'])
            
            return {
                'total_character_profiles': char_count,
                'total_interactions': interaction_count,
                'unique_characters': len(characters),
                'unique_shows': len(shows),
                'shows_analyzed': sorted(list(shows)),
                'sample_characters': sorted(list(characters))[:20]  # Show first 20
            }
            
        except Exception as e:
            logger.error(f"Failed to get character statistics: {e}")
            return {'error': str(e)}
    
    def analyze_season_development(self, show_name: str, season: int) -> Dict:
        """
        Comprehensive season analysis using vector database.
        
        Analyzes character arcs, story progression, relationship evolution,
        and key narrative moments throughout an entire season.
        
        Args:
            show_name: Name of the show
            season: Season number to analyze
            
        Returns:
            Dictionary with comprehensive season analysis
        """
        try:
            logger.info(f"Analyzing season development for {show_name} Season {season}")
            
            # Get all episodes for this season
            season_data = self._get_season_episodes(show_name, season)
            if not season_data:
                return {'error': f'No data found for {show_name} Season {season}'}
            
            # Analyze different aspects of the season
            analysis = {
                'show_name': show_name,
                'season': season,
                'total_episodes': len(season_data['episodes']),
                'episode_range': f"E{min(season_data['episodes'])} - E{max(season_data['episodes'])}",
                
                # Character analysis
                'character_development': self._analyze_season_character_arcs(season_data),
                'character_introductions': self._track_character_introductions(season_data),
                'character_focus_distribution': self._analyze_character_screen_time(season_data),
                
                # Story analysis
                'narrative_progression': self._analyze_story_progression(season_data),
                'thematic_evolution': self._analyze_seasonal_themes(season_data),
                'pivotal_moments': self._identify_pivotal_moments(season_data),
                
                # Relationship analysis
                'relationship_evolution': self._analyze_relationship_development(season_data),
                'social_network_changes': self._track_social_network_evolution(season_data),
                'conflict_resolution_patterns': self._analyze_conflict_patterns(season_data),
                
                # Season-specific insights
                'season_summary': self._generate_season_summary(season_data),
                'character_rankings': self._rank_characters_by_development(season_data),
                'episode_significance_scores': self._calculate_episode_significance(season_data)
            }
            
            # Store season analysis in development collection
            self._store_season_analysis(analysis)
            
            logger.info(f"Season analysis completed for {show_name} Season {season}")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze season development: {e}")
            return {'error': str(e)}
    
    def _get_season_episodes(self, show_name: str, season: int) -> Dict:
        """Get all episode data for a specific season."""
        try:
            # Query all character profiles for this season
            results = self.characters_collection.query(
                query_texts=[f"{show_name} season {season}"],
                where={"$and": [{"show_name": {"$eq": show_name}}, {"season": {"$eq": season}}]},
                n_results=1000,  # Get all episodes
                include=["documents", "metadatas", "embeddings"]
            )
            
            if results['metadatas'] is None or len(results['metadatas']) == 0 or results['metadatas'][0] is None or len(results['metadatas'][0]) == 0:
                return {}
            
            # Organize data by episode
            episodes = defaultdict(lambda: {
                'characters': {},
                'interactions': [],
                'episode_number': 0
            })
            
            for i, meta in enumerate(results['metadatas'][0]):
                episode_num = meta['episode']
                episode_key = f"{show_name}_S{season}E{episode_num}"
                
                episodes[episode_num]['episode_number'] = episode_num
                episodes[episode_num]['characters'][meta['character_name']] = {
                    'dialogue_count': meta['dialogue_count'],
                    'personality_traits': json.loads(meta.get('personality_traits', '[]')),
                    'document': results['documents'][0][i] if results['documents'] is not None and len(results['documents']) > 0 and results['documents'][0] else '',
                    'embedding': results['embeddings'][0][i] if results['embeddings'] is not None and len(results['embeddings']) > 0 and len(results['embeddings'][0]) > 0 else None
                }
            
            # Get interactions for this season
            interaction_results = self.interactions_collection.query(
                query_texts=[f"{show_name} season {season} interactions"],
                n_results=1000,
                include=["documents", "metadatas"]
            )
            
            if interaction_results['metadatas'] is not None and len(interaction_results['metadatas']) > 0 and interaction_results['metadatas'][0]:
                for meta in interaction_results['metadatas'][0]:
                    episode_key = meta['episode_key']
                    if f"S{season}E" in episode_key:
                        # Extract episode number
                        episode_match = re.search(rf'S{season}E(\d+)', episode_key)
                        if episode_match:
                            episode_num = int(episode_match.group(1))
                            episodes[episode_num]['interactions'].append({
                                'characters': json.loads(meta['characters']),
                                'type': meta['interaction_type'],
                                'tone': meta['emotional_tone'],
                                'significance': meta['significance_score']
                            })
            
            return {
                'show_name': show_name,
                'season': season,
                'episodes': sorted(episodes.keys()),
                'episode_data': dict(episodes)
            }
            
        except Exception as e:
            logger.error(f"Failed to get season episodes: {e}")
            return {}
    
    def _analyze_season_character_arcs(self, season_data: Dict) -> Dict:
        """Analyze character development arcs throughout the season."""
        character_arcs = {}
        
        # Track each character across episodes
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            for char_name, char_data in episode_data['characters'].items():
                if char_name not in character_arcs:
                    character_arcs[char_name] = {
                        'episodes_appeared': [],
                        'dialogue_progression': [],
                        'personality_evolution': [],
                        'first_appearance': episode_num,
                        'character_growth_score': 0.0
                    }
                
                character_arcs[char_name]['episodes_appeared'].append(episode_num)
                character_arcs[char_name]['dialogue_progression'].append(char_data['dialogue_count'])
                character_arcs[char_name]['personality_evolution'].append(char_data['personality_traits'])
        
        # Calculate growth scores and trends
        for char_name, arc_data in character_arcs.items():
            if len(arc_data['episodes_appeared']) > 1:
                # Calculate dialogue trend
                dialogue_trend = self._calculate_trend(arc_data['dialogue_progression'])
                
                # Calculate personality development
                personality_diversity = len(set().union(*arc_data['personality_evolution']))
                consistency = len(arc_data['episodes_appeared']) / len(season_data['episodes'])
                
                # Growth score combines multiple factors
                growth_score = (
                    (dialogue_trend + 1) * 0.3 +  # Normalize trend to 0-2 range
                    min(1.0, personality_diversity / 5.0) * 0.4 +
                    consistency * 0.3
                )
                
                character_arcs[char_name]['character_growth_score'] = growth_score
                character_arcs[char_name]['dialogue_trend'] = dialogue_trend
                character_arcs[char_name]['personality_diversity'] = personality_diversity
                character_arcs[char_name]['consistency_score'] = consistency
        
        return character_arcs
    
    def _track_character_introductions(self, season_data: Dict) -> Dict:
        """Track when new characters are introduced during the season."""
        introductions = {}
        
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            new_characters = []
            
            for char_name in episode_data['characters']:
                # Check if this is the character's first appearance in the season
                is_first_appearance = True
                for prev_episode in sorted(season_data['episodes']):
                    if prev_episode >= episode_num:
                        break
                    if char_name in season_data['episode_data'][prev_episode]['characters']:
                        is_first_appearance = False
                        break
                
                if is_first_appearance:
                    char_data = episode_data['characters'][char_name]
                    new_characters.append({
                        'name': char_name,
                        'dialogue_count': char_data['dialogue_count'],
                        'personality_traits': char_data['personality_traits'],
                        'introduction_significance': self._calculate_introduction_significance(char_data, episode_data)
                    })
            
            if new_characters:
                introductions[f'Episode_{episode_num}'] = new_characters
        
        return introductions
    
    def _analyze_character_screen_time(self, season_data: Dict) -> Dict:
        """Analyze how screen time (dialogue count) is distributed among characters."""
        character_screentime = defaultdict(int)
        episode_focus = {}
        
        # Calculate total dialogue per character across season
        for episode_num in season_data['episodes']:
            episode_data = season_data['episode_data'][episode_num]
            episode_dialogue = {}
            
            for char_name, char_data in episode_data['characters'].items():
                dialogue_count = char_data['dialogue_count']
                character_screentime[char_name] += dialogue_count
                episode_dialogue[char_name] = dialogue_count
            
            # Identify episode focus (character with most dialogue)
            if episode_dialogue:
                main_character = max(episode_dialogue, key=episode_dialogue.get)
                episode_focus[f'Episode_{episode_num}'] = {
                    'main_character': main_character,
                    'dialogue_count': episode_dialogue[main_character],
                    'character_distribution': dict(episode_dialogue)
                }
        
        # Calculate percentages
        total_dialogue = sum(character_screentime.values())
        screentime_percentages = {
            char: (count / total_dialogue * 100) if total_dialogue > 0 else 0
            for char, count in character_screentime.items()
        }
        
        return {
            'total_season_dialogue': total_dialogue,
            'character_screentime_raw': dict(character_screentime),
            'character_screentime_percentage': screentime_percentages,
            'episode_focus_analysis': episode_focus,
            'main_characters': sorted(screentime_percentages.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def _analyze_story_progression(self, season_data: Dict) -> Dict:
        """Analyze story progression using semantic similarity of episodes."""
        if not self.encoder:
            return {'error': 'Embeddings not available for story progression analysis'}
        
        episode_embeddings = []
        episode_summaries = []
        
        # Create episode summaries from character dialogues
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            # Combine all character information for episode summary
            episode_summary = f"Episode {episode_num}: "
            character_summaries = []
            
            for char_name, char_data in episode_data['characters'].items():
                char_summary = f"{char_name} ({', '.join(char_data['personality_traits'])})"
                character_summaries.append(char_summary)
            
            episode_summary += "; ".join(character_summaries)
            episode_summaries.append(episode_summary)
            
            # Generate episode embedding
            embedding = self.encoder.encode(episode_summary).tolist()
            episode_embeddings.append(embedding)
        
        # Calculate episode-to-episode similarity
        progression_analysis = {
            'episode_summaries': episode_summaries,
            'narrative_flow': [],
            'story_arcs': self._identify_story_arcs(episode_embeddings, season_data['episodes']),
            'pacing_analysis': self._analyze_story_pacing(season_data)
        }
        
        # Calculate similarity between consecutive episodes
        for i in range(len(episode_embeddings) - 1):
            similarity = self._calculate_cosine_similarity(episode_embeddings[i], episode_embeddings[i + 1])
            progression_analysis['narrative_flow'].append({
                'from_episode': season_data['episodes'][i],
                'to_episode': season_data['episodes'][i + 1],
                'narrative_similarity': similarity,
                'transition_type': 'smooth' if similarity > 0.7 else 'dramatic' if similarity < 0.3 else 'moderate'
            })
        
        return progression_analysis
    
    def _analyze_seasonal_themes(self, season_data: Dict) -> Dict:
        """Analyze thematic elements throughout the season."""
        # Collect all personality traits across the season
        all_traits = []
        episode_themes = {}
        
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            episode_traits = []
            
            for char_name, char_data in episode_data['characters'].items():
                episode_traits.extend(char_data['personality_traits'])
                all_traits.extend(char_data['personality_traits'])
            
            # Count theme frequency for this episode
            trait_counts = Counter(episode_traits)
            episode_themes[f'Episode_{episode_num}'] = {
                'dominant_themes': trait_counts.most_common(3),
                'theme_diversity': len(set(episode_traits)),
                'total_theme_instances': len(episode_traits)
            }
        
        # Analyze season-wide themes
        season_trait_counts = Counter(all_traits)
        dominant_season_themes = season_trait_counts.most_common(5)
        
        # Track theme evolution
        theme_evolution = self._track_theme_evolution(episode_themes, season_data['episodes'])
        
        return {
            'dominant_season_themes': dominant_season_themes,
            'episode_thematic_analysis': episode_themes,
            'theme_evolution': theme_evolution,
            'thematic_diversity_score': len(set(all_traits)) / max(1, len(all_traits)),
            'recurring_themes': [theme for theme, count in season_trait_counts.items() if count >= 3]
        }
    
    def _identify_pivotal_moments(self, season_data: Dict) -> List[Dict]:
        """Identify pivotal moments in the season based on interaction significance."""
        pivotal_moments = []
        
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            # Find high-significance interactions
            significant_interactions = [
                interaction for interaction in episode_data['interactions']
                if interaction['significance'] > 0.7
            ]
            
            for interaction in significant_interactions:
                pivotal_moments.append({
                    'episode': episode_num,
                    'characters_involved': interaction['characters'],
                    'interaction_type': interaction['type'],
                    'emotional_tone': interaction['tone'],
                    'significance_score': interaction['significance'],
                    'moment_type': self._classify_moment_type(interaction)
                })
        
        # Sort by significance and return top moments
        pivotal_moments.sort(key=lambda x: x['significance_score'], reverse=True)
        return pivotal_moments[:10]  # Top 10 pivotal moments
    
    def _analyze_relationship_development(self, season_data: Dict) -> Dict:
        """Analyze how relationships evolve throughout the season."""
        relationship_timeline = defaultdict(list)
        
        # Track relationships episode by episode
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            # Analyze each interaction for relationship development
            for interaction in episode_data['interactions']:
                characters = interaction['characters']
                
                # Create relationship pairs
                for i, char1 in enumerate(characters):
                    for char2 in characters[i + 1:]:
                        relationship_key = tuple(sorted([char1, char2]))
                        
                        relationship_timeline[relationship_key].append({
                            'episode': episode_num,
                            'interaction_type': interaction['type'],
                            'emotional_tone': interaction['tone'],
                            'significance': interaction['significance']
                        })
        
        # Analyze relationship trajectories
        relationship_analysis = {}
        for relationship_key, timeline in relationship_timeline.items():
            char1, char2 = relationship_key
            
            # Calculate relationship strength over time
            strength_progression = []
            cumulative_strength = 0
            
            for interaction in timeline:
                # Adjust strength based on interaction type and tone
                strength_change = interaction['significance']
                
                if interaction['interaction_type'] == 'cooperation':
                    strength_change += 0.2
                elif interaction['interaction_type'] == 'conflict':
                    strength_change -= 0.1
                
                if interaction['emotional_tone'] == 'positive':
                    strength_change += 0.1
                elif interaction['emotional_tone'] == 'negative':
                    strength_change -= 0.1
                
                cumulative_strength += strength_change
                strength_progression.append({
                    'episode': interaction['episode'],
                    'strength': cumulative_strength
                })
            
            relationship_analysis[f"{char1}_{char2}"] = {
                'characters': [char1, char2],
                'interaction_count': len(timeline),
                'relationship_strength': cumulative_strength,
                'strength_progression': strength_progression,
                'relationship_trend': self._calculate_trend([s['strength'] for s in strength_progression]),
                'dominant_interaction_type': Counter([i['interaction_type'] for i in timeline]).most_common(1)[0][0],
                'relationship_classification': self._classify_relationship(cumulative_strength, timeline)
            }
        
        return relationship_analysis
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend (positive = increasing, negative = decreasing, 0 = stable)."""
        if len(values) < 2:
            return 0.0
        
        # Simple linear trend calculation
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        return numerator / denominator if denominator != 0 else 0.0
    
    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            import numpy as np
            
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0
            
            return dot_product / (norm_v1 * norm_v2)
            
        except ImportError:
            # Fallback without numpy
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm_v1 = sum(a * a for a in vec1) ** 0.5
            norm_v2 = sum(b * b for b in vec2) ** 0.5
            
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0
            
            return dot_product / (norm_v1 * norm_v2)
    
    def _store_season_analysis(self, analysis: Dict):
        """Store season analysis in the development collection."""
        try:
            season_id = f"{analysis['show_name']}_S{analysis['season']}_analysis"
            
            # Create document summarizing the season
            document = f"""
            Season Analysis: {analysis['show_name']} Season {analysis['season']}
            Episodes: {analysis['total_episodes']} ({analysis['episode_range']})
            
            Key Characters: {', '.join([char for char, _ in analysis['character_focus_distribution']['main_characters'][:5]])}
            Dominant Themes: {', '.join([theme for theme, _ in analysis['thematic_evolution']['dominant_season_themes'][:3]])}
            
            Character Development Score: {sum([arc['character_growth_score'] for arc in analysis['character_development'].values()]) / max(1, len(analysis['character_development'])) if analysis['character_development'] else 0:.2f}
            
            Top Pivotal Moments: {len(analysis['pivotal_moments'])} significant events identified
            Relationship Dynamics: {len(analysis['relationship_evolution'])} character relationships tracked
            """
            
            metadata = {
                'show_name': analysis['show_name'],
                'season': analysis['season'],
                'total_episodes': analysis['total_episodes'],
                'analysis_type': 'season_analysis',
                'character_count': len(analysis['character_development']),
                'relationship_count': len(analysis['relationship_evolution']),
                'pivotal_moments_count': len(analysis['pivotal_moments'])
            }
            
            self.development_collection.upsert(
                ids=[season_id],
                documents=[document.strip()],
                metadatas=[metadata]
            )
            
        except Exception as e:
            logger.error(f"Failed to store season analysis: {e}")
    
    def _calculate_introduction_significance(self, char_data: Dict, episode_data: Dict) -> float:
        """Calculate significance score for character introduction."""
        # Base significance on dialogue count relative to episode
        total_episode_dialogue = sum(cd['dialogue_count'] for cd in episode_data['characters'].values())
        dialogue_ratio = char_data['dialogue_count'] / max(1, total_episode_dialogue)
        
        # Boost for personality traits (indicates developed character)
        trait_bonus = len(char_data['personality_traits']) * 0.1
        
        return min(1.0, dialogue_ratio + trait_bonus)
    
    def _identify_story_arcs(self, episode_embeddings: List[List[float]], episodes: List[int]) -> List[Dict]:
        """Identify story arcs based on episode similarity patterns."""
        if len(episode_embeddings) < 3:
            return []
        
        arcs = []
        current_arc = {'start_episode': episodes[0], 'episodes': [episodes[0]], 'coherence_score': 0.0}
        
        for i in range(1, len(episode_embeddings)):
            similarity = self._calculate_cosine_similarity(episode_embeddings[i-1], episode_embeddings[i])
            
            if similarity > 0.6:  # Threshold for arc continuity
                current_arc['episodes'].append(episodes[i])
                current_arc['coherence_score'] = (current_arc['coherence_score'] * (len(current_arc['episodes']) - 2) + similarity) / (len(current_arc['episodes']) - 1)
            else:
                # End current arc and start new one
                if len(current_arc['episodes']) > 1:
                    current_arc['end_episode'] = current_arc['episodes'][-1]
                    current_arc['arc_length'] = len(current_arc['episodes'])
                    arcs.append(current_arc)
                
                current_arc = {'start_episode': episodes[i], 'episodes': [episodes[i]], 'coherence_score': 0.0}
        
        # Don't forget the last arc
        if len(current_arc['episodes']) > 1:
            current_arc['end_episode'] = current_arc['episodes'][-1]
            current_arc['arc_length'] = len(current_arc['episodes'])
            arcs.append(current_arc)
        
        return arcs
    
    def _analyze_story_pacing(self, season_data: Dict) -> Dict:
        """Analyze story pacing based on dialogue density and interaction intensity."""
        pacing_data = {}
        
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            # Calculate dialogue density
            total_dialogue = sum(cd['dialogue_count'] for cd in episode_data['characters'].values())
            character_count = len(episode_data['characters'])
            dialogue_density = total_dialogue / max(1, character_count)
            
            # Calculate interaction intensity
            high_significance_interactions = sum(1 for i in episode_data['interactions'] if i['significance'] > 0.6)
            interaction_intensity = high_significance_interactions / max(1, len(episode_data['interactions']))
            
            # Overall pacing score
            pacing_score = (dialogue_density / 10.0 + interaction_intensity) / 2.0  # Normalize
            
            pacing_data[f'Episode_{episode_num}'] = {
                'dialogue_density': dialogue_density,
                'interaction_intensity': interaction_intensity,
                'pacing_score': min(1.0, pacing_score),
                'pacing_type': 'fast' if pacing_score > 0.7 else 'slow' if pacing_score < 0.3 else 'moderate'
            }
        
        return pacing_data
    
    def _track_theme_evolution(self, episode_themes: Dict, episodes: List[int]) -> Dict:
        """Track how themes evolve throughout the season."""
        theme_timeline = defaultdict(list)
        
        # Collect theme data for each episode
        for episode_num in sorted(episodes):
            episode_key = f'Episode_{episode_num}'
            if episode_key in episode_themes:
                themes = episode_themes[episode_key]['dominant_themes']
                
                # Track top 3 themes for this episode
                for theme, count in themes:
                    theme_timeline[theme].append({
                        'episode': episode_num,
                        'frequency': count,
                        'dominance_rank': themes.index((theme, count)) + 1
                    })
        
        # Analyze evolution patterns
        evolution_analysis = {}
        for theme, timeline in theme_timeline.items():
            if len(timeline) >= 2:
                frequencies = [entry['frequency'] for entry in timeline]
                evolution_analysis[theme] = {
                    'appearances': len(timeline),
                    'frequency_trend': self._calculate_trend(frequencies),
                    'peak_episode': max(timeline, key=lambda x: x['frequency'])['episode'],
                    'consistency': len(timeline) / len(episodes),
                    'evolution_pattern': self._classify_theme_pattern(timeline)
                }
        
        return evolution_analysis
    
    def _classify_moment_type(self, interaction: Dict) -> str:
        """Classify the type of pivotal moment based on interaction characteristics."""
        interaction_type = interaction['type']
        emotional_tone = interaction['tone']
        significance = interaction['significance']
        
        if interaction_type == 'conflict' and significance > 0.8:
            return 'major_conflict'
        elif interaction_type == 'cooperation' and emotional_tone == 'positive':
            return 'alliance_formation'
        elif emotional_tone == 'negative' and significance > 0.7:
            return 'dramatic_tension'
        elif emotional_tone == 'positive' and significance > 0.7:
            return 'resolution_moment'
        else:
            return 'character_development'
    
    def _classify_relationship(self, strength: float, timeline: List[Dict]) -> str:
        """Classify relationship based on strength and interaction patterns."""
        if strength > 2.0:
            return 'strong_alliance'
        elif strength > 1.0:
            return 'positive_relationship'
        elif strength > 0:
            return 'neutral_acquaintance'
        elif strength > -1.0:
            return 'mild_rivalry'
        else:
            return 'antagonistic'
    
    def _classify_theme_pattern(self, timeline: List[Dict]) -> str:
        """Classify how a theme evolves over time."""
        frequencies = [entry['frequency'] for entry in timeline]
        
        if len(frequencies) < 2:
            return 'single_occurrence'
        
        trend = self._calculate_trend(frequencies)
        
        if trend > 0.1:
            return 'growing_importance'
        elif trend < -0.1:
            return 'declining_importance'
        else:
            return 'consistent_presence'
    
    def _track_social_network_evolution(self, season_data: Dict) -> Dict:
        """Track how the social network of characters evolves."""
        network_evolution = {}
        
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            # Build network for this episode
            connections = defaultdict(set)
            for interaction in episode_data['interactions']:
                characters = interaction['characters']
                for i, char1 in enumerate(characters):
                    for char2 in characters[i + 1:]:
                        connections[char1].add(char2)
                        connections[char2].add(char1)
            
            # Calculate network metrics
            total_characters = len(episode_data['characters'])
            total_connections = sum(len(chars) for chars in connections.values()) // 2
            
            # Network density
            max_connections = total_characters * (total_characters - 1) // 2
            network_density = total_connections / max(1, max_connections)
            
            # Central characters (most connected)
            centrality_scores = {char: len(connected) for char, connected in connections.items()}
            central_characters = sorted(centrality_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            
            network_evolution[f'Episode_{episode_num}'] = {
                'total_characters': total_characters,
                'total_connections': total_connections,
                'network_density': network_density,
                'central_characters': central_characters,
                'isolated_characters': [char for char in episode_data['characters'] if char not in connections]
            }
        
        return network_evolution
    
    def _analyze_conflict_patterns(self, season_data: Dict) -> Dict:
        """Analyze patterns of conflict and resolution throughout the season."""
        conflict_analysis = {
            'conflicts_by_episode': {},
            'conflict_participants': defaultdict(int),
            'resolution_patterns': [],
            'escalation_trends': []
        }
        
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            # Find conflicts in this episode
            conflicts = [i for i in episode_data['interactions'] if i['type'] == 'conflict']
            cooperations = [i for i in episode_data['interactions'] if i['type'] == 'cooperation']
            
            conflict_analysis['conflicts_by_episode'][f'Episode_{episode_num}'] = {
                'conflict_count': len(conflicts),
                'cooperation_count': len(cooperations),
                'conflict_resolution_ratio': len(cooperations) / max(1, len(conflicts)),
                'conflict_participants': [char for conflict in conflicts for char in conflict['characters']]
            }
            
            # Track conflict participants
            for conflict in conflicts:
                for char in conflict['characters']:
                    conflict_analysis['conflict_participants'][char] += 1
        
        return conflict_analysis
    
    def _generate_season_summary(self, season_data: Dict) -> str:
        """Generate a narrative summary of the season."""
        total_episodes = len(season_data['episodes'])
        total_characters = len(set(char for ep_data in season_data['episode_data'].values() 
                                 for char in ep_data['characters'].keys()))
        
        # Find most active character
        character_activity = defaultdict(int)
        for ep_data in season_data['episode_data'].values():
            for char, char_data in ep_data['characters'].items():
                character_activity[char] += char_data['dialogue_count']
        
        most_active = max(character_activity.items(), key=lambda x: x[1]) if character_activity else ('Unknown', 0)
        
        # Count interactions
        total_interactions = sum(len(ep_data['interactions']) for ep_data in season_data['episode_data'].values())
        
        summary = f"""
        Season Summary for {season_data['show_name']} Season {season_data['season']}:
        
        This season spans {total_episodes} episodes featuring {total_characters} unique characters.
        The most active character is {most_active[0]} with {most_active[1]} dialogue instances.
        
        A total of {total_interactions} character interactions were analyzed, revealing complex
        relationship dynamics and character development arcs throughout the season.
        
        The season demonstrates rich character development with multiple story arcs and
        evolving relationships that drive the narrative forward.
        """
        
        return summary.strip()
    
    def _rank_characters_by_development(self, season_data: Dict) -> List[Dict]:
        """Rank characters by their development throughout the season."""
        character_rankings = []
        
        # Collect character data across all episodes
        character_stats = defaultdict(lambda: {
            'total_dialogue': 0,
            'episodes_appeared': 0,
            'personality_traits': set(),
            'interactions': 0
        })
        
        for ep_data in season_data['episode_data'].values():
            for char_name, char_data in ep_data['characters'].items():
                stats = character_stats[char_name]
                stats['total_dialogue'] += char_data['dialogue_count']
                stats['episodes_appeared'] += 1
                stats['personality_traits'].update(char_data['personality_traits'])
            
            for interaction in ep_data['interactions']:
                for char in interaction['characters']:
                    character_stats[char]['interactions'] += 1
        
        # Calculate development scores
        for char_name, stats in character_stats.items():
            consistency = stats['episodes_appeared'] / len(season_data['episodes'])
            personality_diversity = len(stats['personality_traits'])
            dialogue_activity = stats['total_dialogue'] / max(1, stats['episodes_appeared'])
            social_activity = stats['interactions'] / max(1, stats['episodes_appeared'])
            
            development_score = (
                consistency * 0.3 +
                min(1.0, personality_diversity / 5.0) * 0.3 +
                min(1.0, dialogue_activity / 10.0) * 0.2 +
                min(1.0, social_activity / 5.0) * 0.2
            )
            
            character_rankings.append({
                'character_name': char_name,
                'development_score': development_score,
                'episodes_appeared': stats['episodes_appeared'],
                'total_dialogue': stats['total_dialogue'],
                'personality_traits': list(stats['personality_traits']),
                'interaction_count': stats['interactions'],
                'consistency': consistency
            })
        
        # Sort by development score
        character_rankings.sort(key=lambda x: x['development_score'], reverse=True)
        return character_rankings
    
    def _calculate_episode_significance(self, season_data: Dict) -> Dict:
        """Calculate significance scores for each episode."""
        episode_scores = {}
        
        for episode_num in sorted(season_data['episodes']):
            episode_data = season_data['episode_data'][episode_num]
            
            # Character diversity
            character_count = len(episode_data['characters'])
            
            # Dialogue intensity
            total_dialogue = sum(cd['dialogue_count'] for cd in episode_data['characters'].values())
            
            # Interaction significance
            avg_interaction_significance = (
                sum(i['significance'] for i in episode_data['interactions']) / 
                max(1, len(episode_data['interactions']))
            )
            
            # High-impact interactions
            pivotal_interactions = sum(1 for i in episode_data['interactions'] if i['significance'] > 0.7)
            
            # Combined significance score
            significance_score = (
                min(1.0, character_count / 10.0) * 0.25 +
                min(1.0, total_dialogue / 50.0) * 0.25 +
                avg_interaction_significance * 0.3 +
                min(1.0, pivotal_interactions / 3.0) * 0.2
            )
            
            episode_scores[f'Episode_{episode_num}'] = {
                'significance_score': significance_score,
                'character_count': character_count,
                'total_dialogue': total_dialogue,
                'avg_interaction_significance': avg_interaction_significance,
                'pivotal_interactions': pivotal_interactions,
                'episode_type': 'climactic' if significance_score > 0.8 else 'developmental' if significance_score > 0.5 else 'transitional'
            }
        
        return episode_scores


def main():
    """Example usage of the Character Analysis Agent."""
    try:
        # Initialize the agent
        agent = CharacterAnalysisAgent()
        
        # Example transcript for testing
        sample_transcript = """
        Izuku: I want to become a hero who can save everyone with a smile!
        All Might: Young Midoriya, being a hero means more than just having power.
        Bakugo: Deku! You think you can surpass me? Never!
        Izuku: Kacchan, I know I'm not strong yet, but I won't give up!
        All Might: The heart of a true hero... that's what you have, my boy.
        Bakugo: Tch! Whatever! I'll show you what real strength looks like!
        """
        
        # Analyze characters for multiple episodes to test season analysis
        print("🎭 Setting up sample season data...")
        
        # Episode 1
        profiles_ep1 = agent.analyze_episode_characters(
            "My Hero Academia", 1, 1, sample_transcript
        )
        print(f"Episode 1: Found {len(profiles_ep1)} characters")
        
        # Episode 2 with character development
        sample_transcript_ep2 = """
        Izuku: I'm getting stronger! I won't let my friends down!
        All Might: You've grown so much, young Midoriya. Your determination inspires everyone.
        Bakugo: Damn it, Deku! Why are you always getting in my way?
        Ochaco: Deku-kun, you're so brave! I want to be a hero like you!
        Izuku: Thank you, Uraraka-san. We'll become great heroes together!
        Iida: As class representative, I admire your dedication, Midoriya!
        """
        
        profiles_ep2 = agent.analyze_episode_characters(
            "My Hero Academia", 1, 2, sample_transcript_ep2
        )
        print(f"Episode 2: Found {len(profiles_ep2)} characters")
        
        # Episode 3 with more conflict
        sample_transcript_ep3 = """
        Bakugo: I'll crush you all! I'm the strongest here!
        Izuku: Kacchan, we need to work together to defeat the villain!
        Todoroki: My power... I won't use his fire. Ice is enough.
        Izuku: Todoroki-kun, your power is your own! Not your father's!
        Todoroki: Midoriya... you're right. This is my power!
        All Might: These young heroes... they give me hope for the future.
        """
        
        profiles_ep3 = agent.analyze_episode_characters(
            "My Hero Academia", 1, 3, sample_transcript_ep3
        )
        print(f"Episode 3: Found {len(profiles_ep3)} characters")
        
        print(f"\n🎬 Analyzing Season 1 development...")
        
        # Perform comprehensive season analysis
        season_analysis = agent.analyze_season_development("My Hero Academia", 1)
        
        if 'error' not in season_analysis:
            print("✅ Season Analysis Completed!")
            print(f"\n📊 Season Overview:")
            print(f"  Total Episodes: {season_analysis['total_episodes']}")
            print(f"  Episode Range: {season_analysis['episode_range']}")
            
            print(f"\n👥 Character Development:")
            char_dev = season_analysis['character_development']
            for char_name, arc_data in list(char_dev.items())[:3]:  # Show top 3
                print(f"  {char_name}:")
                print(f"    Growth Score: {arc_data['character_growth_score']:.2f}")
                print(f"    Episodes Appeared: {len(arc_data['episodes_appeared'])}")
                print(f"    Dialogue Trend: {arc_data.get('dialogue_trend', 0):.2f}")
            
            print(f"\n🎭 Character Focus Distribution:")
            focus_dist = season_analysis['character_focus_distribution']
            for char_name, percentage in focus_dist['main_characters'][:3]:
                print(f"  {char_name}: {percentage:.1f}% of season dialogue")
            
            print(f"\n🌟 Pivotal Moments:")
            for i, moment in enumerate(season_analysis['pivotal_moments'][:3], 1):
                print(f"  {i}. Episode {moment['episode']}: {moment['moment_type']}")
                print(f"     Characters: {', '.join(moment['characters_involved'])}")
                print(f"     Significance: {moment['significance_score']:.2f}")
            
            print(f"\n💫 Dominant Season Themes:")
            themes = season_analysis['thematic_evolution']['dominant_season_themes']
            for theme, count in themes[:5]:
                print(f"  {theme}: {count} instances")
            
            print(f"\n🤝 Key Relationships:")
            relationships = season_analysis['relationship_evolution']
            for rel_key, rel_data in list(relationships.items())[:3]:
                chars = rel_data['characters']
                print(f"  {chars[0]} ↔ {chars[1]}:")
                print(f"    Strength: {rel_data['relationship_strength']:.2f}")
                print(f"    Type: {rel_data['relationship_classification']}")
                print(f"    Interactions: {rel_data['interaction_count']}")
            
            print(f"\n📈 Character Rankings (Top 3):")
            rankings = season_analysis['character_rankings']
            for i, char_data in enumerate(rankings[:3], 1):
                print(f"  {i}. {char_data['character_name']}")
                print(f"     Development Score: {char_data['development_score']:.2f}")
                print(f"     Episodes: {char_data['episodes_appeared']}")
                print(f"     Traits: {', '.join(char_data['personality_traits'][:3])}")
        
        else:
            print(f"❌ Season analysis failed: {season_analysis['error']}")
        
        # Test individual character search
        print("\n🔍 Searching for determined characters...")
        moments = agent.search_character_moments("determined hero never give up")
        print(f"Found {len(moments)} relevant moments")
        
        # Get statistics
        print("\n📊 Character database statistics:")
        stats = agent.get_character_statistics()
        for key, value in stats.items():
            if key != 'error':
                print(f"  {key}: {value}")
        
        print("\n✅ Character Analysis Agent with Season Analysis test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error testing Character Analysis Agent: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
