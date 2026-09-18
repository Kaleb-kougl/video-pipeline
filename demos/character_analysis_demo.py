#!/usr/bin/env python3
"""
Character analysis demonstration module.

This module provides comprehensive demonstration of the advanced character
analysis capabilities in the anime video generation system, showcasing
ChromaDB vector database integration for semantic character analysis.

The demonstrations include:
    - Episode-level character analysis
    - Semantic character moment searching
    - Character similarity analysis
    - Relationship mapping and analysis
    - Character development tracking
    - Advanced semantic search features

Example Usage:
    python character_analysis_demo.py

Classes:
    None

Functions:
    demo_character_analysis: Main character analysis demonstration
    demo_advanced_features: Advanced feature demonstrations

Dependencies:
    - ChromaDB: Vector database for character embeddings
    - sentence-transformers: Text embedding model
    - main: Core application functionality

Note:
    Requires ChromaDB and sentence-transformers packages:
    pip install chromadb sentence-transformers
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from main import AnimeVideoGenerator
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_character_analysis():
    """
    Demonstrate comprehensive character analysis features.
    
    This function showcases the main character analysis capabilities including:
    1. Character profile analysis from episode transcripts
    2. Semantic search for character moments and dialogue
    3. Character similarity analysis using vector embeddings
    4. Relationship mapping between characters
    5. Character development tracking over time
    6. Database statistics and insights
    
    The demonstration uses sample transcript data to show functionality
    and provides guidance on using the character analysis system with
    real episode data.
    
    Returns:
        None: All output is displayed to console
        
    Raises:
        Exception: When character analysis agent initialization fails
        ImportError: When ChromaDB dependencies are missing
        
    Note:
        Requires ChromaDB and sentence-transformers to be installed.
        With more processed episodes, analysis results become richer.
    """
    
    print("🎭 Character Analysis Demo")
    print("=" * 50)
    
    # Initialize the generator
    try:
        generator = AnimeVideoGenerator()
        
        if not generator.character_agent:
            print("❌ Character analysis not available. Please install ChromaDB dependencies:")
            print("   pip install chromadb sentence-transformers")
            return
            
        print("✅ Character analysis agent initialized successfully")
        
        # Sample transcript for demonstration
        sample_transcript = """
        Izuku: I want to become a hero who can save everyone with a smile, just like All Might!
        All Might: Young Midoriya, being a hero means more than just having power. It requires courage, determination, and the will to help others.
        Bakugo: Deku! You think you can surpass me? Never! I'm going to be the number one hero!
        Izuku: Kacchan, I know I'm not strong yet, but I won't give up! I'll keep training and become stronger!
        All Might: The heart of a true hero... that's what you have, my boy. Your determination inspires others.
        Bakugo: Tch! Whatever! I'll show you what real strength looks like! I don't need anyone's help!
        Ochaco: Deku-kun, your determination is amazing! You never give up, even when things get tough.
        Izuku: Uraraka-san, thank you for believing in me. Together, we can all become great heroes!
        Iida: As class representative, I must say that teamwork is essential for all aspiring heroes!
        Bakugo: I work alone! I don't need any of you extras slowing me down!
        """
        
        # Step 1: Analyze characters in the sample episode
        print("\n1️⃣ Analyzing Characters in Sample Episode...")
        print("-" * 40)
        
        # First, let's add this to our database (simulating episode processing)
        result = generator.analyze_episode_characters("My Hero Academia", 1, 1)
        
        if 'error' in result:
            # If no existing data, analyze the sample directly
            print("No existing episode data, analyzing sample transcript...")
            character_profiles = generator.character_agent.analyze_episode_characters(
                "My Hero Academia", 1, 1, sample_transcript
            )
            
            print(f"Found {len(character_profiles)} characters:")
            for name, profile in character_profiles.items():
                print(f"  🎭 {name}:")
                print(f"     Dialogue Count: {profile.total_dialogue_count}")
                print(f"     Personality Traits: {', '.join(profile.personality_traits) or 'None detected'}")
                print(f"     Relationships: {list(profile.relationships.keys()) or 'None yet'}")
        else:
            print("Using existing episode data:")
            for char_name, profile in result['characters'].items():
                print(f"  🎭 {char_name}:")
                print(f"     Dialogue Count: {profile['dialogue_count']}")
                print(f"     Personality Traits: {', '.join(profile['personality_traits']) or 'None detected'}")
        
        # Step 2: Search for character moments
        print("\n2️⃣ Searching for Character Moments...")
        print("-" * 40)
        
        search_queries = [
            "determined hero never give up",
            "strength and power",
            "teamwork and friendship"
        ]
        
        for query in search_queries:
            print(f"\n🔍 Query: '{query}'")
            moments = generator.search_character_moments(query, limit=3)
            
            if moments:
                for i, moment in enumerate(moments, 1):
                    print(f"  {i}. {moment['character_name']} (Score: {moment['relevance_score']:.3f})")
                    print(f"     {moment['content_preview'][:100]}...")
            else:
                print("  No moments found")
        
        # Step 3: Find similar characters
        print("\n3️⃣ Finding Similar Characters...")
        print("-" * 40)
        
        test_characters = ["Izuku", "Bakugo", "All Might"]
        
        for char_name in test_characters:
            print(f"\n👥 Characters similar to {char_name}:")
            similar_chars = generator.find_similar_characters(char_name, limit=3)
            
            if similar_chars:
                for i, char in enumerate(similar_chars, 1):
                    print(f"  {i}. {char['character_name']} ({char['show_name']})")
                    print(f"     Similarity: {char['similarity_score']:.3f}")
                    print(f"     Traits: {', '.join(char['personality_traits'])}")
            else:
                print("  No similar characters found yet")
        
        # Step 4: Analyze character relationships
        print("\n4️⃣ Character Relationships...")
        print("-" * 40)
        
        for char_name in ["Izuku", "Bakugo"]:
            print(f"\n🤝 Relationships for {char_name}:")
            relationships = generator.get_character_relationships(char_name)
            
            if 'error' not in relationships and relationships['relationships']:
                for other_char, rel_data in relationships['relationships'].items():
                    print(f"  → {other_char}:")
                    print(f"    Interactions: {rel_data['interaction_count']}")
                    print(f"    Strength: {rel_data['relationship_strength']:.2f}")
                    print(f"    Type: {rel_data['primary_interaction_type']}")
            else:
                print("  No relationships found yet")
        
        # Step 5: Character development analysis
        print("\n5️⃣ Character Development Analysis...")
        print("-" * 40)
        
        for char_name in ["Izuku", "Bakugo"]:
            print(f"\n📈 Development for {char_name}:")
            development = generator.analyze_character_development(char_name, "My Hero Academia")
            
            if 'error' not in development:
                print(f"  Episodes: {development['total_episodes']}")
                print(f"  Development Score: {development['development_score']:.2f}")
                
                if development['personality_evolution']:
                    print("  Trait Evolution:")
                    for trait, evolution in development['personality_evolution'].items():
                        print(f"    {trait}: {evolution['trend']}")
            else:
                print("  Insufficient data for development analysis")
        
        # Step 6: Database statistics
        print("\n6️⃣ Character Database Statistics...")
        print("-" * 40)
        
        stats = generator.get_character_statistics()
        
        if 'error' not in stats:
            print(f"📊 Character Profiles: {stats['total_character_profiles']}")
            print(f"📊 Interactions: {stats['total_interactions']}")
            print(f"📊 Unique Characters: {stats['unique_characters']}")
            print(f"📊 Shows Analyzed: {stats['unique_shows']}")
            
            if stats['shows_analyzed']:
                print(f"📚 Shows: {', '.join(stats['shows_analyzed'])}")
        else:
            print("No statistics available yet")
        
        print("\n✅ Character Analysis Demo Completed!")
        print("\n💡 Tips for using character analysis:")
        print("  • Process multiple episodes to build character development data")
        print("  • Use semantic search to find specific character moments")
        print("  • Analyze character relationships across episodes")
        print("  • Track personality trait evolution over time")
        print("  • Compare characters across different shows")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")


def demo_advanced_features():
    """
    Demonstrate advanced character analysis features and semantic search.
    
    This function showcases sophisticated character analysis capabilities:
    1. Advanced semantic search with contextual queries
    2. Thematic moment discovery (heroism, growth, relationships)
    3. Emotional scene identification
    4. Complex character interaction analysis
    5. Cross-episode character development patterns
    
    The advanced features leverage ChromaDB's vector similarity search
    to find semantically related character moments across episodes,
    enabling sophisticated character analysis workflows.
    
    Returns:
        None: Results displayed to console with examples and explanations
        
    Raises:
        Exception: When character analysis agent is not available
        ImportError: When required dependencies are missing
        
    Note:
        Advanced features require substantial character data to show
        meaningful results. Process multiple episodes for best results.
    """
    
    print("\n\n🚀 Advanced Character Analysis Features")
    print("=" * 50)
    
    try:
        generator = AnimeVideoGenerator()
        
        if not generator.character_agent:
            print("❌ Advanced features require ChromaDB dependencies")
            return
        
        # Advanced search examples
        print("\n🔍 Advanced Semantic Searches:")
        print("-" * 30)
        
        advanced_queries = [
            ("heroic moments", "Find scenes where characters show heroism"),
            ("character growth", "Find moments of character development"),
            ("emotional scenes", "Find emotionally significant moments"),
            ("rivalry and competition", "Find rivalry/competition scenes"),
            ("friendship and support", "Find friendship/support moments")
        ]
        
        for query, description in advanced_queries:
            print(f"\n📝 {description}:")
            print(f"   Query: '{query}'")
            
            moments = generator.search_character_moments(query, limit=2)
            
            if moments:
                for moment in moments:
                    print(f"   → {moment['character_name']}: {moment['relevance_score']:.3f}")
            else:
                print("   → No matches found")
        
        print("\n💡 The character analysis system learns from more data!")
        print("   Process more episodes to see richer analysis results.")
        
    except Exception as e:
        logger.error(f"Advanced demo failed: {e}")


if __name__ == "__main__":
    print("🎬 Starting Character Analysis Demonstration")
    print("This demo showcases ChromaDB-powered character analysis")
    
    try:
        demo_character_analysis()
        demo_advanced_features()
        
        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("\nTo get started with character analysis:")
        print("1. Install dependencies: pip install chromadb sentence-transformers")
        print("2. Process some episodes: python main.py process-episode 'My Hero Academia' 1 1")
        print("3. Analyze characters: python main.py analyze-characters 'My Hero Academia' 1 1")
        print("4. Search moments: python main.py search-character-moments 'heroic determination'")
        
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n💥 Demo failed with error: {e}")
