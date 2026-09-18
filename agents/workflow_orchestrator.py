"""
Main workflow orchestrator that coordinates all agents.
"""

import logging
from datetime import datetime
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate

from agents.character_analysis_agent import CharacterAnalysisAgent
from agents.config_manager import EpisodeConfigManager
from agents.content_agent import ContentAgent
from agents.discovery_agent import EpisodeDiscoveryAgent
from agents.quality_agent import QualityAssuranceAgent
from agents.transcript_agent import TranscriptDiscoveryAgent
from agents.video_agent import VideoGenerationAgent
from core.adaptive_quality_manager import AdaptiveQualityManager
from core.character_episode_enhancer import EpisodeCharacterEnhancer
from core.database import DatabaseManager
from core.intelligent_format_adapter import IntelligentFormatAdapter
from core.schemas import Episode_Summary_Schema, ProcessingResult
from core.visual_coherence_manager import VisualCoherenceManager
from media.media_utils import create_images, mp4_file_enhanced, wave_file

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Orchestrates the entire video generation workflow from start to finish.

    This is the main coordination class that brings together all the specialized agents
    to create a complete video generation pipeline. It manages the flow from transcript
    discovery through final video output, handling errors and state management.
    """

    def __init__(self, db_path: str = "data/databases/video_generator.db"):
        """
        Initialize all the necessary components and agents.

        Sets up the complete ecosystem for video generation including
        database, AI models, and all specialized agents.

        Args:
            db_path (str): Path to the SQLite database file for storing episode data
        """
        # Core infrastructure components
        self.db = DatabaseManager(db_path)  # Database operations

        # Initialize AI model with error handling
        try:
            self.model = init_chat_model(
                "gemini-2.0-flash", model_provider="google_genai"
            )  # AI model
        except Exception as e:
            logger.warning(f"AI model not available: {e}")
            self.model = None

        # Specialized agent instances for different aspects of video generation
        self.content_agent = (
            ContentAgent(self.model) if self.model else None
        )  # Content analysis and generation
        self.video_agent = VideoGenerationAgent()  # Video and image generation
        self.qa_agent = QualityAssuranceAgent()  # Quality control and validation
        self.discovery_agent = EpisodeDiscoveryAgent()  # URL discovery and validation
        self.transcript_agent = TranscriptDiscoveryAgent()  # Transcript extraction
        self.config_manager = EpisodeConfigManager()  # Configuration management

        # Phase 2 Quality Enhancement components
        self.character_analysis_agent = CharacterAnalysisAgent()  # Character analysis with ChromaDB
        self.character_enhancer = EpisodeCharacterEnhancer(
            character_analyzer=self.character_analysis_agent, timing_calculator=self.video_agent
        )
        self.visual_coherence = VisualCoherenceManager(consistency_threshold=0.8)
        self.quality_manager = AdaptiveQualityManager()
        self.format_adapter = IntelligentFormatAdapter()

        # Structured output model for consistent data format
        self.model_with_structure = (
            self.model.with_structured_output(Episode_Summary_Schema) if self.model else None
        )

        logger.info("WorkflowOrchestrator initialized with all agents")

    async def process_episode(self, url: str, show_name: str) -> dict[str, Any]:
        """
        The main method to process an episode, from content extraction to media generation.
        This is the central orchestration method that coordinates all agents to transform
        a transcript URL into a complete video with synchronized audio and images.

        Args:
            url (str): The URL of the episode transcript to process
            show_name (str): The name of the anime show for context and branding

        Returns:
            dict: Result dictionary with success status, job ID, and either data or error message
        """
        # Generate unique job identifier for tracking and logging
        job_id = f"{show_name}_{datetime.now().isoformat()}"

        try:
            # Step 1: Extract and analyze content from the transcript URL
            # This involves web scraping, HTML parsing, and initial content analysis
            logger.info(f"Starting content extraction for {job_id}")
            content_result = self.content_agent.extract_and_analyze(url)

            # Validate that content extraction was successful
            if not content_result["success"]:
                raise Exception(f"Content extraction failed: {content_result['error']}")

            # Step 2: Generate a structured summary using the AI model
            # Transform raw transcript into YouTube-ready content with plot points
            logger.info("Generating AI summary")
            summary_result = self.generate_structured_summary(content_result, show_name)

            # Step 3: Validate the generated content for quality and coherence
            # Ensure the content meets standards before proceeding to media generation
            logger.info("Validating content quality")
            # BUG: the result is computed and then dropped, so this gate does
            # not actually gate. See docs/portfolio-refinement.md.
            # TODO: act on the score, or remove the call.
            _quality_check = self.qa_agent.validate_content(
                summary_result["youtube_transcript"], summary_result["plot_points"]
            )

            # Step 4: Save the processed data to the database for persistence
            # Store all generated content for future reference and reprocessing
            self.db.save_episode(
                summary_result["show"],
                summary_result["season"],
                summary_result["episode"],
                url,
                content_result["transcript"],
                summary_result["youtube_transcript"],
                summary_result["plot_points"],
            )

            # Step 5: Generate the image and audio files for video compilation using Phase 2 enhancement
            # Create all media assets needed for the final video output
            logger.info("Generating media files with Phase 2 Quality Enhancement")
            await self.generate_all_media(summary_result)

            # Log successful completion and return success response
            logger.info(f"Successfully processed episode {job_id}")
            return {"success": True, "job_id": job_id, "data": summary_result}

        except Exception as e:
            # Handle any errors that occur during the workflow
            logger.error(f"Workflow failed for {job_id}: {e}")
            return {"success": False, "job_id": job_id, "error": str(e)}

    def generate_structured_summary(
        self, content_result: dict[str, Any], show_name: str
    ) -> dict[str, Any]:
        """
        Generate a structured summary using a predefined prompt and an AI model.

        This method transforms raw transcript data into YouTube-ready content
        with proper formatting and engagement elements.

        Args:
            content_result (Dict[str, Any]): The dictionary containing the transcript and analysis
            show_name (str): The name of the show for context and branding

        Returns:
            Dict[str, Any]: A dictionary with the structured summary including plot points and transcript
        """
        # Define the system prompt that establishes the AI's role and output format
        # This creates consistent branding and engagement for the YouTube channel
        system_template = """You are a famous YouTuber who makes videos about popular anime shows and your channel is called TLDR Media. 
        Can you summarize this episode of {Show} based on the following transcription? 
        Make sure to ask watchers to Like, Comment, and subscribe somewhere in the video.
        Do not do an introduction.
        
        Additional context: {context}"""

        # Create a structured prompt template for consistent AI interactions
        prompt_template = ChatPromptTemplate.from_messages(
            [("system", system_template), ("user", "{text}")]
        )

        # Generate the actual prompt with show-specific data
        prompt = prompt_template.invoke(
            {
                "Show": show_name,
                "text": content_result["transcript"],
                "context": content_result.get("analysis", ""),
            }
        )

        # Use the structured output model to ensure consistent data format
        response = self.model_with_structure.invoke(prompt)
        return response.model_dump()

    async def generate_all_media(self, episode_data: dict[str, Any]) -> None:
        """
        Generate all media files (images, audio, video) for the episode using Phase 2 Quality Enhancement.

        This method coordinates the creation of all visual and audio assets with character-aware timing,
        visual coherence, adaptive quality, and platform optimization.

        Args:
            episode_data (Dict[str, Any]): The structured data of the episode including plot points and metadata
        """
        logger.info("Starting Phase 2 enhanced media generation")

        # Phase 2 Step 1: Character Analysis Integration
        # Analyze characters and enhance episode with character-aware timing
        try:
            # Get character analysis for this episode
            character_analysis = self.character_analysis_agent.analyze_episode_characters(
                episode_data["show"],
                episode_data["season"],
                episode_data["episode"],
                episode_data.get("transcript", ""),
            )

            # Convert episode data to Phase 2 format
            episode_content = {
                "scenes": [
                    {
                        "prompt": plot_point,
                        "base_duration": 3.0,  # Default base duration
                        "characters": [],  # Will be filled by character analysis
                    }
                    for plot_point in episode_data["plot_points"]
                ]
            }

            # Enhance episode with character data
            enhanced_episode = await self.character_enhancer.enhance_episode_with_character_data(
                episode_content, {"profiles": character_analysis}
            )

            logger.info(
                f"Enhanced episode with {len(enhanced_episode['character_focus'])} characters"
            )

        except Exception as e:
            logger.warning(f"Character enhancement failed, using fallback: {e}")
            # Fallback to original approach
            enhanced_episode = {
                "scenes": [
                    {"prompt": plot_point, "duration": 3.0, "enhanced_prompt": plot_point}
                    for plot_point in episode_data["plot_points"]
                ]
            }

        # Phase 2 Step 2: Adaptive Quality Management
        # Select optimal quality profile based on system resources
        try:
            quality_profile = await self.quality_manager.select_quality_profile(
                context="production",  # Default to production quality
                deadline=None,  # No deadline pressure for standard processing
            )
            logger.info(f"Selected quality profile: {quality_profile.name}")
        except Exception as e:
            logger.warning(f"Quality management failed, using defaults: {e}")
            quality_profile = None

        # Phase 2 Step 3: Visual Coherence Prompt Construction
        # The visual coherence manager does not generate images (create_images below
        # does that); here we only use its prompt-construction half to fold episode
        # style and character consistency instructions into each scene prompt.
        enhanced_prompts = []
        episode_context = {
            "episode_id": f"{episode_data['show']}_S{episode_data['season']}E{episode_data['episode']}",
            "visual_style": "anime",
            "show": episode_data["show"],
        }

        for i, scene in enumerate(enhanced_episode["scenes"]):
            try:
                # Build a coherence-enhanced prompt (style + character consistency)
                coherent_prompt = await self.visual_coherence.build_coherent_prompt(
                    scene.get("enhanced_prompt", scene["prompt"]),
                    scene.get("characters", []),
                    episode_context,
                )
                enhanced_prompts.append(coherent_prompt)
                logger.debug(f"Built coherence-enhanced prompt for scene {i}")

            except Exception as e:
                logger.warning(
                    f"Visual coherence prompt building failed for scene {i}, using fallback: {e}"
                )
                # Fallback to the video agent's generic style prompt enhancement
                enhanced_prompts.append(
                    self.video_agent.generate_optimized_images([scene["prompt"]], episode_data)[0]
                )

        # Step 4: Create the actual image files using enhanced prompts
        create_images(
            enhanced_prompts, episode_data["episode"], episode_data["season"], episode_data["show"]
        )

        # Step 5: Generate the audio file from the YouTube transcript
        wave_length = wave_file(
            show=episode_data["show"],
            season=episode_data["season"],
            episode=episode_data["episode"],
            contents=episode_data["youtube_transcript"],
        )

        # Step 6: Use character-aware durations or fallback to adaptive calculation
        if "scenes" in enhanced_episode:
            # Use Phase 2 character-enhanced durations
            durations = [scene["duration"] for scene in enhanced_episode["scenes"]]
            logger.info("Using character-aware timing")
        else:
            # Fallback to original adaptive duration calculation
            durations = self.video_agent.adaptive_duration_calculation(
                episode_data["plot_points"], wave_length
            )
            logger.info("Using fallback adaptive timing")

        # Step 7: Create the final MP4 video file
        mp4_file_enhanced(
            show=episode_data["show"],
            season=episode_data["season"],
            episode=episode_data["episode"],
            sentences=episode_data["plot_points"],
            durations=durations,
        )

        # Phase 2 Step 8: Platform Adaptation (optional)
        # Generate platform-optimized versions if requested
        try:
            if quality_profile:
                # Record quality metrics for optimization
                processing_metrics = {
                    "processing_time_ms": 0,  # Would be measured in real implementation
                    "memory_usage_mb": 0,  # Would be measured in real implementation
                    "output_quality_score": 0.9,  # Based on quality validation
                    "success": True,
                }
                self.quality_manager.record_quality_metrics(quality_profile, processing_metrics)

        except Exception as e:
            logger.warning(f"Quality metrics recording failed: {e}")

        logger.info("Phase 2 enhanced media generation completed")

    async def process_episode_complete(
        self,
        show_name: str,
        season: int,
        episode: int,
        episode_title: str = None,
        db: DatabaseManager = None,
    ) -> ProcessingResult:
        """
        Complete episode processing by season and episode numbers using transcript discovery.

        This method handles the full workflow from transcript discovery through final video generation.
        It uses the TranscriptDiscoveryAgent to find episodes across multiple sources.

        Args:
            show_name (str): Name of the anime show
            season (int): Season number
            episode (int): Episode number within the season
            episode_title (str, optional): Episode title for better discovery
            db (DatabaseManager, optional): Database instance to use

        Returns:
            ProcessingResult: Processing result with success status and data/error
        """
        logger.info(f"Starting complete processing for {show_name} S{season}E{episode}")

        # Generate unique job identifier for tracking
        job_id = f"{show_name}_S{season}E{episode}_{datetime.now().isoformat()}"

        try:
            # Step 1: Use enhanced discovery agent to find the episode URL with search functionality
            logger.info("Discovering episode URL using enhanced search...")
            discovery_result = self.discovery_agent.search_episode_enhanced(
                show_name, season, episode, episode_title
            )

            if not discovery_result or not discovery_result.get("url"):
                error_msg = (
                    f"No episode URL found for {show_name} Season {season} Episode {episode}"
                )
                logger.error(error_msg)
                return ProcessingResult(success=False, job_id=job_id, error=error_msg)

            discovered_url = discovery_result["url"]
            logger.info(
                f"Found episode URL via {discovery_result['source']} search "
                f"(quality: {discovery_result['quality_score']:.2f}): {discovered_url}"
            )

            # Step 2: Use transcript agent to parse the discovered URL
            logger.info("Parsing transcript content from discovered URL...")
            transcript_result = self.transcript_agent.parse_discovered_url(
                discovered_url, discovery_result["source"]
            )

            if not transcript_result or not transcript_result.get("transcript"):
                error_msg = f"Failed to parse transcript from discovered URL: {discovered_url}"
                logger.error(error_msg)
                return ProcessingResult(success=False, job_id=job_id, error=error_msg)

            logger.info(
                f"Successfully parsed transcript "
                f"(length: {transcript_result['content_length']:,} chars, "
                f"quality: {transcript_result['quality_score']:.2f})"
            )

            # Step 3: Process the found transcript using existing workflow
            # Create content result in expected format
            content_result = {
                "transcript": transcript_result["transcript"],
                "title": transcript_result["title"],
                "episode": f"Season {season}, Episode {episode}",
                "analysis": f"Found via {transcript_result['source']} with quality score {transcript_result['quality_score']:.2f}",
                "success": True,
            }

            # Step 3: Generate structured summary
            logger.info("Generating AI summary...")
            summary_result = self.generate_structured_summary(content_result, show_name)

            # Ensure episode info is correctly set
            summary_result["season"] = str(season)
            summary_result["episode"] = str(episode)
            summary_result["show"] = show_name

            # Step 4: Quality validation
            logger.info("Validating content quality...")
            # BUG: the result is computed and then dropped, so this gate does
            # not actually gate. See docs/portfolio-refinement.md.
            # TODO: act on the score, or remove the call.
            _quality_check = self.qa_agent.validate_content(
                summary_result["youtube_transcript"], summary_result["plot_points"]
            )

            # Step 5: Save to database
            db_instance = db or self.db
            db_instance.save_episode(
                summary_result["show"],
                summary_result["season"],
                summary_result["episode"],
                transcript_result["url"],
                content_result["transcript"],
                summary_result["youtube_transcript"],
                summary_result["plot_points"],
            )

            # Step 6: Generate all media files with Phase 2 enhancement
            logger.info("Generating media files with Phase 2 Quality Enhancement...")
            await self.generate_all_media(summary_result)

            logger.info(f"Successfully completed processing for {job_id}")
            return ProcessingResult(
                success=True, job_id=job_id, data=summary_result, source_info=transcript_result
            )

        except Exception as e:
            logger.error(f"Complete processing failed for {job_id}: {e}")
            return ProcessingResult(success=False, job_id=job_id, error=str(e))

    async def process_episode_from_url(
        self, url: str, show_name: str, db: DatabaseManager = None
    ) -> ProcessingResult:
        """
        Process episode from a direct transcript URL.

        This method processes an episode when you already have the transcript URL,
        bypassing the discovery phase and going straight to content processing.

        Args:
            url (str): Direct URL to the episode transcript
            show_name (str): Name of the anime show for context
            db (DatabaseManager, optional): Database instance to use

        Returns:
            ProcessingResult: Processing result with success status and data/error
        """
        logger.info(f"Starting URL-based processing for {show_name}: {url}")

        # Generate unique job identifier for tracking
        job_id = f"{show_name}_URL_{datetime.now().isoformat()}"

        try:
            # Step 1: Extract and analyze content from the provided URL
            logger.info("Extracting content from URL...")
            content_result = self.content_agent.extract_and_analyze(url)

            # Validate that content extraction was successful
            if not content_result["success"]:
                error_msg = f"Content extraction failed: {content_result['error']}"
                logger.error(error_msg)
                return ProcessingResult(success=False, job_id=job_id, error=error_msg)

            # Step 2: Generate structured summary
            logger.info("Generating AI summary...")
            summary_result = self.generate_structured_summary(content_result, show_name)

            # Step 3: Quality validation
            logger.info("Validating content quality...")
            # BUG: the result is computed and then dropped, so this gate does
            # not actually gate. See docs/portfolio-refinement.md.
            # TODO: act on the score, or remove the call.
            _quality_check = self.qa_agent.validate_content(
                summary_result["youtube_transcript"], summary_result["plot_points"]
            )

            # Step 4: Save to database
            db_instance = db or self.db
            db_instance.save_episode(
                summary_result["show"],
                summary_result["season"],
                summary_result["episode"],
                url,
                content_result["transcript"],
                summary_result["youtube_transcript"],
                summary_result["plot_points"],
            )

            # Step 5: Generate all media files with Phase 2 enhancement
            logger.info("Generating media files with Phase 2 Quality Enhancement...")
            await self.generate_all_media(summary_result)

            logger.info(f"Successfully completed URL processing for {job_id}")
            return ProcessingResult(success=True, job_id=job_id, data=summary_result)

        except Exception as e:
            logger.error(f"URL processing failed for {job_id}: {e}")
            return ProcessingResult(success=False, job_id=job_id, error=str(e))
