#!/usr/bin/env python3
"""
DEPRECATED: Legacy monolithic implementation of the Anime Video Generator.

⚠️  WARNING: This file is deprecated and should not be used for new development.

✅ Use instead: python main_refactored.py --help
📖 Documentation: docs/README_MODULAR.md
🏗️  Architecture: Modular agent-based system in agents/ directory

This file remains for:
- Historical reference
- Legacy compatibility (temporary)
- Migration assistance

Last updated: July 2025
Migration target: main_refactored.py with modular agents
"""

import warnings
import sys

# Issue deprecation warning
warnings.warn(
    "\n" + "="*60 + "\n"
    "⚠️  DEPRECATION WARNING: main.py is deprecated!\n"
    "\n"
    "This monolithic implementation has been replaced by a modern\n"
    "modular architecture for better maintainability and scalability.\n"
    "\n"
    "✅ NEW: python main_refactored.py --help\n"
    "❌ OLD: python main.py (this file)\n"
    "\n"
    "📖 See docs/README_MODULAR.md for migration guide\n"
    "🏗️  New architecture: agents/, core/, utils/ directories\n"
    "="*60,
    DeprecationWarning,
    stacklevel=2
)

# Print console warning for immediate visibility
print("🚨 DEPRECATED: main.py is no longer maintained")
print("✅ Use: python main_refactored.py instead")
print("📖 See: README.md for current usage instructions")
print("-" * 50)

# Web scraping and HTTP requests
import requests
from bs4 import BeautifulSoup

# Google Gemini AI integration for content generation and analysis
from google import genai
from google.genai import types

# Image and media processing
from io import BytesIO
from PIL import Image

# Text processing and pattern matching
import re

# System and utility imports
import getpass  # For secure input handling
import os       # Operating system interface
import json     # JSON data handling
import wave     # Audio file processing

# Video and audio processing with MoviePy
from moviepy import VideoFileClip, ImageClip, concatenate_videoclips, AudioFileClip

# Database operations
import sqlite3

# Date and time handling
from datetime import datetime

# Python data structures and typing
from dataclasses import dataclass
from enum import Enum

# Logging for debugging and monitoring
import logging
from pathlib import Path

# Rate limiting and delays for respectful web scraping
import time
import random

# URL manipulation utilities
from urllib.parse import urljoin, quote

# Set up basic logging to display informational messages.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """
    Enumeration for the status of a processing task.
    Used to track the lifecycle of episode processing jobs from start to completion.
    """
    PENDING = "pending"         # Task has been created but not started
    IN_PROGRESS = "in_progress" # Task is currently being processed
    COMPLETED = "completed"     # Task finished successfully
    FAILED = "failed"          # Task encountered an error and could not complete

@dataclass
class ProcessingJob:
    """
    Data class to hold information about a processing job.
    
    This represents a single episode processing task, tracking its metadata
    and current status throughout the video generation pipeline.
    
    Attributes:
        id (str): Unique identifier for the job
        url (str): Source URL for the episode transcript
        show (str): Name of the anime show
        status (TaskStatus): Current processing status
        created_at (datetime): When the job was created
        completed_at (datetime, optional): When the job finished (None if still running)
        error_message (str, optional): Error details if the job failed
    """
    id: str
    url: str
    show: str
    status: TaskStatus
    created_at: datetime
    completed_at: datetime = None
    error_message: str = None

class DatabaseManager:
    """Manages the SQLite database for storing and retrieving episode information."""
    
    def __init__(self, db_path="data/databases/video_generator.db"):
        """
        Initializes the DatabaseManager.

        Args:
            db_path (str): The path to the SQLite database file.
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """
        Initializes the database tables if they don't already exist.
        
        Creates two main tables:
        1. episodes: Stores core episode data and processing status
        2. processing_logs: Tracks detailed processing history and performance metrics
        """
        with sqlite3.connect(self.db_path) as conn:
            # Create the 'episodes' table to store details about each show episode.
            # This is the main table containing episode metadata and content
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Unique episode identifier
                    show TEXT NOT NULL,                        -- Anime show name
                    season TEXT NOT NULL,                      -- Season number (as text for flexibility)
                    episode TEXT NOT NULL,                     -- Episode number (as text for flexibility)
                    url TEXT NOT NULL,                         -- Source URL for transcript
                    transcript TEXT,                           -- Full episode transcript text
                    summary TEXT,                              -- AI-generated episode summary
                    plot_points TEXT,                          -- JSON array of key plot points
                    status TEXT DEFAULT 'pending',             -- Processing status (pending/completed/failed)
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When record was created
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When record was last modified
                    UNIQUE(show, season, episode)              -- Prevent duplicate episodes
                )
            """)
            
            # Create the 'processing_logs' table to log the status of various tasks.
            # This table tracks the processing pipeline steps and performance
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Unique log entry identifier
                    episode_id INTEGER,                        -- Reference to episodes table
                    task_type TEXT NOT NULL,                   -- Type of task (transcript, video, etc.)
                    status TEXT NOT NULL,                      -- Task status (started/completed/failed)
                    error_message TEXT,                        -- Error details if task failed
                    processing_time REAL,                      -- Time taken in seconds
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When log entry was created
                    FOREIGN KEY (episode_id) REFERENCES episodes (id)  -- Maintain referential integrity
                )
            """)
    
    def save_episode(self, show, season, episode, url, transcript=None, summary=None, plot_points=None):
        """
        Saves or updates an episode's data in the database.
        
        Uses INSERT OR REPLACE to handle both new episodes and updates to existing ones.
        The plot_points list is serialized to JSON for storage in the TEXT field.

        Args:
            show (str): The name of the show (e.g., "My Hero Academia")
            season (str): The season number (stored as string for flexibility)
            episode (str): The episode number (stored as string for flexibility)
            url (str): The URL of the episode transcript source
            transcript (str, optional): The full transcript text. Defaults to None.
            summary (str, optional): AI-generated episode summary. Defaults to None.
            plot_points (list, optional): List of key plot points for video generation. Defaults to None.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Use INSERT OR REPLACE to handle both new records and updates
            # This prevents duplicate entries while allowing data updates
            conn.execute("""
                INSERT OR REPLACE INTO episodes 
                (show, season, episode, url, transcript, summary, plot_points, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (show, season, episode, url, transcript, summary, json.dumps(plot_points) if plot_points else None))
    
    def get_episode(self, show, season, episode):
        """
        Retrieves a specific episode's data from the database.
        
        Uses row_factory to return results as sqlite3.Row objects, which provide
        both index and name-based access to column data.

        Args:
            show (str): The name of the show to search for
            season (str): The season number to search for
            episode (str): The episode number to search for

        Returns:
            sqlite3.Row: The episode data with named column access, or None if not found.
                        Row object allows accessing columns like row['show'], row['transcript'], etc.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Set row_factory to return Row objects instead of tuples
            # This allows named access to columns (e.g., row['show'])
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM episodes WHERE show = ? AND season = ? AND episode = ?
            """, (show, season, episode))
            return cursor.fetchone()

class ContentAgent:
    """
    Agent responsible for extracting and analyzing content from a URL.
    
    This agent handles the web scraping and initial AI analysis of episode transcripts.
    It manages HTTP requests, HTML parsing, and coordinates with AI models for content analysis.
    """
    
    def __init__(self, model):
        """
        Initializes the ContentAgent with an AI model for content analysis.

        Args:
            model: The generative AI model instance to use for content analysis.
                  Expected to have methods for text processing and analysis.
        """
        self.model = model
        self.retry_count = 3  # Number of retry attempts for failed requests
    
    def extract_and_analyze(self, url):
        """
        Extracts HTML content from a URL, parses it, and uses an AI model to analyze it.
        
        This method implements retry logic to handle network issues and temporary failures.
        It combines web scraping with AI analysis to provide comprehensive content extraction.

        Args:
            url (str): The URL to extract content from (typically an episode transcript page)

        Returns:
            dict: A dictionary containing:
                - transcript (str): Full episode transcript text
                - title (str): Episode title
                - episode (str): Episode identifier
                - analysis (str): AI-generated content analysis
                - success (bool): Whether the operation succeeded
        """
        # Implement retry logic to handle temporary network failures
        for attempt in range(self.retry_count):
            try:
                # Step 1: Attempt to get HTML content from the URL
                # This function handles HTTP requests and basic error handling
                html_content = get_html_content(url)
                if html_content:
                    # Step 2: Parse the HTML to extract transcript and metadata
                    # BeautifulSoup parsing extracts structured data from raw HTML
                    transcript, title, episode = parse_html_with_beautifulsoup(html_content)
                    
                    # Step 3: Create a focused analysis prompt for the AI model
                    # Truncate transcript to avoid token limits while preserving key content
                    analysis_prompt = f"""
                    Analyze this episode transcript and extract:
                    1. Main characters mentioned
                    2. Key themes
                    3. Content rating/age appropriateness
                    4. Emotional tone
                    
                    Transcript: {transcript[:1000]}...
                    Title: {title}
                    """
                    
                    # Step 4: Get AI analysis of the content
                    # This provides metadata that can be used for content classification
                    analysis = self.model.invoke(analysis_prompt)
                    
                    # Return successful result with all extracted data
                    return {
                        'transcript': transcript,
                        'title': title,
                        'episode': episode,
                        'analysis': analysis,
                        'success': True
                    }
                break # Exit retry loop on successful content extraction
            except Exception as e:
                # Log the error with attempt number for debugging
                logger.error(f"Content extraction attempt {attempt + 1} failed: {e}")
                if attempt == self.retry_count - 1:
                    # All retry attempts have been exhausted, return failure
                    return {'success': False, 'error': str(e)}
        
        # Fallback return if loop completes without success (shouldn't happen with current logic)
        return {'success': False, 'error': 'Max retries exceeded'}

class VideoGenerationAgent:
    """
    Agent responsible for tasks related to video generation.
    
    This agent handles image generation, duration calculations, and video composition.
    It coordinates with AI image generation models to create visual content that
    matches the episode's plot points and maintains visual consistency.
    """
    
    def __init__(self):
        """
        Initializes the VideoGenerationAgent.
        
        Sets up the Gemini AI client for image generation capabilities.
        """
        self.client = genai.Client()  # Initialize Gemini client for AI image generation
    
    def generate_optimized_images(self, plot_points, episode_context):
        """
        Creates enhanced prompts for generating images with a consistent visual style.
        
        This method takes raw plot points and enhances them with style instructions
        to ensure visual consistency across all generated images in the video.

        Args:
            plot_points (list): A list of sentences describing key scenes/moments
            episode_context (dict): Context about the episode including show title, season, etc.

        Returns:
            list: Enhanced prompts optimized for AI image generation with consistent styling
        """
        # Define the base style prompt for visual consistency
        # This ensures all images have a cohesive anime art style
        style_prompt = f"""
        Create images in a consistent anime art style for {episode_context['show']}.
        Use vibrant colors, dynamic compositions, and maintain visual continuity.
        Style: Modern anime, high quality, detailed backgrounds.
        """
        
        enhanced_prompts = []
        # Process each plot point to create a styled image generation prompt
        for point in plot_points:
            # Combine the consistent style instructions with the specific scene description
            enhanced_prompt = f"{style_prompt}\n\nScene: {point}"
            enhanced_prompts.append(enhanced_prompt)
        
        return enhanced_prompts
    
    def adaptive_duration_calculation(self, sentences, total_duration):
        """
        Calculates the display duration for each image based on sentence length.
        This creates a proportional timing system where longer descriptions get more screen time.

        Args:
            sentences (list): The list of sentences (plot points) to calculate timing for
            total_duration (float): The total duration of the audio track in seconds

        Returns:
            list: A list of durations (in seconds) for each image, proportional to sentence length
        """
        # Count words in each sentence to determine relative complexity/length
        word_counts = [len(sentence.split()) for sentence in sentences]
        total_words = sum(word_counts)
        
        durations = []
        for word_count in word_counts:
            # Calculate duration based on the proportional word count
            # Longer sentences get more time on screen for better pacing
            ratio = word_count / total_words if total_words > 0 else 0
            duration = total_duration * ratio
            # Ensure a minimum duration of 2 seconds for readability
            # Even short sentences need enough time to be processed visually
            durations.append(max(duration, 2.0))
        
        return durations

class QualityAssuranceAgent:
    """
    Agent responsible for quality checks and content validation.
    
    This agent ensures that generated content meets quality standards before
    final video production. It validates both content coherence and file integrity.
    Acts as a quality gate in the video generation pipeline.
    """
    
    def __init__(self, model):
        """
        Initializes the QualityAssuranceAgent with an AI model for content validation.

        Args:
            model: The generative AI model to use for content quality validation
        """
        self.model = model
    
    def validate_content(self, summary, plot_points):
        """
        Uses an AI model to validate the quality and coherence of the summary and plot points.
        This method performs comprehensive content analysis to ensure the generated material
        is suitable for YouTube audience engagement and maintains narrative quality.

        Args:
            summary (str): The episode summary to validate for accuracy and engagement
            plot_points (list): The list of plot points to check for narrative flow

        Returns:
            dict: AI model result including quality score (1-10) and improvement suggestions
        """
        # Create a comprehensive validation prompt that covers multiple quality dimensions
        validation_prompt = f"""
        Review this episode summary and plot points for:
        1. Accuracy and coherence - Does the content make logical sense?
        2. Appropriate length (should be 2-3 minutes when spoken) - Timing analysis
        3. Engaging content for YouTube audience - Entertainment value assessment
        4. Proper narrative flow - Story progression and pacing
        
        Summary: {summary}
        Plot Points: {plot_points}
        
        Provide a quality score (1-10) and specific suggestions for improvement.
        Focus on clarity, engagement, and narrative structure.
        """
        
        # Get AI validation with comprehensive quality analysis
        validation_result = self.model.invoke(validation_prompt)
        return validation_result
    
    def check_file_integrity(self, file_paths):
        """
        Checks if generated files exist and are not empty.
        This method performs essential file validation to ensure all required
        assets are properly generated before video compilation.

        Args:
            file_paths (list): A list of file paths to check for existence and content

        Returns:
            list: A list of issue descriptions for missing or empty files
        """
        issues = []
        # Validate each file in the generation pipeline
        for file_path in file_paths:
            # Check if file exists at the specified path
            if not os.path.exists(file_path):
                issues.append(f"Missing file: {file_path}")
            # Check if file has content (not zero bytes)
            elif os.path.getsize(file_path) == 0:
                issues.append(f"Empty file: {file_path}")
        
        return issues

class EpisodeDiscoveryAgent:
    """
    Agent responsible for discovering and validating episode URLs.
    
    This agent handles the complex task of finding valid transcript URLs
    for anime episodes across different naming conventions and URL patterns.
    It manages URL generation and validation for reliable content discovery.
    """
    
    def __init__(self):
        """
        Initialize the episode discovery agent with base URL and naming patterns.
        Sets up the foundation for episode URL generation and validation.
        """
        # Base URL for the transcript source website
        self.base_url = "https://subslikescript.com/series/My_Hero_Academia-5626028"
        
        # Dictionary of common episode naming patterns for URL construction
        # Different sites use different URL formats, so we support multiple patterns
        self.episode_patterns = {
            # Standard pattern includes episode title in URL
            "standard": "/season-{season}/episode-{episode}-{title}",
            # Numbered pattern uses only season and episode numbers
            "numbered": "/season-{season}/episode-{episode}",
        }
    
    def generate_episode_url(self, season, episode, episode_title=None):
        """
        Generate episode URL based on season, episode number, and optional title.
        This method constructs URLs using different patterns to accommodate
        various transcript site naming conventions.
        
        Args:
            season (int): Season number for the episode
            episode (int): Episode number within the season
            episode_title (str, optional): Episode title for URL formatting
            
        Returns:
            str: Generated episode URL formatted for transcript access
        """
        if episode_title:
            # Clean up the episode title for URL compatibility
            # Remove special characters that could break URLs
            formatted_title = re.sub(r'[^\w\s-]', '', episode_title)
            # Replace spaces with underscores for URL format
            formatted_title = re.sub(r'[\s]+', '_', formatted_title)
            # Construct URL with title included
            url = f"{self.base_url}/season-{season}/episode-{episode}-{formatted_title}"
        else:
            # Use simple numbered format when no title is provided
            url = f"{self.base_url}/season-{season}/episode-{episode}"
        
        return url
    
    def validate_episode_url(self, url):
        """
        Validate if an episode URL exists and contains transcript content.
        This method performs HTTP requests and HTML parsing to verify
        that a URL actually contains usable transcript data.
        
        Args:
            url (str): Episode URL to validate for transcript availability
            
        Returns:
            bool: True if URL is valid and contains transcript content, False otherwise
        """
        try:
            # Attempt to fetch the webpage
            response = requests.get(url)
            # Check if the request was successful (HTTP 200)
            if response.status_code == 200:
                # Parse the HTML content to look for transcript data
                soup = BeautifulSoup(response.text, 'html.parser')
                # Look for the specific element that contains transcript content
                # This is site-specific - different transcript sites use different structures
                transcript_element = soup.find(class_="full-script")
                return transcript_element is not None
        except Exception as e:
            # Log any errors that occur during validation
            logger.error(f"URL validation failed for {url}: {e}")
        
        # Return False if any error occurs or content is not found
        return False
    
    def discover_episode_url(self, season, episode, possible_titles=None):
        """
        Discover the correct URL for an episode by trying different patterns.
        This method implements a fallback strategy to find working URLs
        when exact patterns are unknown or inconsistent.
        
        Args:
            season (int): Season number to search for
            episode (int): Episode number within the season
            possible_titles (list, optional): List of possible episode titles to try
            
        Returns:
            str or None: Valid episode URL if found, None if no valid URL discovered
        """
        # First attempt: Try the simplest pattern without episode title
        # This often works for sites with consistent numbering
        url = self.generate_episode_url(season, episode)
        if self.validate_episode_url(url):
            return url
        
        # Second attempt: Try with each provided title
        # Episode titles can help when sites use title-based URLs
        if possible_titles:
            for title in possible_titles:
                url = self.generate_episode_url(season, episode, title)
                if self.validate_episode_url(url):
                    return url
        
        # Log failure for debugging and monitoring
        logger.warning(f"Could not find valid URL for Season {season}, Episode {episode}")
        return None

class EpisodeConfigManager:
    """
    Manages episode configurations and batch processing settings.
    
    This class handles the configuration of anime series data including
    season information, episode counts, and known episode titles.
    It provides structured data management for batch processing operations.
    """
    
    def __init__(self):
        """
        Initialize configuration manager with default series settings.
        Sets up the basic structure for My Hero Academia episode management.
        """
        # Default configuration with series structure
        # This defines the basic framework for the anime series
        self.default_config = {
            "show": "My Hero Academia",
            # Season structure with episode counts and title storage
            "seasons": {
                1: {"episodes": 13, "titles": {}},  # First season episode count
                2: {"episodes": 25, "titles": {}},  # Subsequent seasons
                3: {"episodes": 25, "titles": {}},
                4: {"episodes": 25, "titles": {}},
                5: {"episodes": 25, "titles": {}},
                6: {"episodes": 25, "titles": {}},
                7: {"episodes": 21, "titles": {}}   # Latest season (may vary)
            }
        }
        # Load any known episode titles for better URL generation
        self.load_episode_titles()
    
    def load_episode_titles(self):
        """
        Load known episode titles for better URL generation.
        This method populates the configuration with actual episode titles
        to improve URL discovery success rates.
        """
        # Sample episode titles for Season 1 of My Hero Academia
        # These titles help generate accurate URLs for transcript sources
        season_1_titles = {
            1: "Izuku_Midoriya_Origin",           # Series pilot episode
            2: "What_It_Takes_to_Be_a_Hero",     # Hero fundamentals
            3: "Roaring_Muscles",                # Physical training focus
            4: "Start_Line",                     # Competition beginning
            5: "What_I_Can_Do_for_Now",          # Character development
            6: "Rage_You_Damn_Nerd",             # Conflict episode
            7: "Deku_vs_Kacchan",                # Major character confrontation
            8: "Bakugo's_Start_Line",            # Character backstory
            9: "Yeah_Just_Do_Your_Best_Ida",     # Supporting character focus
            10: "Encounter_with_the_Unknown",    # Plot advancement
            11: "Game_Over",                     # Crisis episode
            12: "All_Might",                     # Mentor focus
            13: "In_Each_of_Our_Hearts"          # Season finale
        }
        
        # Store the titles in the configuration structure
        self.default_config["seasons"][1]["titles"] = season_1_titles
    
    def get_episode_config(self, season, episode):
        """
        Get configuration for a specific episode.
        This method retrieves all relevant metadata for an episode
        including title information and season context.
        
        Args:
            season (int): Season number to get configuration for
            episode (int): Episode number within the season
            
        Returns:
            dict: Episode configuration with show name, season, episode, title, and limits
        """
        # Check if the requested season exists in our configuration
        if season in self.default_config["seasons"]:
            season_config = self.default_config["seasons"][season]
            # Get the episode title if available, None if not found
            episode_title = season_config["titles"].get(episode)
            
            # Return comprehensive episode configuration
            return {
                "show": self.default_config["show"],        # Show name
                "season": season,                           # Season number
                "episode": episode,                         # Episode number
                "title": episode_title,                     # Episode title (may be None)
                "max_episodes": season_config["episodes"]   # Total episodes in season
            }
        
        # Return None if season is not configured
        return None
    
    def get_season_episodes(self, season):
        """
        Get all episode numbers for a season.
        This method provides a complete list of episode numbers
        for batch processing operations.
        
        Args:
            season (int): Season number to get episode list for
            
        Returns:
            list: List of episode numbers (1 to max_episodes), empty list if season not found
        """
        # Check if the season exists in our configuration
        if season in self.default_config["seasons"]:
            # Get the maximum number of episodes for this season
            max_episodes = self.default_config["seasons"][season]["episodes"]
            # Generate a list from 1 to max_episodes (inclusive)
            return list(range(1, max_episodes + 1))
        
        # Return empty list if season is not configured
        return []

class WorkflowOrchestrator:
    """
    Orchestrates the entire video generation workflow from start to finish.
    
    This is the main coordination class that brings together all the specialized agents
    to create a complete video generation pipeline. It manages the flow from transcript
    discovery through final video output, handling errors and state management.
    """
    
    def __init__(self):
        """
        Initializes all the necessary components and agents.
        Sets up the complete ecosystem for video generation including
        database, AI models, and all specialized agents.
        """
        # Core infrastructure components
        self.db = DatabaseManager()                                        # Database operations
        self.model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")  # AI model
        
        # Specialized agent instances for different aspects of video generation
        self.content_agent = ContentAgent(self.model)                      # Content analysis and generation
        self.video_agent = VideoGenerationAgent()                          # Video and image generation
        self.qa_agent = QualityAssuranceAgent(self.model)                  # Quality control and validation
        self.discovery_agent = EpisodeDiscoveryAgent()                     # URL discovery and validation
        self.transcript_agent = TranscriptDiscoveryAgent()                 # Transcript extraction
        self.config_manager = EpisodeConfigManager()                       # Configuration management
        
        # Structured output model for consistent data format
        self.model_with_structure = self.model.with_structured_output(Episode_Summary_Schema)
    
    def process_episode(self, url, show_name):
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
            if not content_result['success']:
                raise Exception(f"Content extraction failed: {content_result['error']}")
            
            # Step 2: Generate a structured summary using the AI model
            # Transform raw transcript into YouTube-ready content with plot points
            logger.info("Generating AI summary")
            summary_result = self.generate_structured_summary(content_result, show_name)
            
            # Step 3: Validate the generated content for quality and coherence
            # Ensure the content meets standards before proceeding to media generation
            logger.info("Validating content quality")
            quality_check = self.qa_agent.validate_content(
                summary_result['youtube_transcript'], 
                summary_result['plot_points']
            )
            
            # Step 4: Save the processed data to the database for persistence
            # Store all generated content for future reference and reprocessing
            self.db.save_episode(
                summary_result['show'],
                summary_result['season'], 
                summary_result['episode'],
                url,
                content_result['transcript'],
                summary_result['youtube_transcript'],
                summary_result['plot_points']
            )
            
            # Step 5: Generate the image and audio files for video compilation
            # Create all media assets needed for the final video output
            logger.info("Generating media files")
            self.generate_all_media(summary_result)
            
            # Log successful completion and return success response
            logger.info(f"Successfully processed episode {job_id}")
            return {"success": True, "job_id": job_id, "data": summary_result}
            
        except Exception as e:
            # Handle any errors that occur during the workflow
            logger.error(f"Workflow failed for {job_id}: {e}")
            return {"success": False, "job_id": job_id, "error": str(e)}
    
    def generate_structured_summary(self, content_result, show_name):
        """
        Generates a structured summary using a predefined prompt and an AI model.
        This method transforms raw transcript data into YouTube-ready content
        with proper formatting and engagement elements.

        Args:
            content_result (dict): The dictionary containing the transcript and analysis
            show_name (str): The name of the show for context and branding

        Returns:
            dict: A dictionary with the structured summary including plot points and transcript
        """
        from langchain_core.prompts import ChatPromptTemplate
        
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
        prompt = prompt_template.invoke({
            "Show": show_name, 
            "text": content_result['transcript'],
            "context": content_result.get('analysis', '')
        })
        
        # Use the structured output model to ensure consistent data format
        response = self.model_with_structure.invoke(prompt)
        return response.model_dump()
    
    def generate_all_media(self, episode_data):
        """
        Generates all media files (images, audio, video) for the episode.
        This method coordinates the creation of all visual and audio assets
        needed for the final video compilation.

        Args:
            episode_data (dict): The structured data of the episode including plot points and metadata
        """
        # Step 1: Generate AI image prompts with consistent styling
        # Create enhanced prompts that maintain visual continuity across images
        enhanced_prompts = self.video_agent.generate_optimized_images(
            episode_data['plot_points'], 
            episode_data
        )
        
        # Step 2: Create the actual image files using AI image generation
        # Generate visual assets for each plot point in the episode
        create_images(enhanced_prompts, episode_data['episode'], 
                     episode_data['season'], episode_data['show'])
        
        # Step 3: Generate the audio file from the YouTube transcript
        # Convert text to speech for the video narration
        wave_length = wave_file(
            show=episode_data['show'],
            season=episode_data['season'], 
            episode=episode_data['episode'],
            contents=episode_data['youtube_transcript']
        )
        
        # Step 4: Calculate adaptive durations for each image in the video
        # Determine how long each image should be displayed based on content length
        durations = self.video_agent.adaptive_duration_calculation(
            episode_data['plot_points'], wave_length
        )
        
        # Step 5: Create the final MP4 video file with synchronized audio and images
        # Compile all assets into the final video output
        mp4_file_enhanced(
            show=episode_data['show'],
            season=episode_data['season'],
            episode=episode_data['episode'], 
            sentences=episode_data['plot_points'],
            durations=durations
        )

def mp4_file_enhanced(show, season, episode, sentences, durations):
    """
    Creates an MP4 video file from images and an audio file with adaptive slide durations.
    This function is the final assembly step that combines all generated assets
    (images, audio, intro video) into a complete YouTube-ready video.

    Args:
        show (str): The name of the show for file path construction
        season (str): The season number for file path construction
        episode (str): The episode number for file path construction
        sentences (list): A list of plot points (used to find corresponding images)
        durations (list): A list of durations for each image in seconds
    """
    print("create enhanced mp4")
    array_ic = []
    
    # Create an ImageClip for each sentence/image with its calculated duration
    # This step builds the visual timeline with proportional timing
    for index, (sentence, duration) in enumerate(zip(sentences, durations)):
        # Construct path to the generated image file
        image_path = f"{show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png"
        # Create MoviePy ImageClip with specific duration
        ic = ImageClip(image_path).with_duration(duration)
        array_ic.append(ic)
    
    # Load the intro video and the generated audio file
    intro_video = VideoFileClip(f"{show}/tldr_mha_intro.mp4")     # Channel branding intro
    ac_1 = AudioFileClip(f"{show}/Season{season}/Episode{episode}/{show}_{episode}.wav")  # Narration audio
    
    # Concatenate the image clips to create the main content video
    video = concatenate_videoclips(clips=array_ic, method="compose")
    # Attach the audio narration to the visual content
    video_with_audio = video.with_audio(ac_1)
    
    # Add the intro video to the beginning for channel branding
    video_with_intro = concatenate_videoclips(clips=[intro_video, video_with_audio], method="compose")
    
    # Write the final video file with optimized settings for YouTube
    # Use 24fps for smooth playback and AAC audio codec for compatibility
    video_with_intro.write_videofile(
        f"{show}/Season{season}/Episode{episode}/{show}_{season}_{episode}.mp4", 
        fps=24, audio_codec="aac"
    )
    
    # Clean up audio resources to prevent memory leaks
    ac_1.close()

# Pydantic schema imports for structured data validation
from typing import Optional
from pydantic import BaseModel, Field

# Pydantic schema for ensuring the AI model output is in a structured format
# This schema enforces consistent data structure across all episode processing
class Episode_Summary_Schema(BaseModel):
    """
    Summary of a given show episode with structured data validation.
    
    This schema ensures that AI-generated episode summaries contain all required
    fields with proper data types for consistent processing throughout the pipeline.
    """
    show: str = Field(description="The title of the show")
    season: str = Field(description="The numerical season of the show")  
    episode: str = Field(description="The numerical episode of the show")
    youtube_transcript: str = Field(description="Summary of the entire episode optimized for YouTube narration")
    plot_points: list[str] = Field(description="Single sentence summaries of major plot points in this episode")

def get_html_content(url):
    """
    Fetches the HTML content from a given URL.
    This function handles HTTP requests with proper error handling
    to retrieve webpage content for transcript extraction.

    Args:
        url (str): The URL of the webpage to fetch

    Returns:
        str: The HTML content of the page, or None if an error occurs
    """
    print("retrieve html")
    try:
        # Make HTTP GET request to fetch webpage content
        response = requests.get(url)
        # Raise an HTTPError for bad responses (4xx or 5xx status codes)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        # Log and handle any network or HTTP errors
        print(f"Error fetching URL {url}: {e}")
        return None

def parse_html_with_beautifulsoup(html_content):
    """
    Parses HTML content using BeautifulSoup and extracts various information.
    This function specifically targets transcript content from episode pages
    and extracts metadata like title and episode information.

    Args:
        html_content (str): The HTML content as a string to parse

    Returns:
        tuple: (transcript_text, title, episode) - extracted content and metadata
    """
    print("parse html")
    if not html_content:
        print("No HTML content to parse.")
        return None, None, None

    # Parse HTML content using BeautifulSoup for element extraction
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract the page title from the h1 element
    title = soup.find('h1')
    if title:
        title = title.get_text()
    
    # Use regex to extract season and episode information from title
    match = re.search(r'Season \d+, Episode \d+', title)
    episode = match.group(0) if match else "Unknown Episode"

    # Find the transcript content using the specific class name
    # This is site-specific - different transcript sites use different structures
    items = soup.find(class_="full-script")
    if items:
        # Return the transcript text along with metadata
        return items.get_text(), title, episode
    else:
        print("  No elements with class 'full-script' found.")
        return None, title, episode

def create_images(sentences, episode, season, show):
    """
    Creates AI-generated images for each plot point in the episode.
    This function coordinates the generation of multiple images that will
    be used as visual slides in the final video compilation.
    
    Args:
        sentences (list): List of plot point descriptions or enhanced prompts for image generation
        episode (str): Episode identifier for file naming and organization
        season (str): Season identifier for file naming and organization
        show (str): Show name for file naming and organization
    """
    print(f"iterate through and create {len(sentences)} images")
    # Generate an image for each plot point/sentence
    for index, sentence in enumerate(sentences):
        create_image(sentence, episode, season, show, index)

def create_image(image_sentence, episode, season, show, index): 
    """
    Generate a single image using AI based on plot point description.
    This function uses Google's Gemini model to create anime-style images
    that visually represent specific scenes from the episode.
    
    Args:
        image_sentence (str): Description of the scene to generate (enhanced prompt with style)
        episode (str): Episode identifier for file naming
        season (str): Season identifier for file naming
        show (str): Show name for file naming
        index (int): Image index for unique filename generation
    """
    print(f"create image:{index}")
    # Initialize Google Generative AI client for image generation
    client = genai.Client()
    
    # Generate image using Gemini's image generation model
    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=image_sentence,
        config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE']  # Request both text and image output
        )
    )
    
    # Process the response to extract and save the generated image
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            # Print any text response from the model
            print(part.text)
        elif part.inline_data is not None:
            # Extract and save the generated image
            image = Image.open(BytesIO((part.inline_data.data)))
            # Ensure the directory structure exists
            os.makedirs(f"{show}/Season{season}/Episode{episode}", exist_ok=True)
            # Save image with structured filename for video compilation
            image.save(f"{show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png")

def wave_file(show, season, episode, contents, channels=1, rate=24000, sample_width=2):
    """
    Generate audio file from text using AI text-to-speech.
    This function converts the YouTube transcript text into spoken narration
    using Google's Gemini TTS model with a specific voice configuration.
    
    Args:
        show (str): Show name for file organization
        season (str): Season identifier for file organization
        episode (str): Episode identifier for file organization
        contents (str): Text content to convert to speech (YouTube transcript)
        channels (int): Audio channels (default: 1 for mono audio)
        rate (int): Sample rate in Hz (default: 24000 for good quality)
        sample_width (int): Sample width in bytes (default: 2 for 16-bit audio)
        
    Returns:
        float: Duration of generated audio file in seconds for video timing
    """
    print("create wave file")
    # Initialize Google Generative AI client for text-to-speech
    client = genai.Client()
    
    # Ensure the directory structure exists for audio file storage
    os.makedirs(f"{show}/Season{season}/Episode{episode}", exist_ok=True)
    file_name = f"{show}/Season{season}/Episode{episode}/{show}_{episode}.wav"
    
    # Generate speech audio using Gemini TTS model
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],  # Request audio output only
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name='Kore',  # Use specific voice for consistency
                    )
                )
            ),
        )
    )
    
    # Extract audio data from the response
    data = response.candidates[0].content.parts[0].inline_data.data

    # Write the audio data to a WAV file with specified parameters
    with wave.open(file_name, "wb") as wf:
        wf.setnchannels(channels)      # Set audio channels
        wf.setsampwidth(sample_width)  # Set bit depth
        wf.setframerate(rate)          # Set sample rate
        wf.writeframes(data)           # Write audio data

    # Return the duration for video timing calculations
    return get_wav_duration(file_name)

def get_wav_duration(wav_file_path):
    """
    Determine the duration of a WAV audio file.
    This function calculates the exact duration needed for video timing
    by analyzing the audio file's frame count and sample rate.
    
    Args:
        wav_file_path (str): Path to WAV file to analyze
        
    Returns:
        float: Duration in seconds for video synchronization
    """
    print("determine wave duration")
    # Open WAV file in read mode and extract timing information
    with wave.open(wav_file_path, 'r') as wf:
        num_frames = wf.getnframes()    # Total number of audio frames
        frame_rate = wf.getframerate()  # Frames per second (sample rate)
        # Calculate duration: total frames divided by frames per second
        duration = num_frames / frame_rate
        return duration

def read_json(file_path):
    """
    Read and parse JSON data from file.
    This utility function loads and displays JSON configuration data
    for debugging and data inspection purposes.
    
    Args:
        file_path (str): Path to JSON file to read
        
    Returns:
        dict: Parsed JSON data structure
    """
    from pathlib import Path
    from pprint import pprint

    # Load JSON file and parse the content
    data = json.loads(Path(file_path).read_text())
    print('loaded json')
    # Pretty print the data for debugging/inspection
    pprint(data)
    return data

# Import required for model initialization
from langchain.chat_models import init_chat_model

class TranscriptDiscoveryAgent:
    """
    Agent that searches multiple public sources for anime episode transcripts.
    
    This specialized agent implements a multi-source strategy for finding episode
    transcripts across different websites. It handles various URL patterns,
    search mechanisms, and content extraction methods for robust transcript discovery.
    """
    
    def __init__(self):
        """
        Initialize the transcript discovery agent with multiple source configurations.
        Sets up a comprehensive configuration for different transcript websites
        with their specific search patterns and content selectors.
        """
        # Configuration for multiple transcript sources
        # Each source has specific URL patterns, selectors, and search capabilities
        self.sources = {
            # Primary source: SubsLikeScript (reliable anime transcripts)
            'subslikescript': {
                'base_url': 'https://subslikescript.com',
                'search_url': 'https://subslikescript.com/search',
                # Multiple URL patterns to try for episode discovery
                'search_patterns': [
                    '/series/{show_slug}',                                      # Show overview page
                    '/series/{show_slug}/season-{season}/episode-{episode}',   # Episode with number
                    '/series/{show_slug}/season-{season}/episode-{episode}-{title_slug}'  # Episode with title
                ],
                'transcript_selector': '.full-script',      # CSS selector for transcript content
                'title_selector': 'h1',                     # CSS selector for page title
                'search_result_selector': 'a[href*="series"]',  # Search result links
                'search_title_selector': '',                # Use link text directly
                'supports_search': True                     # Has search functionality
            },
            # Secondary source: Transcripts Wiki (Fandom-based transcripts)
            'transcripts_wiki': {
                'base_url': 'https://transcripts.fandom.com',
                'search_url': 'https://community.fandom.com/wiki/Special:Search',
                # Wiki-style URL patterns
                'search_patterns': [
                    '/wiki/{show_slug}',                           # Show main page
                    '/wiki/{show_slug}/Season_{season}',          # Season page
                    '/wiki/{show_slug}_Season_{season}_Episode_{episode}'  # Specific episode
                ],
                'transcript_selector': '.mw-parser-output',   # MediaWiki content area
                'title_selector': '.page-header__title',      # Wiki page title
                'search_result_selector': 'a[href*="/wiki/"]', # Wiki search results
                'search_title_selector': '.unified-search__result__title',  # Search result titles
                'supports_search': True,
                # Additional search parameters for Fandom search
                'search_params': {
                    'scope': 'cross-wiki',
                    'contentType': '',
                    'ns[0]': '0',      # Main namespace
                    'ns[1]': '4',      # Project namespace
                    'ns[2]': '12',     # Help namespace
                    'ns[3]': '110',
                    'ns[4]': '112',
                    'ns[5]': '118',
                    'ns[6]': '500',
                    'ns[7]': '502',
                    'ns[8]': '2900'
                }
            },
            'anime_transcripts': {
                'base_url': 'https://anime-transcripts.com',
                'search_patterns': [
                    '/{show_slug}',
                    '/{show_slug}/season-{season}',
                    '/{show_slug}/s{season}e{episode:02d}'
                ],
                'transcript_selector': '.transcript-content',
                'title_selector': '.episode-title',
                'supports_search': False
            }
        }
        
        # Common show name mappings to URL slugs
        self.show_mappings = {
            'My Hero Academia': ['my-hero-academia', 'boku-no-hero-academia', 'mha', 'My_Hero_Academia-5626028'],
            'Attack on Titan': ['attack-on-titan', 'shingeki-no-kyojin', 'aot'],
            'Demon Slayer': ['demon-slayer', 'kimetsu-no-yaiba'],
            'One Piece': ['one-piece'],
            'Naruto': ['naruto', 'naruto-shippuden'],
            'Dragon Ball': ['dragon-ball', 'dragon-ball-z', 'dragon-ball-super'],
            'Death Note': ['death-note'],
            'Fullmetal Alchemist': ['fullmetal-alchemist', 'fma'],
            'Hunter x Hunter': ['hunter-x-hunter', 'hxh'],
            'Tokyo Ghoul': ['tokyo-ghoul'],
            'Jujutsu Kaisen': ['jujutsu-kaisen'],
            'Chainsaw Man': ['chainsaw-man'],
            'Frieren: Beyond Journey\'s End': ['Frieren_Beyond_Journeys_End-22248376', 'frieren-beyond-journeys-end']
        }
        
        # Request session with retry and delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.retry_count = 3
        self.delay_range = (1, 3)  # Random delay between requests
    
    def get_show_slugs(self, show_name):
        """
        Get possible URL slugs for a show name with comprehensive pattern generation.
        
        Args:
            show_name (str): The show name
            
        Returns:
            list: List of possible URL slugs
        """
        # Check if we have predefined mappings
        if show_name in self.show_mappings:
            return self.show_mappings[show_name]
        
        slugs = []
        original = show_name.strip()
        
        # Basic cleanup
        cleaned = original.lower()
        
        # Handle common patterns and special characters
        replacements = [
            # Remove/replace punctuation
            (':', ''),
            ("'", ''),
            ('"', ''),
            ('!', ''),
            ('?', ''),
            ('.', ''),
            (',', ''),
            ('&', 'and'),
            ('+', 'plus'),
            ('~', ''),
            ('/', '-'),
            ('\\', '-'),
            ('(', ''),
            (')', ''),
            ('[', ''),
            (']', ''),
            ('{', ''),
            ('}', ''),
        ]
        
        # Generate multiple variations
        for old, new in replacements:
            cleaned = cleaned.replace(old, new)
        
        # Remove extra spaces and normalize
        cleaned = ' '.join(cleaned.split())
        
        # Pattern 1: Standard dash-separated
        slugs.append(cleaned.replace(' ', '-'))
        
        # Pattern 2: Underscore-separated
        slugs.append(cleaned.replace(' ', '_'))
        
        # Pattern 3: No separators (concatenated)
        slugs.append(cleaned.replace(' ', ''))
        
        # Pattern 4: Title case with dashes
        title_case = '-'.join(word.capitalize() for word in cleaned.split())
        slugs.append(title_case)
        
        # Pattern 5: Handle subtitle patterns (e.g., "Title: Subtitle" -> "title-subtitle")
        if ':' in original:
            parts = [part.strip() for part in original.split(':')]
            if len(parts) == 2:
                main_title, subtitle = parts
                # Main title only
                main_cleaned = self._clean_title_part(main_title)
                slugs.append(main_cleaned.replace(' ', '-'))
                slugs.append(main_cleaned.replace(' ', '_'))
                
                # Subtitle only
                sub_cleaned = self._clean_title_part(subtitle)
                slugs.append(sub_cleaned.replace(' ', '-'))
                slugs.append(sub_cleaned.replace(' ', '_'))
                
                # Combined variations
                combined = f"{main_cleaned} {sub_cleaned}"
                slugs.append(combined.replace(' ', '-'))
                slugs.append(combined.replace(' ', '_'))
        
        # Pattern 6: Acronyms (first letter of each word)
        words = cleaned.split()
        if len(words) > 1:
            acronym = ''.join(word[0] for word in words if word)
            slugs.append(acronym)
            slugs.append(acronym.upper())
        
        # Pattern 7: Remove common words
        common_words = {'the', 'a', 'an', 'of', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}
        filtered_words = [word for word in words if word not in common_words]
        if len(filtered_words) != len(words):
            filtered_title = ' '.join(filtered_words)
            slugs.append(filtered_title.replace(' ', '-'))
            slugs.append(filtered_title.replace(' ', '_'))
        
        # Pattern 8: Handle numbers (convert to words and vice versa)
        number_map = {
            '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five',
            '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten',
            'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
            'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'
        }
        
        for old_num, new_num in number_map.items():
            if old_num in cleaned:
                numbered_variant = cleaned.replace(old_num, new_num)
                slugs.append(numbered_variant.replace(' ', '-'))
                slugs.append(numbered_variant.replace(' ', '_'))
        
        # Remove duplicates while preserving order
        unique_slugs = []
        seen = set()
        for slug in slugs:
            if slug and slug not in seen:
                unique_slugs.append(slug)
                seen.add(slug)
        
        return unique_slugs
    
    def _clean_title_part(self, title_part):
        """Helper method to clean individual title parts."""
        cleaned = title_part.lower().strip()
        
        # Remove special characters
        for char in ":'\"!?.,&+~()[]{}":
            cleaned = cleaned.replace(char, '')
        
        # Normalize spaces
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def format_episode_title(self, title):
        """
        Format episode title for URL usage.
        
        Args:
            title (str): Episode title
            
        Returns:
            str: Formatted title slug
        """
        if not title:
            return ''
        
        # Remove special characters and format for URL
        slug = title.lower()
        slug = ''.join(c for c in slug if c.isalnum() or c in ' -_')
        slug = slug.replace(' ', '-')
        slug = '-'.join(filter(None, slug.split('-')))  # Remove empty parts
        
        return slug
    
    def search_source(self, source_name, show_name, season, episode, episode_title=None):
        """
        Search a specific source for episode transcript.
        
        Args:
            source_name (str): Name of the source to search
            show_name (str): Show name
            season (int): Season number
            episode (int): Episode number
            episode_title (str, optional): Episode title
            
        Returns:
            dict: Search result with transcript data or None
        """
        if source_name not in self.sources:
            return None
        
        source_config = self.sources[source_name]
        show_slugs = self.get_show_slugs(show_name)
        
        for show_slug in show_slugs:
            for pattern in source_config['search_patterns']:
                try:
                    # Format the URL pattern
                    if '{title_slug}' in pattern and episode_title:
                        title_slug = self.format_episode_title(episode_title)
                        url = source_config['base_url'] + pattern.format(
                            show_slug=show_slug,
                            season=season,
                            episode=episode,
                            title_slug=title_slug
                        )
                    else:
                        url = source_config['base_url'] + pattern.format(
                            show_slug=show_slug,
                            season=season,
                            episode=episode
                        )
                    
                    logger.info(f"Trying {source_name}: {url}")
                    
                    # Attempt to fetch and parse
                    result = self._fetch_and_parse(url, source_config)
                    if result:
                        result['source'] = source_name
                        result['url'] = url
                        return result
                    
                    # Random delay between requests
                    time.sleep(random.uniform(*self.delay_range))
                    
                except Exception as e:
                    logger.debug(f"Error searching {source_name} with pattern {pattern}: {e}")
                    continue
        
        return None
    
    def _fetch_and_parse(self, url, source_config):
        """
        Fetch URL and parse content according to source configuration.
        
        Args:
            url (str): URL to fetch
            source_config (dict): Source-specific parsing configuration
            
        Returns:
            dict: Parsed content or None if failed
        """
        for attempt in range(self.retry_count):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract transcript
                transcript_element = soup.select_one(source_config['transcript_selector'])
                if not transcript_element:
                    return None
                
                transcript = transcript_element.get_text(strip=True, separator=' ')
                
                # Extract title
                title_element = soup.select_one(source_config['title_selector'])
                title = title_element.get_text(strip=True) if title_element else "Unknown Title"
                
                # Basic content validation
                if len(transcript) < 500:  # Too short to be a full transcript
                    return None
                
                # Extract episode info from title or URL
                episode_info = self._extract_episode_info(title, url)
                
                return {
                    'transcript': transcript,
                    'title': title,
                    'episode_info': episode_info,
                    'content_length': len(transcript),
                    'quality_score': self._assess_content_quality(transcript)
                }
                
            except requests.exceptions.RequestException as e:
                logger.debug(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
            except Exception as e:
                logger.debug(f"Parsing failed: {e}")
                break
        
        return None
    
    def _extract_episode_info(self, title, url):
        """
        Extract episode information from title or URL.
        
        Args:
            title (str): Page title
            url (str): Page URL
            
        Returns:
            dict: Extracted episode information
        """
        episode_info = {'season': None, 'episode': None}
        
        # Try to extract from title
        season_match = re.search(r'[Ss]eason\s*(\d+)', title)
        episode_match = re.search(r'[Ee]pisode\s*(\d+)', title)
        
        if season_match:
            episode_info['season'] = season_match.group(1)
        if episode_match:
            episode_info['episode'] = episode_match.group(1)
        
        # Try to extract from URL if not found in title
        if not episode_info['season']:
            season_match = re.search(r'season[-_](\d+)', url, re.I)
            if season_match:
                episode_info['season'] = season_match.group(1)
        
        if not episode_info['episode']:
            episode_match = re.search(r'episode[-_](\d+)', url, re.I)
            if episode_match:
                episode_info['episode'] = episode_match.group(1)
        
        return episode_info
    
    def _assess_content_quality(self, transcript):
        """
        Assess the quality of transcript content.
        
        Args:
            transcript (str): Transcript text
            
        Returns:
            float: Quality score from 0.0 to 1.0
        """
        score = 0.0
        
        # Length check
        if len(transcript) > 1000:
            score += 0.3
        elif len(transcript) > 500:
            score += 0.2
        
        # Dialogue indicators
        dialogue_indicators = [':', '"', '–', '-', 'said', 'replied']
        if any(indicator in transcript for indicator in dialogue_indicators):
            score += 0.3
        
        # Narrative structure
        narrative_words = ['scene', 'cut to', 'fade in', 'fade out', 'meanwhile']
        if any(word in transcript.lower() for word in narrative_words):
            score += 0.2
        
        # Character names (common anime character patterns)
        if len([word for word in transcript.split() if word[0].isupper()]) > 10:
            score += 0.2
        
        return min(score, 1.0)
    
    def find_episode_transcript(self, show_name, season, episode, episode_title=None, use_discovery=True):
        """
        Search all sources for the best episode transcript with enhanced discovery.
        
        Args:
            show_name (str): Show name
            season (int): Season number
            episode (int): Episode number
            episode_title (str, optional): Episode title for better matching
            use_discovery (bool): Whether to use dynamic pattern discovery
            
        Returns:
            dict: Best transcript result or None if not found
        """
        logger.info(f"Searching for {show_name} Season {season} Episode {episode}")
        
        all_results = []
        
        # First pass: Try site search functionality for supported sources
        for source_name, source_config in self.sources.items():
            if source_config.get('supports_search', False):
                logger.info(f"🔍 Trying site search for {source_name}")
                result = self.search_using_site_search(source_name, show_name, season, episode)
                if result:
                    all_results.append(result)
                    logger.info(f"Found transcript via search on {source_name} (quality: {result['quality_score']:.2f})")
        
        # Second pass: Standard URL pattern search for all sources
        if not all_results:
            logger.info("🔗 Trying standard URL patterns...")
            for source_name in self.sources.keys():
                result = self.search_source(source_name, show_name, season, episode, episode_title)
                if result:
                    all_results.append(result)
                    logger.info(f"Found transcript on {source_name} (quality: {result['quality_score']:.2f})")
        
        # Third pass: Enhanced discovery if no results and discovery is enabled
        if not all_results and use_discovery:
            logger.info(f"No results found with standard methods. Trying enhanced discovery...")
            result = self.search_with_fallback_discovery(show_name, season, episode, episode_title)
            if result:
                all_results.append(result)
        
        if not all_results:
            logger.warning(f"No transcripts found for {show_name} S{season}E{episode}")
            return None
        
        # Select best result based on quality score and content length
        best_result = max(all_results, key=lambda x: (x['quality_score'], x['content_length']))
        
        search_method = "search" if best_result.get('found_via_search') else "URL patterns"
        logger.info(f"Selected best result from {best_result['source']} via {search_method} "
                   f"(quality: {best_result['quality_score']:.2f}, "
                   f"length: {best_result['content_length']} chars)")
        
        return best_result

    def process_episode_by_numbers(self, season, episode, episode_title=None, show_name="My Hero Academia"):
        """
        Process episode by season and episode numbers using transcript discovery.
        
        Args:
            season (int): Season number
            episode (int): Episode number
            episode_title (str, optional): Episode title for better matching
            show_name (str): Show name (default: "My Hero Academia")
            
        Returns:
            dict: Processing result
        """
        # Use transcript discovery agent to find the episode
        transcript_result = self.transcript_agent.find_episode_transcript(
            show_name, season, episode, episode_title
        )
        
        if not transcript_result:
            return {
                'success': False, 
                'error': f'No transcript found for {show_name} Season {season} Episode {episode}'
            }
        
        # Process the found transcript
        try:
            # Create content result in expected format
            content_result = {
                'transcript': transcript_result['transcript'],
                'title': transcript_result['title'],
                'episode': f"Season {season}, Episode {episode}",
                'analysis': f"Found via {transcript_result['source']} with quality score {transcript_result['quality_score']:.2f}",
                'success': True
            }
            
            # Continue with existing processing workflow
            logger.info("Generating AI summary")
            summary_result = self.generate_structured_summary(content_result, show_name)
            
            # Ensure episode info is correctly set
            summary_result['season'] = str(season)
            summary_result['episode'] = str(episode)
            summary_result['show'] = show_name
            
            # Save to database
            self.db.save_episode(
                summary_result['show'],
                summary_result['season'], 
                summary_result['episode'],
                transcript_result['url'],
                content_result['transcript'],
                summary_result['youtube_transcript'],
                summary_result['plot_points']
            )
            
            return {"success": True, "data": summary_result, "source_info": transcript_result}
            
        except Exception as e:
            logger.error(f"Processing failed for Season {season} Episode {episode}: {e}")
            return {"success": False, "error": str(e)}
    
    def process_season_batch(self, season, start_episode=None, end_episode=None, show_name="My Hero Academia"):
        """
        Process multiple episodes in a season.
        
        Args:
            season (int): Season number
            start_episode (int, optional): Starting episode number
            end_episode (int, optional): Ending episode number
            show_name (str): Show name (default: "My Hero Academia")
            
        Returns:
            dict: Batch processing results
        """
        # Get episode configuration
        episode_config = self.config_manager.get_episode_config(season, 1)
        if not episode_config:
            return {'success': False, 'error': f'No configuration found for season {season}'}
        
        # Determine episode range
        if start_episode is None:
            start_episode = 1
        if end_episode is None:
            end_episode = episode_config['max_episodes']
        
        results = {
            'season': season,
            'total_episodes': end_episode - start_episode + 1,
            'successful': 0,
            'failed': 0,
            'episodes': {}
        }
        
        for ep_num in range(start_episode, end_episode + 1):
            logger.info(f"Processing Season {season}, Episode {ep_num}")
            
            # Get episode title if available
            ep_config = self.config_manager.get_episode_config(season, ep_num)
            episode_title = ep_config.get('title') if ep_config else None
            
            result = self.process_episode_by_numbers(season, ep_num, episode_title, show_name)
            
            results['episodes'][ep_num] = result
            if result['success']:
                results['successful'] += 1
            else:
                results['failed'] += 1
            
            # Add delay between episodes to be respectful to servers
            time.sleep(random.uniform(2, 5))
        
        return results

    def discover_show_slug(self, show_name, season=1, episode=1):
        """
        Dynamically discover the correct slug for a show by testing URLs.
        
        Args:
            show_name (str): Show name to discover slug for
            season (int): Season to test with (default: 1)
            episode (int): Episode to test with (default: 1)
            
        Returns:
            str: Working slug if found, None otherwise
        """
        logger.info(f"🔍 Discovering URL patterns for '{show_name}'")
        
        possible_slugs = self.get_show_slugs(show_name)
        
        # Test each source with each slug
        for source_name, source_config in self.sources.items():
            logger.info(f"Testing {source_name}...")
            
            for slug in possible_slugs:
                for pattern in source_config['search_patterns']:
                    try:
                        # Skip patterns that require title_slug
                        if '{title_slug}' in pattern:
                            continue
                            
                        url = source_config['base_url'] + pattern.format(
                            show_slug=slug,
                            season=season,
                            episode=episode
                        )
                        
                        logger.debug(f"Testing: {url}")
                        
                        # Quick HEAD request to check if URL exists
                        response = self.session.head(url, timeout=5)
                        if response.status_code == 200:
                            logger.info(f"✅ Found working pattern: {slug} on {source_name}")
                            
                            # Add to our mappings for future use
                            if show_name not in self.show_mappings:
                                self.show_mappings[show_name] = []
                            if slug not in self.show_mappings[show_name]:
                                self.show_mappings[show_name].append(slug)
                            
                            return slug
                            
                    except Exception as e:
                        logger.debug(f"Failed {url}: {e}")
                        continue
                    
                    # Small delay between tests
                    time.sleep(0.5)
        
        logger.warning(f"❌ No working URL pattern found for '{show_name}'")
        return None
    
    def search_with_fallback_discovery(self, show_name, season, episode, episode_title=None):
        """
        Enhanced search that includes dynamic pattern discovery.
        
        Args:
            show_name (str): Show name
            season (int): Season number
            episode (int): Episode number
            episode_title (str, optional): Episode title
            
        Returns:
            dict: Search result or None
        """
        # First, try the normal search
        result = None
        for source_name in self.sources.keys():
            result = self.search_source(source_name, show_name, season, episode, episode_title)
            if result:
                break
        
        # If normal search fails, try pattern discovery
        if not result:
            logger.info(f"Standard search failed for {show_name}, trying pattern discovery...")
            discovered_slug = self.discover_show_slug(show_name, season, episode)
            
            if discovered_slug:
                # Try search again with discovered pattern
                for source_name in self.sources.keys():
                    result = self.search_source(source_name, show_name, season, episode, episode_title)
                    if result:
                        break
        
        return result
    
    def search_using_site_search(self, source_name, show_name, season, episode):
        """
        Use the site's built-in search functionality to find episodes.
        
        Args:
            source_name (str): Name of the source to search
            show_name (str): Show name
            season (int): Season number
            episode (int): Episode number
            
        Returns:
            dict: Search result with transcript data or None
        """
        if source_name not in self.sources:
            return None
        
        source_config = self.sources[source_name]
        
        # Check if this source supports search
        if not source_config.get('supports_search', False):
            return None
        
        try:
            # Generate source-specific search query
            search_query = self._generate_search_query(source_name, show_name, season, episode)
            search_params = self._get_search_params(source_config, search_query)
            
            logger.info(f"🔍 Searching {source_name} for: '{search_query}'")
            
            # Perform search
            response = self.session.get(
                source_config['search_url'], 
                params=search_params, 
                timeout=10
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find search results
            search_results = soup.select(source_config.get('search_result_selector', 'a'))
            
            # Filter search results based on source type
            relevant_results = []
            for result in search_results:
                href = result.get('href', '')
                text = result.get_text(strip=True)
                
                if source_name == 'transcripts_wiki':
                    # For Fandom, look for wiki pages containing transcripts
                    if (href and '/wiki/' in href and text and len(text) > 5 and 
                        'action=edit' not in href and 'Special:' not in href and
                        'Category:' not in href and 'Template:' not in href):
                        relevant_results.append(result)
                elif source_name == 'subslikescript':
                    # For SubsLikeScript, look for series pages
                    if href and href != '/series' and 'series/' in href and text != 'TV Shows':
                        relevant_results.append(result)
                else:
                    # Default filtering
                    if href and text and len(text) > 3:
                        relevant_results.append(result)
            
            logger.info(f"Found {len(relevant_results)} relevant search results")
            
            if not relevant_results:
                logger.info("No relevant results found in search")
                return None
            
            # Look for the most relevant result
            best_match = self._find_best_search_match(
                relevant_results, show_name, season, episode, source_config
            )
            
            if best_match:
                # Get the result URL
                result_url = best_match.get('href')
                if result_url and not result_url.startswith('http'):
                    result_url = urljoin(source_config['base_url'], result_url)
                
                logger.info(f"🎯 Best match: {result_url}")
                
                if source_name == 'transcripts_wiki':
                    # For wiki sources, the search result might be a direct transcript page
                    # Try multiple attempts to get a valid transcript
                    valid_result = self._try_wiki_page_variants(result_url, source_config)
                    if valid_result:
                        valid_result['source'] = source_name
                        valid_result['found_via_search'] = True
                        return valid_result
                else:
                    # For other sources like SubsLikeScript, find episode on series page
                    episode_url = self._find_episode_on_series_page(
                        result_url, season, episode, source_config
                    )
                    
                    if episode_url:
                        logger.info(f"📺 Found episode URL: {episode_url}")
                        
                        # Fetch and parse the transcript from the episode page
                        result = self._fetch_and_parse(episode_url, source_config)
                        if result:
                            result['source'] = source_name
                            result['url'] = episode_url
                            result['found_via_search'] = True
                            return result
                    else:
                        logger.info("Could not find specific episode on series page")
                        return None
            
        except Exception as e:
            logger.error(f"Search failed for {source_name}: {e}")
        
        return None
    
    def _find_best_search_match(self, search_results, show_name, season, episode, source_config):
        """
        Find the best matching search result for the episode.
        
        Args:
            search_results: List of search result elements
            show_name (str): Show name
            season (int): Season number
            episode (int): Episode number
            source_config (dict): Source configuration
            
        Returns:
            BeautifulSoup element: Best matching result or None
        """
        scored_results = []
        
        for result in search_results:
            # Get the title/text of the search result
            title_element = result.select_one(source_config.get('search_title_selector', ''))
            title = title_element.get_text(strip=True) if title_element else result.get_text(strip=True)
            
            # Get the URL
            url = result.get('href', '')
            
            # Score this result based on relevance
            score = self._score_search_result(title, url, show_name, season, episode)
            
            if score > 0:
                scored_results.append({
                    'element': result,
                    'title': title,
                    'url': url,
                    'score': score
                })
                logger.debug(f"Result: '{title}' (score: {score:.2f})")
        
        # Return the highest scoring result
        if scored_results:
            best_result = max(scored_results, key=lambda x: x['score'])
            logger.info(f"Best match: '{best_result['title']}' (score: {best_result['score']:.2f})")
            return best_result['element']
        
        return None
    
    def _score_search_result(self, title, url, show_name, season, episode):
        """
        Score a search result based on how well it matches the target episode.
        
        Args:
            title (str): Title of the search result
            url (str): URL of the search result
            show_name (str): Target show name
            season (int): Target season
            episode (int): Target episode
            
        Returns:
            float: Relevance score (higher is better)
        """
        score = 0.0
        title_lower = title.lower()
        url_lower = url.lower()
        show_lower = show_name.lower()
        
        # Show name matching (most important)
        show_words = show_lower.split()
        title_words = title_lower.split()
        
        # Check for exact show name match
        if show_lower in title_lower:
            score += 3.0
        else:
            # Check for partial matches
            matching_words = sum(1 for word in show_words if word in title_lower)
            score += (matching_words / len(show_words)) * 2.0
        
        # Season matching
        season_patterns = [
            f"season {season}",
            f"season{season}",
            f"s{season}",
            f"s{season:02d}"
        ]
        
        for pattern in season_patterns:
            if pattern in title_lower or pattern in url_lower:
                score += 1.5
                break
        
        # Episode matching
        episode_patterns = [
            f"episode {episode}",
            f"episode{episode}",
            f"ep {episode}",
            f"ep{episode}",
            f"e{episode}",
            f"e{episode:02d}"
        ]
        
        for pattern in episode_patterns:
            if pattern in title_lower or pattern in url_lower:
                score += 1.5
                break
        
        # Bonus for transcript-related keywords
        transcript_keywords = ['transcript', 'script', 'dialogue', 'subtitles']
        for keyword in transcript_keywords:
            if keyword in title_lower or keyword in url_lower:
                score += 1.0  # Increased bonus for transcript keywords
                break
        
        # Wiki-specific bonuses
        if '/wiki/' in url_lower:
            # Bonus for wiki pages
            score += 0.5
            
            # Higher bonus for pages that look like episode pages
            wiki_episode_indicators = ['episode', 'transcript', 'script']
            for indicator in wiki_episode_indicators:
                if indicator in title_lower:
                    score += 0.5
                    break
        
        # Penalty for unrelated content
        negative_keywords = [
            'review', 'trailer', 'preview', 'summary', 'discussion', 'category', 
            'template', 'reaction', 'reacts', 'abridged', 'parody', 'dub', 'fandub'
        ]
        for keyword in negative_keywords:
            if keyword in title_lower:
                score -= 1.0  # Increased penalty for clearly unrelated content
        
        # Additional penalties for edit pages and special pages
        if 'action=edit' in url_lower or 'Special:' in url_lower:
            score -= 2.0
        
        return max(score, 0.0)
    
    def _find_episode_on_series_page(self, series_url, season, episode, source_config):
        """
        Navigate to a series page and find the specific episode.
        
        Args:
            series_url (str): URL of the series page
            season (int): Season number
            episode (int): Episode number
            source_config (dict): Source configuration
            
        Returns:
            str: Episode URL if found, None otherwise
        """
        try:
            response = self.session.get(series_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for episode links on the series page
            episode_links = soup.find_all('a', href=True)
            
            for link in episode_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Check if this link matches our target episode
                if self._is_target_episode_link(href, text, season, episode):
                    episode_url = href
                    if not episode_url.startswith('http'):
                        episode_url = source_config['base_url'] + episode_url
                    return episode_url
            
            logger.info(f"Episode S{season}E{episode} not found on series page")
            return None
            
        except Exception as e:
            logger.error(f"Failed to check series page {series_url}: {e}")
            return None
    
    def _is_target_episode_link(self, href, text, season, episode):
        """
        Check if a link points to the target episode.
        
        Args:
            href (str): Link href
            text (str): Link text
            season (int): Target season
            episode (int): Target episode
            
        Returns:
            bool: True if this appears to be the target episode
        """
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Check for season/episode patterns in URL
        season_patterns = [
            f'season-{season}',
            f'season{season}',
            f'/s{season}',
            f's{season:02d}'
        ]
        
        episode_patterns = [
            f'episode-{episode}',
            f'episode{episode}', 
            f'/e{episode}',
            f'e{episode:02d}'
        ]
        
        # Must have both season and episode indicators
        has_season = any(pattern in href_lower for pattern in season_patterns)
        has_episode = any(pattern in href_lower for pattern in episode_patterns)
        
        if has_season and has_episode:
            return True
        
        # Also check in the link text
        season_in_text = any(pattern.replace('-', ' ').replace('/', ' ') in text_lower for pattern in season_patterns)
        episode_in_text = any(pattern.replace('-', ' ').replace('/', ' ') in text_lower for pattern in episode_patterns)
        
        # More flexible text matching
        season_text_patterns = [f'season {season}', f's{season}', f's{season:02d}']
        episode_text_patterns = [f'episode {episode}', f'ep {episode}', f'e{episode}', f'e{episode:02d}']
        
        season_in_text = season_in_text or any(pattern in text_lower for pattern in season_text_patterns)
        episode_in_text = episode_in_text or any(pattern in text_lower for pattern in episode_text_patterns)
        
        return season_in_text and episode_in_text

    def _generate_search_query(self, source_name, show_name, season, episode):
        """
        Generate a search query tailored to the specific source.
        
        Args:
            source_name (str): Name of the source
            show_name (str): Show name
            season (int): Season number
            episode (int): Episode number
            
        Returns:
            str: Formatted search query
        """
        if source_name == 'transcripts_wiki':
            # For Fandom/wiki sources, search broadly for transcript content
            return f"{show_name} transcript"
        elif source_name == 'subslikescript':
            # For SubsLikeScript, include season/episode for more specific results
            return f"{show_name} season {season} episode {episode}"
        else:
            # Default format
            return f"{show_name} season {season} episode {episode}"
    
    def _get_search_params(self, source_config, search_query):
        """
        Get search parameters for the specific source.
        
        Args:
            source_config (dict): Source configuration
            search_query (str): Search query string
            
        Returns:
            dict: Search parameters
        """
        # Start with base search parameter
        if 'search_params' in source_config:
            # Use predefined search params (like for Fandom)
            params = source_config['search_params'].copy()
            params['query'] = search_query
        else:
            # Default search param format
            params = {'q': search_query}
        
        return params

    def _try_wiki_page_variants(self, base_url, source_config):
        """
        Try different variants of a wiki page URL to find actual content.
        
        Args:
            base_url (str): Base wiki page URL
            source_config (dict): Source configuration
            
        Returns:
            dict: Valid result if found, None otherwise
        """
        urls_to_try = [base_url]
        
        # Remove edit action if present
        if '?action=edit' in base_url:
            clean_url = base_url.replace('?action=edit', '')
            urls_to_try.append(clean_url)
        
        # Try with different URL variations
        if base_url.endswith('_transcript'):
            # Try without _transcript suffix
            base_without_transcript = base_url.replace('_transcript', '')
            urls_to_try.append(base_without_transcript)
            urls_to_try.append(f"{base_without_transcript}/Transcript")
            urls_to_try.append(f"{base_without_transcript}/Scripts")
        
        for url in urls_to_try:
            try:
                logger.debug(f"Trying wiki variant: {url}")
                result = self._fetch_and_parse(url, source_config)
                if result and result['content_length'] > 500:  # Ensure substantial content
                    result['url'] = url
                    logger.info(f"✅ Found valid wiki content at: {url}")
                    return result
            except Exception as e:
                logger.debug(f"Failed wiki variant {url}: {e}")
                continue
        
        logger.info(f"❌ No valid wiki content found for variants of: {base_url}")
        return None


# =============================================================================
# DEPRECATED MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚨 CRITICAL: main.py is DEPRECATED and should not be executed!")
    print("="*70)
    print()
    print("This monolithic implementation has been replaced by a modern")
    print("modular architecture for better maintainability and scalability.")
    print()
    print("✅ CORRECT USAGE:")
    print("   python main_refactored.py --help")
    print("   python main_refactored.py process-episode \"My Hero Academia\" 1 4")
    print()
    print("📖 DOCUMENTATION:")
    print("   README.md - Quick start guide")
    print("   docs/README_MODULAR.md - Detailed architecture guide")
    print()
    print("🏗️  NEW ARCHITECTURE:")
    print("   agents/        - Specialized processing agents")
    print("   core/          - Database and schemas")
    print("   utils/         - Utility functions")
    print("   media/         - Media processing")
    print()
    print("❌ This file (main.py) should only be used for:")
    print("   - Historical reference")
    print("   - Understanding the migration from monolithic to modular")
    print("   - Emergency fallback (not recommended)")
    print()
    print("🔄 MIGRATION ASSISTANCE:")
    print("   All functionality from this file is available in the new")
    print("   modular system with improved error handling, testing,")
    print("   and maintainability.")
    print()
    print("="*70)
    print("⚠️  Execution blocked to prevent accidental usage.")
    print("⚠️  Use main_refactored.py for current functionality.")
    print("="*70)
    
    # Optionally offer to redirect (commented out to prevent accidental execution)
    # import subprocess
    # print("\n🤔 Run main_refactored.py instead? (y/N): ", end="")
    # if input().lower().startswith('y'):
    #     subprocess.call([sys.executable, "main_refactored.py"] + sys.argv[1:])
    
    sys.exit(1)  # Exit with error code to indicate deprecated usage