#!/usr/bin/env python3
"""
Vector database integration for semantic search capabilities.

This module provides vector search functionality for the anime generator,
enabling semantic episode search, similarity detection, and content analysis.
"""

import os
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import numpy as np

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class VectorSearchManager:
    """
    Manages vector database operations for semantic search in the anime generator.
    
    Provides functionality for:
    - Episode transcript embedding and storage
    - Semantic search across episodes
    - Similar content discovery
    - Quality assessment through semantic similarity
    """
    
    def __init__(self, persist_directory: str = "vector_db", collection_name: str = "anime_transcripts"):
        """
        Initialize vector search manager.
        
        Args:
            persist_directory (str): Directory to persist the vector database
            collection_name (str): Name of the collection to store vectors
        """
        if not CHROMA_AVAILABLE:
            raise ImportError("ChromaDB not available. Install with: pip install chromadb")
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("SentenceTransformers not available. Install with: pip install sentence-transformers")
            self.encoder = None
        else:
            # Use a model that's good for general semantic similarity
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except ValueError:
            # Collection doesn't exist, create it
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Anime episode transcripts for semantic search"}
            )
            logger.info(f"Created new collection: {collection_name}")
    
    def add_episode(self, show_name: str, season: int, episode: int, 
                   transcript: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Add an episode transcript to the vector database.
        
        Args:
            show_name (str): Name of the show
            season (int): Season number
            episode (int): Episode number
            transcript (str): Full transcript text
            metadata (Dict): Additional metadata for the episode
            
        Returns:
            bool: True if successfully added, False otherwise
        """
        try:
            # Create unique ID for the episode
            episode_id = f"{show_name}_S{season}E{episode}".replace(" ", "_")
            
            # Prepare metadata
            episode_metadata = {
                "show_name": show_name,
                "season": season,
                "episode": episode,
                "transcript_length": len(transcript),
                **(metadata or {})
            }
            
            # Split transcript into chunks for better search granularity
            chunks = self._chunk_transcript(transcript)
            
            # Generate embeddings if encoder is available
            if self.encoder:
                embeddings = self.encoder.encode(chunks)
            else:
                # Use ChromaDB's default embedding function
                embeddings = None
            
            # Prepare data for insertion
            ids = [f"{episode_id}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {**episode_metadata, "chunk_index": i, "chunk_text": chunk[:200]}
                for i, chunk in enumerate(chunks)
            ]
            
            # Add to collection
            self.collection.add(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Added {len(chunks)} chunks for {episode_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add episode {show_name} S{season}E{episode}: {e}")
            return False
    
    def search_episodes(self, query: str, limit: int = 10, 
                       show_filter: str = None, season_filter: int = None) -> List[Dict]:
        """
        Search for episodes using semantic similarity.
        
        Args:
            query (str): Search query
            limit (int): Maximum number of results to return
            show_filter (str): Filter by specific show name
            season_filter (int): Filter by specific season
            
        Returns:
            List[Dict]: Search results with metadata and similarity scores
        """
        try:
            # Build where clause for filtering
            where_clause = {}
            if show_filter:
                where_clause["show_name"] = show_filter
            if season_filter is not None:
                where_clause["season"] = season_filter
            
            # Perform search
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_clause if where_clause else None,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results['documents'] is not None and len(results['documents']) > 0 and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    formatted_results.append({
                        'rank': i + 1,
                        'show_name': metadata['show_name'],
                        'season': metadata['season'],
                        'episode': metadata['episode'],
                        'chunk_index': metadata['chunk_index'],
                        'similarity_score': 1 - distance,  # Convert distance to similarity
                        'transcript_snippet': doc[:300] + "..." if len(doc) > 300 else doc,
                        'full_chunk': doc,
                        'metadata': metadata
                    })
            
            logger.info(f"Found {len(formatted_results)} results for query: {query[:50]}...")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []
    
    def find_similar_episodes(self, show_name: str, season: int, episode: int, 
                            limit: int = 5) -> List[Dict]:
        """
        Find episodes similar to a specific episode.
        
        Args:
            show_name (str): Reference show name
            season (int): Reference season
            episode (int): Reference episode
            limit (int): Number of similar episodes to find
            
        Returns:
            List[Dict]: Similar episodes with similarity scores
        """
        try:
            # Get the reference episode's chunks
            episode_id = f"{show_name}_S{season}E{episode}".replace(" ", "_")
            
            # Find all chunks for this episode
            episode_chunks = self.collection.get(
                where={"show_name": show_name, "season": season, "episode": episode},
                include=["documents", "metadatas"]
            )
            
            if episode_chunks['documents'] is None or len(episode_chunks['documents']) == 0:
                logger.warning(f"No data found for {show_name} S{season}E{episode}")
                return []
            
            # Use the first chunk as representative for similarity search
            reference_text = episode_chunks['documents'][0]
            
            # Search for similar content, excluding the same episode
            results = self.collection.query(
                query_texts=[reference_text],
                n_results=limit * 3,  # Get more results to filter out same episode
                include=["documents", "metadatas", "distances"]
            )
            
            # Group results by episode and filter out the reference episode
            episode_similarities = {}
            if results['documents'] is not None and len(results['documents']) > 0 and results['documents'][0]:
                for doc, metadata, distance in zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                ):
                    # Skip the same episode
                    if (metadata['show_name'] == show_name and 
                        metadata['season'] == season and 
                        metadata['episode'] == episode):
                        continue
                    
                    episode_key = f"{metadata['show_name']}_S{metadata['season']}E{metadata['episode']}"
                    if episode_key not in episode_similarities:
                        episode_similarities[episode_key] = {
                            'show_name': metadata['show_name'],
                            'season': metadata['season'],
                            'episode': metadata['episode'],
                            'similarity_scores': [],
                            'best_snippet': doc[:200] + "..."
                        }
                    
                    episode_similarities[episode_key]['similarity_scores'].append(1 - distance)
            
            # Calculate average similarity per episode
            similar_episodes = []
            for episode_key, data in episode_similarities.items():
                avg_similarity = np.mean(data['similarity_scores'])
                similar_episodes.append({
                    'show_name': data['show_name'],
                    'season': data['season'],
                    'episode': data['episode'],
                    'average_similarity': avg_similarity,
                    'max_similarity': max(data['similarity_scores']),
                    'best_snippet': data['best_snippet']
                })
            
            # Sort by similarity and return top results
            similar_episodes.sort(key=lambda x: x['average_similarity'], reverse=True)
            return similar_episodes[:limit]
            
        except Exception as e:
            logger.error(f"Failed to find similar episodes for {show_name} S{season}E{episode}: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        try:
            count = self.collection.count()
            
            # Get sample of metadata to analyze
            sample = self.collection.peek(limit=min(100, count))
            
            shows = set()
            seasons = set()
            episodes = set()
            
            if sample['metadatas'] is not None and len(sample['metadatas']) > 0:
                for metadata in sample['metadatas']:
                    shows.add(metadata['show_name'])
                    seasons.add(f"{metadata['show_name']}_S{metadata['season']}")
                    episodes.add(f"{metadata['show_name']}_S{metadata['season']}E{metadata['episode']}")
            
            return {
                'total_chunks': count,
                'unique_shows': len(shows),
                'unique_seasons': len(seasons),
                'unique_episodes': len(episodes),
                'shows_list': sorted(list(shows)),
                'encoder_model': str(self.encoder) if self.encoder else "ChromaDB default"
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    def remove_episode(self, show_name: str, season: int, episode: int) -> bool:
        """Remove an episode from the vector database."""
        try:
            # Find all chunks for this episode
            results = self.collection.get(
                where={"show_name": show_name, "season": season, "episode": episode},
                include=["metadatas"]
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Removed {len(results['ids'])} chunks for {show_name} S{season}E{episode}")
                return True
            else:
                logger.warning(f"No data found to remove for {show_name} S{season}E{episode}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove episode {show_name} S{season}E{episode}: {e}")
            return False
    
    def _chunk_transcript(self, transcript: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split transcript into overlapping chunks for better search granularity.
        
        Args:
            transcript (str): Full transcript text
            chunk_size (int): Target size for each chunk
            overlap (int): Overlap between chunks
            
        Returns:
            List[str]: List of transcript chunks
        """
        if len(transcript) <= chunk_size:
            return [transcript]
        
        chunks = []
        start = 0
        
        while start < len(transcript):
            end = start + chunk_size
            
            # Try to break at sentence boundaries
            if end < len(transcript):
                # Look for sentence endings within the last 100 characters
                for i in range(min(100, chunk_size // 4)):
                    if transcript[end - i] in '.!?':
                        end = end - i + 1
                        break
            
            chunk = transcript[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - overlap
            if start >= len(transcript):
                break
        
        return chunks


def install_dependencies():
    """Install required dependencies for vector search."""
    try:
        import subprocess
        import sys
        
        print("Installing vector search dependencies...")
        
        # Install ChromaDB
        subprocess.check_call([sys.executable, "-m", "pip", "install", "chromadb"])
        print("✅ ChromaDB installed")
        
        # Install SentenceTransformers
        subprocess.check_call([sys.executable, "-m", "pip", "install", "sentence-transformers"])
        print("✅ SentenceTransformers installed")
        
        print("Vector search dependencies installed successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
    except Exception as e:
        print(f"❌ Error during installation: {e}")


if __name__ == "__main__":
    # Example usage and testing
    if not CHROMA_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("Missing dependencies. Run install_dependencies() to install them.")
        install_dependencies()
    else:
        # Test the vector search functionality
        print("Testing Vector Search Manager...")
        
        vsm = VectorSearchManager()
        
        # Add sample episode
        sample_transcript = """
        Izuku struggles during the UA entrance exam, finding himself behind other students.
        He destroys a giant robot to save Ochaco but breaks his arm and legs.
        Despite zero combat points, he passes due to rescue points for heroic actions.
        All Might welcomes him to UA High School.
        """
        
        success = vsm.add_episode("My Hero Academia", 1, 4, sample_transcript, {
            "title": "Start Line",
            "quality_score": 0.85
        })
        
        if success:
            print("✅ Sample episode added successfully")
            
            # Test search
            results = vsm.search_episodes("hero entrance exam")
            print(f"✅ Search returned {len(results)} results")
            
            # Test stats
            stats = vsm.get_collection_stats()
            print(f"✅ Collection stats: {stats}")
        else:
            print("❌ Failed to add sample episode")
