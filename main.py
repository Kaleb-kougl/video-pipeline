#!/usr/bin/env python3
"""
Main entry point for the anime video generation system.

This is the refactored version using a modular architecture.
"""

import argparse
import asyncio
import logging
import os
import random
import sys
import time
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agents.character_analysis_agent import CharacterAnalysisAgent
from agents.config_manager import EpisodeConfigManager
from agents.content_agent import ContentAgent
from agents.discovery_agent import EpisodeDiscoveryAgent
from agents.quality_agent import QualityAssuranceAgent
from agents.transcript_agent import TranscriptDiscoveryAgent
from agents.transcript_source_agent import TranscriptSourceDiscoveryAgent
from agents.video_agent import VideoGenerationAgent
from agents.workflow_orchestrator import WorkflowOrchestrator
from config.settings import get_settings
from core.database import DatabaseManager
from core.schemas import ProcessingResult
from media.format_exporters import (
    InstagramReelsExporter,
    TikTokExporter,
    TwitterVideoExporter,
    YouTubeShortsExporter,
)
from media.media_utils import create_images, mp4_file_enhanced, wave_file
from utils.vector_search import VectorSearchManager


# Set up logging
def setup_logging():
    """Configure logging for the application."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("anime_generator.log")],
    )


logger = logging.getLogger(__name__)


class AnimeVideoGenerator:
    """Main application class for anime video generation."""

    def __init__(self):
        """Initialize the anime video generator with all modular agents."""
        self.settings = get_settings()
        self.db = DatabaseManager(self.settings.database_path)

        # Initialize AI model for content agents
        try:
            from langchain.chat_models import init_chat_model

            self.model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
        except Exception as e:
            # Fallback if langchain or credentials are not available
            self.model = None
            logger.warning(f"AI model not available: {e}")

        # Initialize all agents
        self.transcript_agent = TranscriptDiscoveryAgent()
        self.transcript_source_agent = TranscriptSourceDiscoveryAgent()
        self.content_agent = ContentAgent(self.model) if self.model else None
        self.video_agent = VideoGenerationAgent()
        self.quality_agent = QualityAssuranceAgent()
        self.discovery_agent = EpisodeDiscoveryAgent()
        self.config_manager = EpisodeConfigManager()
        self.orchestrator = WorkflowOrchestrator()

        # Initialize character analysis agent (optional)
        try:
            self.character_agent = CharacterAnalysisAgent()
            logger.info("Character analysis enabled with ChromaDB backend")
        except ImportError:
            self.character_agent = None
            logger.info("Character analysis disabled (missing ChromaDB dependencies)")

        # Initialize vector search manager (optional)
        try:
            self.vector_search = VectorSearchManager()
            logger.info("Vector search enabled")
        except Exception as e:
            self.vector_search = None
            logger.info(f"Vector search disabled: {e}")

        # Create output directory if it doesn't exist
        os.makedirs(self.settings.output_directory, exist_ok=True)

        logger.info("Anime Video Generator initialized")

    async def process_episode_by_url(self, url: str, show_name: str) -> ProcessingResult:
        """
        Process an episode given its URL using the complete modular workflow.

        Args:
            url (str): The URL of the episode transcript
            show_name (str): The name of the show

        Returns:
            ProcessingResult: Result of the processing
        """
        logger.info(f"Processing episode from URL: {url}")

        try:
            # Use the workflow orchestrator for complete processing with Phase 2 enhancement
            result = await self.orchestrator.process_episode_from_url(url, show_name, self.db)

            if result.success:
                logger.info(f"Successfully processed episode from URL: {url}")
            else:
                logger.error(f"Failed to process episode from URL: {result.error}")

            return result

        except Exception as e:
            logger.error(f"Processing failed for URL {url}: {e}")
            return ProcessingResult(success=False, error=str(e))

    async def process_episode_by_numbers(
        self,
        show_name: str,
        season: int,
        episode: int,
        episode_title: str = None,
        full_processing: bool = True,
    ) -> ProcessingResult:
        """
        Process an episode by show name, season, and episode numbers using complete workflow.

        Args:
            show_name (str): The name of the show
            season (int): Season number
            episode (int): Episode number
            episode_title (str, optional): Episode title for better matching
            full_processing (bool): Whether to do full AI/video processing or just transcript discovery

        Returns:
            ProcessingResult: Result of the processing
        """
        logger.info(f"Processing {show_name} Season {season} Episode {episode}")

        try:
            if full_processing:
                # Use the workflow orchestrator for complete processing with Phase 2 enhancement
                result = await self.orchestrator.process_episode_complete(
                    show_name, season, episode, episode_title, self.db
                )
            else:
                # Just do transcript discovery and save to database
                # Use enhanced discovery agent for better URL finding
                discovery_result = self.discovery_agent.search_episode_enhanced(
                    show_name, season, episode, episode_title
                )

                if not discovery_result or not discovery_result.get("url"):
                    return ProcessingResult(
                        success=False,
                        error=f"No episode URL found for {show_name} Season {season} Episode {episode}",
                    )

                # Parse transcript from discovered URL
                transcript_result = self.transcript_agent.parse_discovered_url(
                    discovery_result["url"], discovery_result["source"]
                )

                if not transcript_result or not transcript_result.get("transcript"):
                    return ProcessingResult(
                        success=False,
                        error=f"Failed to parse transcript from discovered URL: {discovery_result['url']}",
                    )

                # Save transcript to database
                self.db.save_episode(
                    show=show_name,
                    season=str(season),
                    episode=str(episode),
                    url=discovery_result["url"],
                    transcript=transcript_result["transcript"],
                )

                result = ProcessingResult(
                    success=True,
                    data={
                        "show": show_name,
                        "season": season,
                        "episode": episode,
                        "transcript_url": discovery_result["url"],
                        "transcript_source": discovery_result["source"],
                        "quality_score": transcript_result["quality_score"],
                    },
                )

            if result.success:
                logger.info(f"Successfully processed {show_name} S{season}E{episode}")
            else:
                logger.error(f"Failed to process {show_name} S{season}E{episode}: {result.error}")

            return result

        except Exception as e:
            logger.error(f"Processing failed for {show_name} S{season}E{episode}: {e}")
            return ProcessingResult(success=False, error=str(e))

    async def process_season_batch(
        self,
        show_name: str,
        season: int,
        start_episode: int = None,
        end_episode: int = None,
        full_processing: bool = False,
    ):
        """
        Process multiple episodes in a season using modular workflow.

        Args:
            show_name (str): The name of the show
            season (int): Season number
            start_episode (int, optional): Starting episode number
            end_episode (int, optional): Ending episode number
            full_processing (bool): Whether to do full AI/video processing
        """
        # Get episode range from config manager
        from config.settings import EpisodeConfigs

        max_episodes = EpisodeConfigs.get_season_episodes(show_name, season)
        if not max_episodes:
            logger.error(f"No configuration found for {show_name} season {season}")
            return

        if start_episode is None:
            start_episode = 1
        if end_episode is None:
            end_episode = max_episodes

        logger.info(
            f"Processing {show_name} Season {season}, Episodes {start_episode}-{end_episode}"
        )
        logger.info(
            f"Full processing: {'enabled' if full_processing else 'disabled (transcript only)'}"
        )

        successful = 0
        failed = 0

        for ep_num in range(start_episode, end_episode + 1):
            episode_config = self.config_manager.get_episode_config(show_name, season, ep_num)
            episode_title = episode_config.get("title") if episode_config else None

            result = await self.process_episode_by_numbers(
                show_name, season, ep_num, episode_title, full_processing
            )

            if result.success:
                successful += 1
            else:
                failed += 1
                logger.error(f"Failed to process episode {ep_num}: {result.error}")

            # Add delay between episodes to be respectful to servers
            time.sleep(random.uniform(2, 5))

        logger.info(f"Batch processing complete: {successful} successful, {failed} failed")

    async def process_season(
        self,
        show_name: str,
        season: int,
        force_reprocess: bool = False,
        target_minutes: int = None,
        export_format: str = "standard",
    ) -> ProcessingResult:
        """
        Comprehensive season processing with configurable video length.

        This function:
        1. Analyzes character development and relationships across all episodes
        2. Creates a configurable-length summary of the season (5-15 minutes)
        3. Stores the summary for future analysis
        4. Generates images from summary concepts
        5. Creates YouTube transcript and voice recording
        6. Produces final MP4 video

        Args:
            show_name (str): The name of the show
            season (int): Season number
            force_reprocess (bool): Whether to reprocess even if summary exists
            target_minutes (int): Target video length in minutes (5-15)
            export_format (str): Target export format (standard, youtube_shorts, tiktok, instagram_reels, twitter)

        Returns:
            ProcessingResult: Result of the season processing
        """
        logger.info(f"🎬 Starting comprehensive season processing for {show_name} Season {season}")

        if target_minutes:
            logger.info(f"🎯 Target video length: {target_minutes} minutes")

        try:
            # Step 1: Check if season summary already exists
            existing_summary = self.db.get_season_summary(show_name, season)
            if existing_summary and not force_reprocess:
                logger.info(f"Season summary already exists for {show_name} S{season}")
                return ProcessingResult(
                    success=True,
                    data={
                        "message": "Season summary already exists",
                        "existing_summary": existing_summary,
                        "use_force_reprocess": "Set force_reprocess=True to regenerate",
                    },
                )

            # Step 2: Ensure all episodes have transcripts
            logger.info("📚 Ensuring all episodes have transcripts...")
            from config.settings import EpisodeConfigs

            episode_count = EpisodeConfigs.get_season_episodes(show_name, season)
            if not episode_count:
                # Try to discover episodes
                discovered_episodes = self.discover_show_episodes(show_name, season)
                episode_count = (
                    len(discovered_episodes) if discovered_episodes else 12
                )  # Default fallback

            # Process episodes to ensure transcripts are available
            transcript_errors = []
            for ep_num in range(1, episode_count + 1):
                episode_data = self.db.get_episode(show_name, season, ep_num)
                if not episode_data or not episode_data["transcript"]:
                    logger.info(f"Processing transcript for S{season}E{ep_num}")
                    result = await self.process_episode_by_numbers(
                        show_name, season, ep_num, full_processing=False
                    )
                    if not result.success:
                        transcript_errors.append(f"S{season}E{ep_num}: {result.error}")

                # Add delay to be respectful to servers
                time.sleep(random.uniform(1, 3))

            if transcript_errors:
                logger.warning(f"Some transcripts failed to process: {transcript_errors}")

            # Step 3: Calculate video structure
            video_config = self._calculate_video_structure(target_minutes)
            logger.info(f"📊 Video structure: {video_config}")

            # Step 4: Perform comprehensive season analysis
            logger.info("🔍 Analyzing character development and relationships...")
            season_analysis = self.analyze_season_development(show_name, season)

            if "error" in season_analysis:
                return ProcessingResult(
                    success=False, error=f"Season analysis failed: {season_analysis['error']}"
                )

            # Step 5: Generate length-adaptive summary
            target_min = target_minutes or 5
            logger.info(f"📝 Generating {target_min}-minute chronological summary...")
            season_summary = self._generate_season_summary_with_length(
                show_name, season, season_analysis, target_min
            )

            if not season_summary:
                return ProcessingResult(success=False, error="Failed to generate season summary")

            # Step 5: Store initial summary in database
            logger.info("💾 Storing season summary...")

            # Step 6: Parse summary into chronological ideas for images
            logger.info("🎨 Parsing summary into visual concepts...")
            visual_concepts = self._parse_summary_to_concepts(season_summary, target_min)

            # Step 7: Generate images from concepts
            logger.info(f"🖼️ Generating {len(visual_concepts)} images...")
            print(f"🎨 GENERATING {len(visual_concepts)} IMAGES...")
            print(
                "💡 TIP: Upgrade to Google Cloud billing for AI-generated anime artwork, or enjoy free placeholder images!"
            )
            self._generate_season_images(visual_concepts, show_name, season)

            # Step 8: Create YouTube transcript
            logger.info("📺 Creating YouTube transcript...")
            youtube_transcript = self._create_youtube_transcript(season_summary, show_name, season)

            # Step 9: Convert to voice recording
            logger.info("🎤 Converting to voice recording...")
            print("🎙️  GENERATING AUDIO NARRATION...")
            print(
                "💡 TIP: Upgrade to Google Cloud billing for professional AI voice-over, or use free silent audio!"
            )
            audio_file = self._create_voice_recording(youtube_transcript, show_name, season)

            # Step 10: Create final MP4 video
            logger.info("🎬 Creating final MP4 video...")
            video_file = self._create_season_video(audio_file, visual_concepts, show_name, season)

            # Step 10.5: Export in specified format if not standard
            export_result = self.export_video_format(
                show_name, season, visual_concepts, audio_file, export_format
            )

            export_skipped = export_result.get("status") == "skipped_not_implemented"
            if export_skipped:
                logger.warning(
                    f"⚠️ Platform export '{export_format}' was skipped: it is not implemented, "
                    f"so no {export_format} file exists. Only the standard MP4 was produced."
                )
                print(
                    f"⚠️  {export_format} export SKIPPED - platform export is not implemented. "
                    f"No {export_format} file was created; the standard MP4 is available."
                )

            # Step 11: Store media file information in database
            # Never persist an export record that claims a file exists when it does not.
            media_files = {
                "audio_file": audio_file,
                "video_file": video_file,
                "image_count": len(visual_concepts),
                "youtube_transcript": youtube_transcript,
                "export_format": "standard" if export_skipped else export_format,
                "requested_export_format": export_format,
                "export_result": export_result,
            }

            # Update the database entry with media files
            summary_id = self.db.save_season_summary(
                show_name, season, season_summary, season_analysis, media_files
            )

            logger.info(f"✅ Season processing completed successfully for {show_name} S{season}")

            # Add helpful message about free vs paid features
            print("\n" + "=" * 70)
            print("🎉 VIDEO GENERATION COMPLETE!")
            print("=" * 70)
            print("📁 Your video includes:")
            print("   🖼️  Beautiful placeholder images (upgrade for AI artwork)")
            print("   🔇 Silent audio track (upgrade for AI narration)")
            print("   🎬 Professional video compilation")
            print("\n💰 Want premium AI features?")
            print("   • Enable Google Cloud billing for AI-generated images & voice")
            print("   • Cost: ~$0.43 per 10-minute video")
            print("   • No code changes needed - just enable billing!")
            print("=" * 70)

            return ProcessingResult(
                success=True,
                data={
                    "show_name": show_name,
                    "season": season,
                    "summary_id": summary_id,
                    "summary": season_summary,
                    "video_config": video_config,  # Include video configuration
                    "target_duration_minutes": target_min,
                    "analysis_insights": {
                        "total_characters": season_analysis["character_insights"][
                            "total_characters"
                        ],
                        "total_episodes": season_analysis["season_info"]["total_episodes"],
                        "pivotal_moments": season_analysis["story_insights"][
                            "pivotal_moments_count"
                        ],
                        "dominant_themes": season_analysis["story_insights"]["dominant_themes"][:3],
                    },
                    "media_files": media_files,
                    "processing_stats": {
                        "transcript_errors": len(transcript_errors),
                        "failed_episodes": transcript_errors if transcript_errors else None,
                    },
                },
            )

        except Exception as e:
            logger.error(f"Season processing failed for {show_name} S{season}: {e}")
            return ProcessingResult(success=False, error=str(e))

    def get_stats(self):
        """Get processing statistics."""
        return self.db.get_processing_stats()

    def analyze_episode_quality(self, show_name: str, season: int, episode: int) -> dict:
        """Analyze episode quality across all stages."""
        try:
            # Get episode data from database
            episode_data = self.db.get_episode(show_name, season, episode)

            if not episode_data:
                logger.warning(f"No data found for {show_name} S{season}E{episode}")
                return None

            # Perform comprehensive quality analysis
            quality_report = self.quality_agent.validate_complete_workflow(
                transcript_data=episode_data["transcript_data"],
                content_data=episode_data["content_data"],
                video_data=episode_data["video_data"],
                discovery_data=episode_data["discovery_data"],
                workflow_data=episode_data["workflow_data"],
                show_name=show_name,
            )

            return quality_report

        except Exception as e:
            logger.error(f"Quality analysis failed for {show_name} S{season}E{episode}: {e}")
            return None

    def discover_show_episodes(self, show_name: str, season: int = None) -> list[dict]:
        """Discover available episodes for a show."""
        try:
            if season:
                episodes = self.discovery_agent.discover_season_episodes(show_name, season)
            else:
                episodes = self.discovery_agent.discover_all_episodes(show_name)

            return episodes

        except Exception as e:
            logger.error(f"Episode discovery failed for {show_name}: {e}")
            return []

    def generate_content_summary(self, show_name: str, season: int, episode: int) -> str:
        """Generate AI content summary for an episode."""
        try:
            # Get episode data from database
            episode_data = self.db.get_episode(show_name, season, episode)

            if not episode_data or not episode_data["transcript"]:
                logger.warning(f"No transcript data found for {show_name} S{season}E{episode}")
                return None

            # Generate the summary through the orchestrator. ContentAgent has no
            # transcript-to-summary method -- it only exposes extract_and_analyze(url) --
            # so the call that used to be here (content_agent.generate_episode_summary)
            # raised AttributeError into the handler below and returned None on every
            # invocation, making `summarize` silently do nothing.
            result = self.orchestrator.generate_structured_summary(
                {"transcript": episode_data["transcript"]}, show_name
            )
            if not result:
                logger.warning(f"Summary generation returned nothing for {show_name}")
                return None

            return result.get("youtube_transcript")

        except Exception as e:
            logger.error(
                f"Content summary generation failed for {show_name} S{season}E{episode}: {e}"
            )
            return None

    def analyze_episode_characters(self, show_name: str, season: int, episode: int) -> dict:
        """Analyze characters in an episode using ChromaDB-powered character analysis."""
        try:
            if not self.character_agent:
                logger.warning("Character analysis not available (ChromaDB dependencies missing)")
                return {"error": "Character analysis not available"}

            # Get episode data from database
            episode_data = self.db.get_episode(show_name, season, episode)

            if not episode_data or not episode_data["transcript"]:
                logger.warning(f"No transcript data found for {show_name} S{season}E{episode}")
                return {"error": "No transcript data found"}

            # Use character analysis agent
            character_profiles = self.character_agent.analyze_episode_characters(
                show_name, season, episode, episode_data["transcript"]
            )

            # Convert profiles to serializable format
            serializable_profiles = {}
            for name, profile in character_profiles.items():
                serializable_profiles[name] = {
                    "name": profile.name,
                    "dialogue_count": profile.total_dialogue_count,
                    "personality_traits": profile.personality_traits,
                    "relationships": profile.relationships,
                    "first_appearance": profile.first_appearance,
                }

            return {
                "episode": f"{show_name} S{season}E{episode}",
                "characters": serializable_profiles,
                "total_characters": len(serializable_profiles),
                "analysis_completed": True,
            }

        except Exception as e:
            logger.error(f"Character analysis failed for {show_name} S{season}E{episode}: {e}")
            return {"error": str(e)}

    def find_similar_characters(
        self, character_name: str, show_name: str = None, limit: int = 5
    ) -> list[dict]:
        """Find characters similar to the given character across all analyzed episodes."""
        try:
            if not self.character_agent:
                logger.warning("Character analysis not available (ChromaDB dependencies missing)")
                return []

            similar_chars = self.character_agent.find_similar_characters(
                character_name, show_name, limit
            )

            return similar_chars

        except Exception as e:
            logger.error(f"Similar character search failed for {character_name}: {e}")
            return []

    def analyze_character_development(self, character_name: str, show_name: str) -> dict:
        """Analyze how a character develops across episodes."""
        try:
            if not self.character_agent:
                logger.warning("Character analysis not available (ChromaDB dependencies missing)")
                return {"error": "Character analysis not available"}

            development_analysis = self.character_agent.analyze_character_development(
                character_name, show_name
            )

            return development_analysis

        except Exception as e:
            logger.error(f"Character development analysis failed for {character_name}: {e}")
            return {"error": str(e)}

    def get_character_relationships(self, character_name: str, show_name: str = None) -> dict:
        """Get relationship map for a character."""
        try:
            if not self.character_agent:
                logger.warning("Character analysis not available (ChromaDB dependencies missing)")
                return {"error": "Character analysis not available"}

            relationships = self.character_agent.get_character_relationships(
                character_name, show_name
            )

            return relationships

        except Exception as e:
            logger.error(f"Character relationship analysis failed for {character_name}: {e}")
            return {"error": str(e)}

    def search_character_moments(
        self, query: str, character_name: str = None, show_name: str = None, limit: int = 10
    ) -> list[dict]:
        """Search for specific character moments using semantic search."""
        try:
            if not self.character_agent:
                logger.warning("Character analysis not available (ChromaDB dependencies missing)")
                return []

            moments = self.character_agent.search_character_moments(
                query, character_name, show_name, limit
            )

            return moments

        except Exception as e:
            logger.error(f"Character moment search failed: {e}")
            return []

    def get_character_statistics(self) -> dict:
        """Get overall statistics about the character database."""
        try:
            if not self.character_agent:
                logger.warning("Character analysis not available (ChromaDB dependencies missing)")
                return {"error": "Character analysis not available"}

            stats = self.character_agent.get_character_statistics()
            return stats

        except Exception as e:
            logger.error(f"Character statistics retrieval failed: {e}")
            return {"error": str(e)}

    def analyze_season_development(self, show_name: str, season: int) -> dict:
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
            if not self.character_agent:
                logger.warning("Character analysis not available (ChromaDB dependencies missing)")
                return {"error": "Character analysis not available"}

            logger.info(f"Starting comprehensive season analysis for {show_name} Season {season}")

            # Perform season analysis using the character agent
            season_analysis = self.character_agent.analyze_season_development(show_name, season)

            if "error" in season_analysis:
                logger.error(f"Season analysis failed: {season_analysis['error']}")
                return season_analysis

            # Add additional insights and formatting
            analysis_summary = {
                "season_info": {
                    "show_name": show_name,
                    "season": season,
                    "total_episodes": season_analysis["total_episodes"],
                    "episode_range": season_analysis["episode_range"],
                },
                "character_insights": {
                    "total_characters": len(season_analysis["character_development"]),
                    "character_development_scores": {
                        name: arc["character_growth_score"]
                        for name, arc in season_analysis["character_development"].items()
                    },
                    "top_developing_characters": sorted(
                        [
                            (name, arc["character_growth_score"])
                            for name, arc in season_analysis["character_development"].items()
                        ],
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5],
                    "character_focus_distribution": season_analysis["character_focus_distribution"][
                        "main_characters"
                    ][:5],
                },
                "story_insights": {
                    "pivotal_moments_count": len(season_analysis["pivotal_moments"]),
                    "dominant_themes": season_analysis["thematic_evolution"][
                        "dominant_season_themes"
                    ][:5],
                    "narrative_arcs": len(
                        season_analysis["narrative_progression"].get("story_arcs", [])
                    ),
                    "thematic_diversity": season_analysis["thematic_evolution"][
                        "thematic_diversity_score"
                    ],
                },
                "relationship_insights": {
                    "total_relationships": len(season_analysis["relationship_evolution"]),
                    "strongest_relationships": sorted(
                        [
                            (rel_key, rel_data["relationship_strength"])
                            for rel_key, rel_data in season_analysis[
                                "relationship_evolution"
                            ].items()
                        ],
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5],
                    "relationship_types": {
                        rel_key: rel_data["relationship_classification"]
                        for rel_key, rel_data in season_analysis["relationship_evolution"].items()
                    },
                },
                "episode_analysis": {
                    "most_significant_episodes": sorted(
                        [
                            (ep_key, ep_data["significance_score"])
                            for ep_key, ep_data in season_analysis[
                                "episode_significance_scores"
                            ].items()
                        ],
                        key=lambda x: x[1],
                        reverse=True,
                    )[:3],
                    "episode_types_distribution": {
                        ep_key: ep_data["episode_type"]
                        for ep_key, ep_data in season_analysis[
                            "episode_significance_scores"
                        ].items()
                    },
                },
                "raw_analysis": season_analysis,  # Include full analysis for detailed inspection
            }

            logger.info(f"Season analysis completed successfully for {show_name} Season {season}")
            return analysis_summary

        except Exception as e:
            logger.error(f"Season development analysis failed for {show_name} Season {season}: {e}")
            return {"error": str(e)}

    def _generate_season_summary_with_length(
        self, show_name: str, season: int, season_analysis: dict, target_minutes: int
    ) -> str:
        """
        Generate a length-adaptive chronological summary of the season.

        Args:
            show_name: Name of the show
            season: Season number
            season_analysis: Analysis data from analyze_season_development
            target_minutes: Target video length in minutes

        Returns:
            String containing the formatted summary
        """
        try:
            if not self.content_agent or not self.model:
                # No AI model available - the length-adaptive prompt is useless
                # without one, so fall back to the deterministic basic summary.
                return self._generate_basic_season_summary(show_name, season, season_analysis)

            # Build the prompt whose section timings are scaled to target_minutes
            length_prompt = self._generate_length_adaptive_prompt(
                show_name, season, season_analysis, target_minutes
            )

            # Actually use it. Previously this result was discarded and the
            # fixed 5-minute prompt from _generate_season_summary was used
            # instead, which silently ignored target_minutes.
            response = self.model.invoke(length_prompt)
            return response.content if hasattr(response, "content") else str(response)

        except Exception as e:
            logger.error(f"Length-adaptive summary generation failed: {e}")
            # Fallback to the fixed-length summary generator
            return self._generate_season_summary(show_name, season, season_analysis)

    def _generate_season_summary(self, show_name: str, season: int, season_analysis: dict) -> str:
        """
        Generate a comprehensive 5-minute chronological summary of the season.

        Args:
            show_name: Name of the show
            season: Season number
            season_analysis: Analysis data from analyze_season_development

        Returns:
            String containing the formatted 5-minute summary
        """
        try:
            if not self.content_agent or not self.model:
                # Fallback to basic summary generation
                return self._generate_basic_season_summary(show_name, season, season_analysis)

            # Create a structured prompt for AI summary generation
            summary_prompt = f"""
            Create a comprehensive 5-minute chronological summary of {show_name} Season {season}.
            This summary will be used to create a video, so structure it with clear narrative flow.
            
            Based on the following analysis data:
            
            SEASON OVERVIEW:
            - Total Episodes: {season_analysis["season_info"]["total_episodes"]}
            - Episode Range: {season_analysis["season_info"]["episode_range"]}
            
            CHARACTER DEVELOPMENT:
            - Total Characters: {season_analysis["character_insights"]["total_characters"]}
            - Top Developing Characters: {", ".join([name for name, _ in season_analysis["character_insights"]["top_developing_characters"]])}
            
            STORY ELEMENTS:
            - Pivotal Moments: {season_analysis["story_insights"]["pivotal_moments_count"]}
            - Dominant Themes: {", ".join([theme for theme, _ in season_analysis["story_insights"]["dominant_themes"]])}
            - Narrative Arcs: {season_analysis["story_insights"]["narrative_arcs"]}
            
            RELATIONSHIPS:
            - Key Relationships: {", ".join([rel_key for rel_key, _ in season_analysis["relationship_insights"]["strongest_relationships"]])}
            
            SIGNIFICANT EPISODES:
            - Most Important: {", ".join([ep_key for ep_key, _ in season_analysis["episode_analysis"]["most_significant_episodes"]])}
            
            Please structure the summary as follows:
            1. Opening Hook (30 seconds): Introduce the season's central conflict/theme
            2. Character Arcs (90 seconds): Detail the main character developments
            3. Plot Progression (120 seconds): Chronological major story beats
            4. Relationship Evolution (60 seconds): Key relationship changes
            5. Climax and Resolution (60 seconds): Season finale and resolution
            
            Use engaging, descriptive language suitable for video narration.
            Include specific episode references and character moments.
            Ensure chronological flow and natural transitions between sections.
            """

            # Generate the summary using the AI model
            response = self.model.invoke(summary_prompt)
            summary = response.content if hasattr(response, "content") else str(response)

            return summary

        except Exception as e:
            logger.error(f"AI summary generation failed: {e}")
            # Fallback to basic summary
            return self._generate_basic_season_summary(show_name, season, season_analysis)

    def _generate_basic_season_summary(
        self, show_name: str, season: int, season_analysis: dict
    ) -> str:
        """Fallback method to generate basic season summary without AI."""
        try:
            summary_parts = []

            # Opening
            summary_parts.append(
                f"Season {season} of {show_name} presents a complex narrative spanning {season_analysis['season_info']['total_episodes']} episodes."
            )

            # Character development
            top_chars = [
                name
                for name, _ in season_analysis["character_insights"]["top_developing_characters"][
                    :3
                ]
            ]
            if top_chars:
                summary_parts.append(
                    f"The season focuses primarily on the development of {', '.join(top_chars)}, showcasing significant character growth throughout the arc."
                )

            # Themes
            themes = [
                theme for theme, _ in season_analysis["story_insights"]["dominant_themes"][:3]
            ]
            if themes:
                summary_parts.append(
                    f"Major themes explored include {', '.join(themes)}, woven throughout the season's narrative structure."
                )

            # Relationships
            relationships = [
                rel_key
                for rel_key, _ in season_analysis["relationship_insights"][
                    "strongest_relationships"
                ][:3]
            ]
            if relationships:
                summary_parts.append(
                    f"Key relationship dynamics involve {', '.join(relationships)}, evolving significantly across episodes."
                )

            # Significant episodes
            important_eps = [
                ep_key
                for ep_key, _ in season_analysis["episode_analysis"]["most_significant_episodes"][
                    :3
                ]
            ]
            if important_eps:
                summary_parts.append(
                    f"Pivotal episodes include {', '.join(important_eps)}, marking crucial turning points in the season's progression."
                )

            # Conclusion
            summary_parts.append(
                "The season culminates in a satisfying resolution while setting up future narrative possibilities."
            )

            return " ".join(summary_parts)

        except Exception as e:
            logger.error(f"Basic summary generation failed: {e}")
            return f"Season {season} of {show_name} - Analysis data available but summary generation failed."

    def _calculate_video_structure(self, target_minutes: int = None) -> dict[str, int]:
        """
        Calculate video timing structure based on target duration.

        Args:
            target_minutes: Target video length in minutes (5-15)

        Returns:
            Dictionary with timing structure in seconds
        """
        # Validate and set target duration
        if target_minutes is None:
            target_minutes = self.settings.video_config.default_duration_minutes

        target_minutes = max(self.settings.video_config.min_duration_minutes, target_minutes)
        target_minutes = min(self.settings.video_config.max_duration_minutes, target_minutes)

        total_seconds = target_minutes * 60

        return {
            "total_duration": total_seconds,
            "opening_hook": int(total_seconds * self.settings.video_config.opening_hook_ratio),
            "character_arcs": int(total_seconds * self.settings.video_config.character_arcs_ratio),
            "plot_progression": int(
                total_seconds * self.settings.video_config.plot_progression_ratio
            ),
            "relationship_evolution": int(
                total_seconds * self.settings.video_config.relationship_evolution_ratio
            ),
            "climax_resolution": int(
                total_seconds * self.settings.video_config.climax_resolution_ratio
            ),
        }

    def _calculate_visual_timing(self, target_minutes: int, concept_count: int) -> dict[str, float]:
        """
        Calculate visual concept timing based on video length.

        Args:
            target_minutes: Target video length
            concept_count: Number of visual concepts

        Returns:
            Visual timing configuration
        """
        total_seconds = target_minutes * 60
        available_time = total_seconds * 0.8  # 80% for visuals, 20% for transitions/effects

        concept_duration = available_time / concept_count

        # Apply min/max constraints
        concept_duration = max(self.settings.video_config.min_concept_duration, concept_duration)
        concept_duration = min(self.settings.video_config.max_concept_duration, concept_duration)

        # For 5-minute videos with 6 concepts, we want exactly 5.0 seconds per concept
        if target_minutes == 5 and concept_count == 6:
            concept_duration = 5.0

        return {
            "concept_duration": concept_duration,
            "total_concepts": concept_count,
            "transition_time": 0.5,
        }

    @staticmethod
    def _format_season_analysis_for_prompt(season_analysis: dict) -> str:
        """
        Render season analysis data as a prompt block.

        Tolerates partial or empty analysis data: any section that is missing
        is simply reported as unknown rather than raising, so prompt building
        never fails on incomplete input.

        Args:
            season_analysis: Analysis data from analyze_season_development

        Returns:
            An indented, human-readable block for embedding in an AI prompt
        """
        analysis = season_analysis or {}

        def names(section: str, key: str) -> str:
            """Join the first element of each (name, score) pair in a section."""
            pairs = analysis.get(section, {}).get(key, []) or []
            labels = [str(pair[0]) for pair in pairs if pair]
            return ", ".join(labels) if labels else "unknown"

        def value(section: str, key: str) -> str:
            found = analysis.get(section, {}).get(key)
            return "unknown" if found is None else str(found)

        return f"""        SEASON OVERVIEW:
        - Total Episodes: {value("season_info", "total_episodes")}
        - Episode Range: {value("season_info", "episode_range")}

        CHARACTER DEVELOPMENT:
        - Total Characters: {value("character_insights", "total_characters")}
        - Top Developing Characters: {names("character_insights", "top_developing_characters")}

        STORY ELEMENTS:
        - Pivotal Moments: {value("story_insights", "pivotal_moments_count")}
        - Dominant Themes: {names("story_insights", "dominant_themes")}
        - Narrative Arcs: {value("story_insights", "narrative_arcs")}

        RELATIONSHIPS:
        - Key Relationships: {names("relationship_insights", "strongest_relationships")}

        SIGNIFICANT EPISODES:
        - Most Important: {names("episode_analysis", "most_significant_episodes")}"""

    def _generate_length_adaptive_prompt(
        self, show_name: str, season: int, season_analysis: dict, target_minutes: int
    ) -> str:
        """
        Generate AI prompt adapted to target video length.

        Args:
            show_name: Name of the show
            season: Season number
            season_analysis: Season analysis data
            target_minutes: Target video length in minutes

        Returns:
            Length-appropriate AI prompt
        """
        structure = self._calculate_video_structure(target_minutes)

        # Base prompt structure
        prompt = f"""
        Create a comprehensive {target_minutes}-minute chronological summary of {show_name} Season {season}.
        This summary will be used to create a video, so structure it with clear narrative flow.

        Based on the following analysis data:
{self._format_season_analysis_for_prompt(season_analysis)}

        Please structure the summary with the following timing:
        """

        # Add adaptive timing instructions based on video length
        if target_minutes <= 5:
            prompt += """
            1. Opening Hook ({} seconds): Brief, punchy introduction
            2. Character Focus ({} seconds): Key character developments only  
            3. Plot Summary ({} seconds): Major story beats and conflicts
            4. Relationships ({} seconds): Critical relationship changes
            5. Resolution ({} seconds): Climax and conclusion
            
            Keep descriptions concise and impactful. Focus on the most essential elements.
            """.format(
                structure["opening_hook"],
                structure["character_arcs"],
                structure["plot_progression"],
                structure["relationship_evolution"],
                structure["climax_resolution"],
            )
        elif target_minutes <= 10:
            prompt += """
            1. Opening Hook ({} seconds): Engaging introduction with season themes
            2. Character Development ({} seconds): Detailed character arcs and growth with detailed analysis
            3. Plot Progression ({} seconds): Comprehensive story analysis with subplots
            4. Relationship Evolution ({} seconds): Complex relationship dynamics  
            5. Climax and Resolution ({} seconds): Detailed finale analysis
            
            Include specific episode references and character moments.
            Provide moderate depth while maintaining engagement.
            """.format(
                structure["opening_hook"],
                structure["character_arcs"],
                structure["plot_progression"],
                structure["relationship_evolution"],
                structure["climax_resolution"],
            )
        else:  # 10-15 minutes
            prompt += """
            1. Opening Hook ({} seconds): Comprehensive season introduction with context
            2. Character Development ({} seconds): In-depth character analysis with detailed arcs
            3. Plot Progression ({} seconds): Thorough story exploration including subplots and themes
            4. Relationship Evolution ({} seconds): Complex relationship analysis and development
            5. Climax and Resolution ({} seconds): Detailed finale analysis and implications
            
            Include detailed episode references, character quotes, and thematic analysis.
            Provide comprehensive exploration suitable for dedicated fans with detailed analysis.
            """.format(
                structure["opening_hook"],
                structure["character_arcs"],
                structure["plot_progression"],
                structure["relationship_evolution"],
                structure["climax_resolution"],
            )

        return prompt

    def _parse_summary_to_concepts(self, summary: str, target_minutes: int = 5) -> list[dict]:
        """
        Parse the season summary into visual concepts for image generation.

        Args:
            summary: The season summary text
            target_minutes: Target video length in minutes for timing calculation

        Returns:
            List of dictionaries containing image concepts
        """
        try:
            # Split summary into logical segments
            concepts = []

            # Simple approach: split by sentences and create concepts
            sentences = [s.strip() for s in summary.split(".") if s.strip()]

            # Group sentences into visual concepts (roughly 3-4 sentences per concept)
            concept_size = 3
            for i in range(0, len(sentences), concept_size):
                concept_sentences = sentences[i : i + concept_size]
                concept_text = ". ".join(concept_sentences) + "."

                # Create enhanced prompt for anime-style image generation
                enhanced_prompt = f"Anime style artwork depicting: {concept_text}. High quality digital art, vibrant colors, dynamic composition, professional anime illustration style."

                concepts.append(
                    {
                        "index": len(concepts),
                        "text": concept_text,
                        "enhanced_prompt": enhanced_prompt,
                    }
                )

            # Ensure we have at least 5 concepts for a good video
            while len(concepts) < 5:
                concepts.append(
                    {
                        "index": len(concepts),
                        "text": "Season highlights and memorable moments",
                        "enhanced_prompt": "Anime style montage artwork showing season highlights, multiple characters, dynamic action scenes, vibrant colors, high quality digital art.",
                    }
                )

            # Calculate adaptive timing for all concepts
            visual_timing = self._calculate_visual_timing(target_minutes, len(concepts))

            # Apply calculated duration to each concept
            for concept in concepts:
                concept["duration"] = visual_timing["concept_duration"]

            logger.info(f"Generated {len(concepts)} visual concepts from summary")
            return concepts

        except Exception as e:
            logger.error(f"Failed to parse summary to concepts: {e}")
            # Return basic concepts as fallback with adaptive timing
            fallback_concepts = [
                {
                    "index": i,
                    "text": f"Season concept {i + 1}",
                    "enhanced_prompt": f"Anime style artwork depicting season themes and characters, concept {i + 1}, high quality digital art.",
                }
                for i in range(5)
            ]

            # Apply adaptive timing to fallback concepts
            visual_timing = self._calculate_visual_timing(target_minutes, len(fallback_concepts))
            for concept in fallback_concepts:
                concept["duration"] = visual_timing["concept_duration"]

            return fallback_concepts

    def _generate_season_images(self, visual_concepts: list[dict], show_name: str, season: int):
        """
        Generate images for each visual concept.

        Args:
            visual_concepts: List of concept dictionaries
            show_name: Name of the show
            season: Season number
        """
        try:
            # Extract image prompts from concepts
            image_prompts = [concept["enhanced_prompt"] for concept in visual_concepts]

            # Use existing media utils function with correct parameter order
            create_images(image_prompts, f"Season_{season}", str(season), show_name)

            logger.info(f"Generated {len(visual_concepts)} images for season summary")

        except Exception as e:
            logger.error(f"Failed to generate season images: {e}")

    def _create_youtube_transcript(self, summary: str, show_name: str, season: int) -> str:
        """
        Create a YouTube-formatted transcript from the summary.

        Args:
            summary: Season summary text
            show_name: Name of the show
            season: Season number

        Returns:
            Formatted YouTube transcript
        """
        try:
            # Create YouTube-style formatting
            youtube_transcript = f"""
            Welcome to our {show_name} Season {season} summary!
            
            In this video, we'll explore the complete arc of Season {season}, covering character development, major plot points, and the season's most memorable moments.
            
            {summary}
            
            Thanks for watching! If you enjoyed this season summary, please like and subscribe for more anime content analysis.
            
            What was your favorite moment from Season {season}? Let us know in the comments below!
            """

            # Save transcript file
            transcript_dir = Path(self.settings.output_directory) / show_name / f"Season_{season}"
            transcript_dir.mkdir(parents=True, exist_ok=True)
            transcript_file = transcript_dir / "youtube_transcript.txt"

            with open(transcript_file, "w", encoding="utf-8") as f:
                f.write(youtube_transcript.strip())

            logger.info(f"Created YouTube transcript: {transcript_file}")
            return youtube_transcript.strip()

        except Exception as e:
            logger.error(f"Failed to create YouTube transcript: {e}")
            return summary  # Return original summary as fallback

    def _create_voice_recording(self, transcript: str, show_name: str, season: int) -> str:
        """
        Convert transcript to voice recording.

        Args:
            transcript: Text to convert to speech
            show_name: Name of the show
            season: Season number

        Returns:
            Path to the generated audio file
        """
        try:
            # Use existing media utils function with correct parameters
            duration = wave_file(show_name, str(season), f"Season_{season}", transcript)

            # Construct the expected audio file path based on the media_utils implementation
            audio_file = (
                f"{show_name}/Season{season}/Season_{season}/{show_name}_Season_{season}.wav"
            )

            logger.info(f"Generated voice recording: {audio_file} (duration: {duration}s)")
            return audio_file

        except Exception as e:
            logger.error(f"Failed to create voice recording: {e}")
            return ""

    def _create_season_video(
        self, audio_file: str, visual_concepts: list[dict], show_name: str, season: int
    ) -> str:
        """
        Create final MP4 video combining audio and images.

        Args:
            audio_file: Path to the audio file
            visual_concepts: List of visual concept data
            show_name: Name of the show
            season: Season number

        Returns:
            Path to the generated video file
        """
        try:
            # Prepare data for mp4_file_enhanced
            sentences = [concept["enhanced_prompt"] for concept in visual_concepts]
            durations = [concept["duration"] for concept in visual_concepts]

            # Use existing media utils function with correct parameters
            mp4_file_enhanced(show_name, str(season), f"Season_{season}", sentences, durations)

            # Construct the expected video file path based on the media_utils implementation
            video_file = (
                f"{show_name}/Season{season}/Season_{season}/{show_name}_Season_{season}.mp4"
            )

            logger.info(f"Generated season video: {video_file}")
            return video_file

        except Exception as e:
            logger.error(f"Failed to create season video: {e}")
            return ""

    def export_video_format(
        self,
        show_name: str,
        season: int,
        visual_concepts: list[dict],
        audio_file: str,
        export_format: str,
    ) -> dict[str, str]:
        """
        Export video in specified format after standard video generation.

        Args:
            show_name: Name of the show
            season: Season number
            visual_concepts: List of visual concept data
            audio_file: Path to the audio file
            export_format: Target export format

        Returns:
            Dict with export results. Platform exports are not implemented, so
            for any non-standard format this returns a dict with
            ``success=False`` and ``status='skipped_not_implemented'`` rather
            than raising or claiming a file was produced.
        """
        if export_format == "standard":
            return {"format": "standard", "message": "Standard MP4 format used"}

        try:
            # Prepare video content for export
            video_content = {
                "show_name": show_name,
                "season": season,
                "visual_concepts": visual_concepts,
                "audio_file": audio_file,
                "total_duration": sum(concept.get("duration", 10) for concept in visual_concepts),
            }

            # Get appropriate exporter
            exporters = {
                "youtube_shorts": YouTubeShortsExporter(),
                "tiktok": TikTokExporter(),
                "instagram_reels": InstagramReelsExporter(),
                "twitter": TwitterVideoExporter(),
            }

            exporter = exporters.get(export_format)
            if not exporter:
                return {"success": False, "error": f"Unknown export format: {export_format}"}

            # Export in specified format
            result = exporter.export_video(video_content)

            logger.info(f"Export format {export_format} completed: {result}")
            return result

        except NotImplementedError as e:
            # Platform export is a known gap, not a crash: report it honestly and
            # let the pipeline continue with the standard MP4 only.
            logger.warning(f"Export format '{export_format}' skipped - not implemented: {e}")
            return {
                "format": export_format,
                "success": False,
                "status": "skipped_not_implemented",
                "output_path": None,
                "error": str(e),
            }

        except Exception as e:
            logger.error(f"Failed to export in format {export_format}: {e}")
            return {"format": export_format, "success": False, "error": str(e)}

    def validate_stage_quality(self, show_name: str, season: int, episode: int, stage: str) -> dict:
        """Validate quality for a specific workflow stage."""
        try:
            # Get episode data from database
            episode_data = self.db.get_episode(show_name, season, episode)

            if not episode_data:
                logger.warning(f"No data found for {show_name} S{season}E{episode}")
                return None

            # Get stage-specific data
            if stage == "transcript":
                data = episode_data["transcript_data"]
                result = self.quality_agent.validate_transcript_quality(data)
            elif stage == "content":
                data = episode_data["content_data"]
                original_transcript = episode_data["transcript"]
                result = self.quality_agent.validate_content_quality(data, original_transcript)
            elif stage == "video":
                data = episode_data["video_data"]
                content_source = episode_data["content_data"]
                result = self.quality_agent.validate_video_quality(data, content_source)
            elif stage == "discovery":
                data = episode_data["discovery_data"]
                result = self.quality_agent.validate_episode_discovery(data, show_name)
            elif stage == "workflow":
                data = episode_data["workflow_data"]
                result = self.quality_agent.coordinator.validate_stage_quality("workflow", data)
            else:
                raise ValueError(f"Unknown stage: {stage}")

            return result

        except Exception as e:
            logger.error(
                f"Stage quality validation failed for {show_name} S{season}E{episode} ({stage}): {e}"
            )
            return None


async def main():
    """
    Main entry point providing comprehensive command-line interface.

    This function sets up the complete CLI for the anime video generation system
    with support for episode processing, season analysis, quality assessment,
    character analysis, and various utility commands.

    Available Commands:
        - process-url: Process episode from transcript URL
        - process-episode: Process episode by show/season/episode numbers
        - process-season: Batch process multiple episodes in a season
        - create-season-summary: Generate comprehensive season summaries with video
        - stats: Display processing statistics
        - test-transcript: Test transcript discovery functionality
        - analyze-quality: Perform quality analysis on episodes
        - discover: Discover available episodes for shows
        - analyze-characters: Character analysis and profiling
        - analyze-season: Comprehensive season analysis
        - view-season-summaries: View generated season summaries

    The CLI supports various output formats, quality control, and advanced
    character analysis features when ChromaDB dependencies are available.

    Raises:
        SystemExit: When invalid command line arguments are provided
        KeyboardInterrupt: When user cancels operation
        Exception: Various exceptions depending on the command executed

    Example:
        python main.py process-episode "My Hero Academia" 1 1 --full
        python main.py create-season-summary "My Hero Academia" 1 --duration 10
        python main.py analyze-season "My Hero Academia" 1
    """
    setup_logging()

    parser = argparse.ArgumentParser(description="Anime Video Generator")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Process single episode by URL
    url_parser = subparsers.add_parser("process-url", help="Process episode by URL")
    url_parser.add_argument("url", help="Episode transcript URL")
    url_parser.add_argument("show", help="Show name")

    # Process single episode by numbers
    episode_parser = subparsers.add_parser(
        "process-episode", help="Process episode by show/season/episode"
    )
    episode_parser.add_argument("show", help="Show name")
    episode_parser.add_argument("season", type=int, help="Season number")
    episode_parser.add_argument("episode", type=int, help="Episode number")
    episode_parser.add_argument("--title", help="Episode title (optional)")
    episode_parser.add_argument(
        "--full", action="store_true", help="Enable full AI/video processing"
    )

    # Process season batch
    batch_parser = subparsers.add_parser("process-season", help="Process multiple episodes")
    batch_parser.add_argument("show", help="Show name")
    batch_parser.add_argument("season", type=int, help="Season number")
    batch_parser.add_argument("--start", type=int, help="Starting episode number")
    batch_parser.add_argument("--end", type=int, help="Ending episode number")
    batch_parser.add_argument("--full", action="store_true", help="Enable full AI/video processing")

    # Process complete season summary with multimedia
    season_summary_parser = subparsers.add_parser(
        "create-season-summary",
        help="Create comprehensive season summary with configurable video length",
    )
    season_summary_parser.add_argument("show", help="Show name")
    season_summary_parser.add_argument("season", type=int, help="Season number")
    season_summary_parser.add_argument(
        "--force", action="store_true", help="Force reprocessing even if summary exists"
    )
    season_summary_parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=5,
        help="Video duration in minutes (5-15)",
        metavar="MINUTES",
    )
    season_summary_parser.add_argument(
        "--format",
        "-f",
        choices=["standard", "youtube_shorts", "tiktok", "instagram_reels", "twitter"],
        default="standard",
        help="Export format for the video",
    )

    # View season summaries
    view_summaries_parser = subparsers.add_parser(
        "view-season-summaries", help="View existing season summaries"
    )
    view_summaries_parser.add_argument("--show", help="Filter by show name")

    # Get statistics
    subparsers.add_parser("stats", help="Show processing statistics")

    # Test transcript discovery
    test_parser = subparsers.add_parser("test-transcript", help="Test transcript discovery")
    test_parser.add_argument("show", help="Show name")
    test_parser.add_argument("season", type=int, help="Season number")
    test_parser.add_argument("episode", type=int, help="Episode number")

    # Analyze episode quality
    quality_parser = subparsers.add_parser("analyze-quality", help="Analyze episode quality")
    quality_parser.add_argument("show", help="Show name")
    quality_parser.add_argument("season", type=int, help="Season number")
    quality_parser.add_argument("episode", type=int, help="Episode number")

    # Discover episodes
    discover_parser = subparsers.add_parser("discover", help="Discover available episodes")
    discover_parser.add_argument("show", help="Show name")
    discover_parser.add_argument("--season", type=int, help="Specific season to discover")

    # Generate content summary
    summary_parser = subparsers.add_parser("summarize", help="Generate AI content summary")
    summary_parser.add_argument("show", help="Show name")
    summary_parser.add_argument("season", type=int, help="Season number")
    summary_parser.add_argument("episode", type=int, help="Episode number")

    # Quality validation commands
    quality_parser = subparsers.add_parser(
        "validate-quality", help="Run comprehensive quality validation"
    )
    quality_parser.add_argument("show", help="Show name")
    quality_parser.add_argument("season", type=int, help="Season number")
    quality_parser.add_argument("episode", type=int, help="Episode number")
    quality_parser.add_argument(
        "--stage",
        choices=["transcript", "content", "video", "discovery", "workflow"],
        help="Validate specific stage only",
    )

    # Quality dashboard
    subparsers.add_parser("quality-dashboard", help="Show quality monitoring dashboard")

    # Quality trends
    trends_parser = subparsers.add_parser("quality-trends", help="Show quality trends analysis")
    trends_parser.add_argument("--show", help="Filter by specific show")
    trends_parser.add_argument("--days", type=int, default=30, help="Number of days to analyze")

    # Transcript source discovery commands
    sources_parser = subparsers.add_parser(
        "discover-sources", help="Discover transcript sources for a show"
    )
    sources_parser.add_argument("show", help="Show name")
    sources_parser.add_argument("--season", type=int, help="Specific season to search for")

    # Evaluate transcript source quality
    evaluate_parser = subparsers.add_parser(
        "evaluate-source", help="Evaluate a specific transcript source"
    )
    evaluate_parser.add_argument("url", help="Source URL to evaluate")
    evaluate_parser.add_argument("show", help="Show name for context")

    # Get source recommendations
    recommend_parser = subparsers.add_parser(
        "recommend-sources", help="Get recommended transcript sources"
    )
    recommend_parser.add_argument("show", help="Show name")
    recommend_parser.add_argument(
        "--season", type=int, help="Specific season to get recommendations for"
    )

    # Vector search commands (if available)
    vector_search_parser = subparsers.add_parser(
        "search-episodes", help="Semantic search across episodes"
    )
    vector_search_parser.add_argument("query", help="Search query")
    vector_search_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results to return"
    )
    vector_search_parser.add_argument("--show", help="Filter by specific show")
    vector_search_parser.add_argument("--season", type=int, help="Filter by specific season")

    # Find similar episodes
    similar_parser = subparsers.add_parser(
        "similar-episodes", help="Find episodes similar to a specific one"
    )
    similar_parser.add_argument("show", help="Show name")
    similar_parser.add_argument("season", type=int, help="Season number")
    similar_parser.add_argument("episode", type=int, help="Episode number")
    similar_parser.add_argument(
        "--limit", type=int, default=5, help="Number of similar episodes to find"
    )

    # Vector database stats
    subparsers.add_parser("vector-stats", help="Show vector database statistics")

    # Index episode for vector search
    index_parser = subparsers.add_parser("index-episode", help="Add episode to vector search index")
    index_parser.add_argument("show", help="Show name")
    index_parser.add_argument("season", type=int, help="Season number")
    index_parser.add_argument("episode", type=int, help="Episode number")

    # Character analysis commands
    char_analyze_parser = subparsers.add_parser(
        "analyze-characters", help="Analyze characters in an episode"
    )
    char_analyze_parser.add_argument("show", help="Show name")
    char_analyze_parser.add_argument("season", type=int, help="Season number")
    char_analyze_parser.add_argument("episode", type=int, help="Episode number")

    # Find similar characters
    similar_chars_parser = subparsers.add_parser(
        "similar-characters", help="Find characters similar to a given character"
    )
    similar_chars_parser.add_argument("character", help="Character name")
    similar_chars_parser.add_argument("--show", help="Filter by show name")
    similar_chars_parser.add_argument(
        "--limit", type=int, default=5, help="Number of similar characters to find"
    )

    # Character development analysis
    char_dev_parser = subparsers.add_parser(
        "character-development", help="Analyze character development across episodes"
    )
    char_dev_parser.add_argument("character", help="Character name")
    char_dev_parser.add_argument("show", help="Show name")

    # Character relationships
    char_rel_parser = subparsers.add_parser(
        "character-relationships", help="Get character relationship map"
    )
    char_rel_parser.add_argument("character", help="Character name")
    char_rel_parser.add_argument("--show", help="Filter by show name")

    # Search character moments
    char_search_parser = subparsers.add_parser(
        "search-character-moments", help="Search for specific character moments"
    )
    char_search_parser.add_argument("query", help="Search query")
    char_search_parser.add_argument("--character", help="Filter by character name")
    char_search_parser.add_argument("--show", help="Filter by show name")
    char_search_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results to return"
    )

    # Character statistics
    subparsers.add_parser("character-stats", help="Show character database statistics")

    # Season analysis
    season_analysis_parser = subparsers.add_parser(
        "analyze-season", help="Comprehensive season analysis using vector database"
    )
    season_analysis_parser.add_argument("show", help="Show name")
    season_analysis_parser.add_argument("season", type=int, help="Season number")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Validate duration parameter for create-season-summary before initialization
    if args.command == "create-season-summary" and hasattr(args, "duration"):
        if not (5 <= args.duration <= 15):
            print("❌ Error: Duration must be between 5 and 15 minutes", file=sys.stderr)
            sys.exit(1)

    # Initialize the generator
    generator = AnimeVideoGenerator()

    try:
        if args.command == "process-url":
            result = await generator.process_episode_by_url(args.url, args.show)
            print(f"Result: {result}")

        elif args.command == "process-episode":
            result = await generator.process_episode_by_numbers(
                args.show, args.season, args.episode, args.title, args.full
            )
            print(f"Result: {result}")

        elif args.command == "process-season":
            await generator.process_season_batch(
                args.show, args.season, args.start, args.end, args.full
            )

        elif args.command == "create-season-summary":
            format_msg = f" in {args.format} format" if args.format != "standard" else ""
            print(
                f"🎬 Creating {args.duration}-minute season summary for {args.show} Season {args.season}{format_msg}..."
            )
            result = await generator.process_season(
                args.show, args.season, args.force, args.duration, args.format
            )

            if result.success:
                print("✅ Season summary created successfully!")
                print(f"🎯 Target Duration: {result.data['target_duration_minutes']} minutes")
                print(f"📊 Video Structure: {result.data['video_config']}")

                print("\n📊 Analysis Summary:")
                insights = result.data.get("analysis_insights", {})
                for key, value in insights.items():
                    print(f"  {key.replace('_', ' ').title()}: {value}")

                print("\n📁 Media Files:")
                media_files = result.data.get("media_files", {})
                for key, value in media_files.items():
                    if value:
                        print(f"  {key.replace('_', ' ').title()}: {value}")

                if result.data.get("processing_stats", {}).get("transcript_errors"):
                    print("\n⚠️ Some episodes had transcript issues:")
                    for error in result.data["processing_stats"]["failed_episodes"][:3]:
                        print(f"  - {error}")
            else:
                print(f"❌ Season summary creation failed: {result.error}")

        elif args.command == "stats":
            stats = generator.get_stats()
            print("Processing Statistics:")
            print(f"Total episodes: {stats['total_episodes']}")
            print(f"Status counts: {stats['status_counts']}")
            print(f"Recent activity: {stats['recent_activity']}")

        elif args.command == "test-transcript":
            # Use enhanced discovery agent instead of old transcript agent
            result = generator.discovery_agent.search_episode_enhanced(
                args.show, args.season, args.episode
            )
            if result:
                print("Found transcript via enhanced discovery:")
                print(f"Source: {result['source']}")
                print(f"URL: {result['url']}")
                print(f"Quality: {result['quality_score']:.2f}")
                print("Discovery method: Enhanced search with query parameters")

                # Also show transcript parsing result
                transcript_result = generator.transcript_agent.parse_discovered_url(
                    result["url"], result["source"]
                )
                if transcript_result:
                    print(f"Transcript length: {transcript_result['content_length']} chars")
                    print(f"Parse quality: {transcript_result['quality_score']:.2f}")
            else:
                print("No transcript found via enhanced discovery")

        elif args.command == "analyze-quality":
            quality_report = generator.analyze_episode_quality(args.show, args.season, args.episode)
            if quality_report:
                print("Quality Analysis Report:")
                for key, value in quality_report.items():
                    print(f"{key}: {value}")
            else:
                print("Quality analysis failed")

        elif args.command == "discover":
            episodes = generator.discover_show_episodes(args.show, args.season)
            if episodes:
                print(f"Discovered Episodes for {args.show}:")
                for episode in episodes:
                    print(
                        f"  S{episode.get('season', '?')}E{episode.get('episode', '?')}: {episode.get('title', 'Unknown')}"
                    )
            else:
                print("No episodes discovered")

        elif args.command == "summarize":
            summary = generator.generate_content_summary(args.show, args.season, args.episode)
            if summary:
                print(f"Content Summary for {args.show} S{args.season}E{args.episode}:")
                print(summary)
            else:
                print("Content summary generation failed")

        elif args.command == "validate-quality":
            if args.stage:
                result = generator.validate_stage_quality(
                    args.show, args.season, args.episode, args.stage
                )
                if result:
                    print(
                        f"Quality Validation for {args.show} S{args.season}E{args.episode} ({args.stage}):"
                    )
                    print(f"Overall Score: {result['overall_score']:.2f}")
                    print(f"Acceptable: {result['is_acceptable']}")
                    if result["issues"]:
                        print("Issues:")
                        for issue in result["issues"]:
                            print(f"  - {issue}")
                    if result["recommendations"]:
                        print("Recommendations:")
                        for rec in result["recommendations"]:
                            print(f"  - {rec}")
                else:
                    print("Quality validation failed")
            else:
                result = generator.analyze_episode_quality(args.show, args.season, args.episode)
                if result:
                    print(
                        f"Comprehensive Quality Analysis for {args.show} S{args.season}E{args.episode}:"
                    )
                    print(f"Overall Score: {result['overall_score']:.2f}")
                    print(f"Meets Standards: {result['meets_standards']}")
                    print(f"Passed Gates: {', '.join(result['passed_quality_gates'])}")
                    if result["failed_quality_gates"]:
                        print(f"Failed Gates: {', '.join(result['failed_quality_gates'])}")
                    if result["critical_issues"]:
                        print("Critical Issues:")
                        for issue in result["critical_issues"]:
                            print(f"  - {issue}")
                    print("Recommendations:")
                    for rec in result["recommendations"]:
                        print(f"  - {rec}")
                else:
                    print("Quality analysis failed")

        elif args.command == "quality-dashboard":
            dashboard = generator.quality_agent.get_quality_dashboard()
            if dashboard.get("status") == "no_data":
                print("No quality data available yet")
            else:
                print("Quality Dashboard:")
                print(f"Total Evaluations: {dashboard['total_evaluations']}")
                print(f"Recent Evaluations: {dashboard['recent_evaluations']}")
                print(f"Recent Trend: {dashboard['recent_trend']}")
                print("\nStage Averages:")
                for stage, avg in dashboard["stage_averages"].items():
                    print(f"  {stage}: {avg:.2f}")
                print("\nQuality Gate Pass Rates:")
                for stage, rate in dashboard["gate_pass_rates"].items():
                    print(f"  {stage}: {rate:.1%}")

        elif args.command == "quality-trends":
            # This would need implementation in the quality coordinator
            print("Quality trends analysis not yet implemented")

        elif args.command == "discover-sources":
            sources = generator.transcript_source_agent.discover_sources_for_show(
                args.show, args.season
            )
            if sources:
                print(f"Discovered {len(sources)} transcript sources for {args.show}:")
                for i, source in enumerate(sources, 1):
                    print(f"\n{i}. {source.url}")
                    print(f"   Type: {source.source_type}")
                    print(f"   Reliability: {source.reliability_score:.2f}")
                    print(f"   Quality: {source.content_quality}")
                    print(f"   Coverage: {source.episode_coverage}")
                    print(f"   Access: {source.accessibility}")
            else:
                print(f"No transcript sources found for {args.show}")

        elif args.command == "evaluate-source":
            from agents.transcript_source_agent import TranscriptSource

            # Create a temporary source object for evaluation
            temp_source = TranscriptSource(
                url=args.url,
                source_type="unknown",
                reliability_score=0.5,
                content_quality="unknown",
                last_updated=None,
                accessibility="unknown",
                format_type="unknown",
                language="english",
                episode_coverage="unknown",
                metadata={},
            )

            evaluation = generator.transcript_source_agent.evaluate_source_quality(temp_source)
            if evaluation.get("accessible", False):
                print(f"Source Evaluation for: {args.url}")
                print(f"Overall Score: {evaluation['overall_score']:.2f}")
                print(f"Accessibility: {evaluation['accessibility']}")
                print(f"Update Frequency: {evaluation['update_frequency']}")

                content_analysis = evaluation.get("content_analysis", {})
                print("\nContent Analysis:")
                print(f"  Word Count: {content_analysis.get('word_count', 0)}")
                print(
                    f"  Character Dialogue: {content_analysis.get('character_dialogue_count', 0)}"
                )
                print(f"  Scene Descriptions: {content_analysis.get('scene_description_count', 0)}")
                print(
                    f"  Structure Quality: {content_analysis.get('structure_quality', 'unknown')}"
                )
                print(f"  Has Timestamps: {content_analysis.get('has_timestamps', False)}")

                community_validation = evaluation.get("community_validation", {})
                print("\nCommunity Validation:")
                print(f"  Has Community: {community_validation.get('has_community', False)}")
                print(f"  Type: {community_validation.get('type', 'unknown')}")
                print(
                    f"  Validation Level: {community_validation.get('validation_level', 'unknown')}"
                )

                technical_quality = evaluation.get("technical_quality", {})
                print("\nTechnical Quality:")
                print(f"  Load Time: {technical_quality.get('load_time', 0):.2f}s")
                print(f"  Content Length: {technical_quality.get('content_length', 0)} bytes")
                print(f"  Has SSL: {technical_quality.get('has_ssl', False)}")
                print(f"  Mobile Friendly: {technical_quality.get('mobile_friendly', False)}")
            else:
                error = evaluation.get("error", "Unknown error")
                print(f"Failed to evaluate source: {error}")

        elif args.command == "recommend-sources":
            sources = generator.transcript_source_agent.discover_sources_for_show(
                args.show, args.season
            )
            recommendations = generator.transcript_source_agent.get_source_recommendations(sources)

            print(f"Source Recommendations for {args.show}:")
            print(f"Summary: {recommendations['summary']}")

            if recommendations["recommended"]:
                print(f"\nRecommended Sources ({len(recommendations['recommended'])}):")
                for i, source in enumerate(recommendations["recommended"], 1):
                    print(f"{i}. {source.url} (Score: {source.reliability_score:.2f})")
                    print(f"   Type: {source.source_type}, Quality: {source.content_quality}")

            if recommendations["backup"]:
                print(f"\nBackup Sources ({len(recommendations['backup'])}):")
                for i, source in enumerate(recommendations["backup"], 1):
                    print(f"{i}. {source.url} (Score: {source.reliability_score:.2f})")

            if recommendations["avoid"]:
                print(f"\nSources to Avoid ({len(recommendations['avoid'])}):")
                for i, source in enumerate(recommendations["avoid"], 1):
                    print(f"{i}. {source.url} (Score: {source.reliability_score:.2f})")

            if recommendations.get("best_source"):
                best = recommendations["best_source"]
                print(f"\nBest Source: {best.url}")
                print(f"Score: {best.reliability_score:.2f}")
                print(f"Type: {best.source_type}")
                print(f"Quality: {best.content_quality}")
            else:
                print("\nNo sources found to recommend.")

        elif args.command == "analyze-characters":
            result = generator.analyze_episode_characters(args.show, args.season, args.episode)

            if "error" in result:
                print(f"Character analysis failed: {result['error']}")
            else:
                print(f"Character Analysis for {result['episode']}:")
                print(f"Total Characters: {result['total_characters']}")

                for char_name, profile in result["characters"].items():
                    print(f"\n📖 {char_name}:")
                    print(f"   Dialogue Count: {profile['dialogue_count']}")
                    print(
                        f"   Personality Traits: {', '.join(profile['personality_traits']) or 'None detected'}"
                    )
                    if profile["relationships"]:
                        print(f"   Relationships: {', '.join(profile['relationships'].keys())}")
                    print(
                        f"   First Appearance: S{profile['first_appearance']['season']}E{profile['first_appearance']['episode']}"
                    )

        elif args.command == "similar-characters":
            similar_chars = generator.find_similar_characters(args.character, args.show, args.limit)

            if similar_chars:
                print(f"Characters Similar to {args.character}:")
                for i, char in enumerate(similar_chars, 1):
                    print(f"\n{i}. {char['character_name']} ({char['show_name']})")
                    print(f"   Similarity Score: {char['similarity_score']:.3f}")
                    print(f"   Personality Traits: {', '.join(char['personality_traits'])}")
                    print(f"   Dialogue Count: {char['dialogue_count']}")
            else:
                print(f"No similar characters found for {args.character}")

        elif args.command == "character-development":
            development = generator.analyze_character_development(args.character, args.show)

            if "error" in development:
                print(f"Character development analysis failed: {development['error']}")
            else:
                print(f"Character Development Analysis for {development['character_name']}:")
                print(f"Show: {development['show_name']}")
                print(f"Total Episodes: {development['total_episodes']}")
                print(f"Development Score: {development['development_score']:.2f}")

                if development["first_appearance"]:
                    first = development["first_appearance"]
                    print(f"First Appearance: S{first['season']}E{first['episode']}")

                if development["latest_appearance"]:
                    latest = development["latest_appearance"]
                    print(f"Latest Appearance: S{latest['season']}E{latest['episode']}")

                print(f"Dialogue Trend: {development['dialogue_trend']}")

                if development["personality_evolution"]:
                    print("\nPersonality Evolution:")
                    for trait, evolution in development["personality_evolution"].items():
                        print(
                            f"  {trait}: {evolution['trend']} (early: {evolution['first_third']:.2f}, recent: {evolution['last_third']:.2f})"
                        )

        elif args.command == "character-relationships":
            relationships = generator.get_character_relationships(args.character, args.show)

            if "error" in relationships:
                print(f"Character relationship analysis failed: {relationships['error']}")
            else:
                print(f"Character Relationships for {relationships['character_name']}:")
                print(f"Total Relationships: {relationships['total_relationships']}")

                for other_char, rel_data in relationships["relationships"].items():
                    print(f"\n🤝 {other_char}:")
                    print(f"   Interaction Count: {rel_data['interaction_count']}")
                    print(f"   Relationship Strength: {rel_data['relationship_strength']:.2f}")
                    print(f"   Primary Interaction: {rel_data['primary_interaction_type']}")
                    print(f"   Emotional Tone: {rel_data['primary_emotional_tone']}")
                    print(f"   Episodes: {', '.join(rel_data['episodes'][:5])}")  # Show first 5

        elif args.command == "search-character-moments":
            moments = generator.search_character_moments(
                args.query, args.character, args.show, args.limit
            )

            if moments:
                print(f"Character Moments for Query: '{args.query}'")
                for i, moment in enumerate(moments, 1):
                    print(
                        f"\n{i}. {moment['character_name']} - {moment['show_name']} S{moment['season']}E{moment['episode']}"
                    )
                    print(f"   Relevance Score: {moment['relevance_score']:.3f}")
                    print(f"   Personality Traits: {', '.join(moment['personality_traits'])}")
                    print(f"   Preview: {moment['content_preview']}")
            else:
                print(f"No character moments found for query: '{args.query}'")

        elif args.command == "character-stats":
            stats = generator.get_character_statistics()

            if "error" in stats:
                print(f"Failed to get character statistics: {stats['error']}")
            else:
                print("Character Database Statistics:")
                print(f"Total Character Profiles: {stats['total_character_profiles']}")
                print(f"Total Interactions: {stats['total_interactions']}")
                print(f"Unique Characters: {stats['unique_characters']}")
                print(f"Unique Shows: {stats['unique_shows']}")

                if stats["shows_analyzed"]:
                    print(f"\nShows Analyzed: {', '.join(stats['shows_analyzed'])}")

                if stats["sample_characters"]:
                    print(f"\nSample Characters: {', '.join(stats['sample_characters'])}")

        elif args.command == "analyze-season":
            print(f"🎬 Analyzing {args.show} Season {args.season}...")
            analysis = generator.analyze_season_development(args.show, args.season)

            if "error" in analysis:
                print(f"❌ Season analysis failed: {analysis['error']}")
            else:
                print("✅ Season Analysis Completed!\n")

                # Season Overview
                season_info = analysis["season_info"]
                print("📊 Season Overview:")
                print(f"  Show: {season_info['show_name']}")
                print(f"  Season: {season_info['season']}")
                print(
                    f"  Episodes: {season_info['total_episodes']} ({season_info['episode_range']})"
                )

                # Character Insights
                char_insights = analysis["character_insights"]
                print("\n👥 Character Development:")
                print(f"  Total Characters: {char_insights['total_characters']}")

                print("\n🌟 Top Developing Characters:")
                for i, (char_name, score) in enumerate(
                    char_insights["top_developing_characters"], 1
                ):
                    print(f"  {i}. {char_name}: {score:.2f}")

                print("\n🎭 Screen Time Leaders:")
                for char_name, percentage in char_insights["character_focus_distribution"]:
                    print(f"  {char_name}: {percentage:.1f}%")

                # Story Insights
                story_insights = analysis["story_insights"]
                print("\n📖 Story Analysis:")
                print(f"  Pivotal Moments: {story_insights['pivotal_moments_count']}")
                print(f"  Narrative Arcs: {story_insights['narrative_arcs']}")
                print(f"  Thematic Diversity: {story_insights['thematic_diversity']:.2f}")

                print("\n🎨 Dominant Themes:")
                for theme, count in story_insights["dominant_themes"]:
                    print(f"  {theme}: {count} instances")

                # Relationship Insights
                rel_insights = analysis["relationship_insights"]
                print("\n🤝 Relationship Analysis:")
                print(f"  Total Relationships: {rel_insights['total_relationships']}")

                if rel_insights["strongest_relationships"]:
                    print("\n💫 Strongest Relationships:")
                    for rel_key, strength in rel_insights["strongest_relationships"]:
                        chars = rel_key.replace("_", " ↔ ")
                        rel_type = rel_insights["relationship_types"].get(rel_key, "unknown")
                        print(f"  {chars}: {strength:.2f} ({rel_type})")

                # Episode Analysis
                ep_insights = analysis["episode_analysis"]
                print("\n🎯 Most Significant Episodes:")
                for ep_key, score in ep_insights["most_significant_episodes"]:
                    ep_type = ep_insights["episode_types_distribution"].get(ep_key, "unknown")
                    print(f"  {ep_key}: {score:.2f} ({ep_type})")

                print("\n💡 For detailed analysis, check the raw data in the returned object.")

        elif args.command == "view-season-summaries":
            summaries = generator.db.get_all_season_summaries(args.show)

            if summaries:
                print(f"📚 Season Summaries{' for ' + args.show if args.show else ''}:")
                print("=" * 50)

                for summary in summaries:
                    print(f"\n🎬 {summary['show']} Season {summary['season']}")
                    print(f"   Created: {summary['created_at']}")
                    print(f"   Updated: {summary['updated_at']}")

                    # Show preview of summary
                    summary_preview = (
                        summary["summary"][:200] + "..."
                        if len(summary["summary"]) > 200
                        else summary["summary"]
                    )
                    print(f"   Preview: {summary_preview}")

                    # Show analysis insights if available
                    if summary["analysis_data"]:
                        analysis = summary["analysis_data"]
                        season_info = analysis.get("season_info", {})
                        char_insights = analysis.get("character_insights", {})
                        story_insights = analysis.get("story_insights", {})

                        print(f"   Episodes: {season_info.get('total_episodes', 'N/A')}")
                        print(f"   Characters: {char_insights.get('total_characters', 'N/A')}")
                        print(
                            f"   Pivotal Moments: {story_insights.get('pivotal_moments_count', 'N/A')}"
                        )

                    # Show media files if available
                    if summary["media_files"]:
                        media = summary["media_files"]
                        print("   Media Files:")
                        for key, value in media.items():
                            if value:
                                print(f"     {key.replace('_', ' ').title()}: {value}")

                    print("-" * 30)

            else:
                filter_text = f" for {args.show}" if args.show else ""
                print(f"No season summaries found{filter_text}")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
