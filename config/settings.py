"""
Configuration settings module for the anime video generation system.

This module provides comprehensive configuration management using Pydantic
for validation and type safety. It includes settings for video generation,
database connections, AI models, media processing, and show-specific
episode configurations.

Classes:
    VideoConfig: Video generation configuration with advanced validation
    Settings: Main application settings with environment variable support
    EpisodeConfigs: Episode configurations and metadata for anime shows

Functions:
    get_settings: Get the global application settings instance
    update_settings: Update application settings dynamically

Global Variables:
    settings: Global Settings instance for application-wide configuration

The configuration system supports environment variables with the prefix
'ANIME_GEN_' and automatically loads from .env files when available.

Example Usage:
    from config.settings import get_settings
    
    settings = get_settings()
    print(f"Database: {settings.database_path}")
    print(f"Video FPS: {settings.video_fps}")
"""

import os
from typing import Dict, Any, Optional, ClassVar
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing_extensions import Self


class VideoConfig(BaseModel):
    """
    Video generation configuration with advanced Pydantic validation.
    Uses Pydantic's Field constraints and custom validators for robust configuration.
    """
    model_config = ConfigDict(
        frozen=True,  # Immutable config for thread safety
        validate_assignment=True,  # Validate on assignment changes
        str_strip_whitespace=True,  # Auto-strip whitespace
        extra='forbid'  # Prevent accidental config additions
    )
    
    default_duration_minutes: int = Field(default=5, description="Default video duration in minutes")
    min_duration_minutes: int = Field(default=5, description="Minimum allowed video duration")
    max_duration_minutes: int = Field(default=15, description="Maximum allowed video duration")
    
    # Timing ratios (percentages of total duration)
    opening_hook_ratio: float = Field(default=0.10, description="Opening hook percentage of total")
    character_arcs_ratio: float = Field(default=0.30, description="Character arcs percentage of total")
    plot_progression_ratio: float = Field(default=0.40, description="Plot progression percentage of total")
    relationship_evolution_ratio: float = Field(default=0.10, description="Relationship evolution percentage")
    climax_resolution_ratio: float = Field(default=0.10, description="Climax resolution percentage")
    
    # Visual timing configuration with validation
    min_concept_duration: float = Field(
        default=3.0, 
        gt=0.5,  # Must be greater than 0.5 seconds
        le=5.0,  # Cannot exceed 5 seconds minimum
        description="Minimum seconds per visual concept"
    )
    max_concept_duration: float = Field(
        default=15.0, 
        ge=8.0,   # Must be at least 8 seconds
        le=30.0,  # Cannot exceed 30 seconds maximum
        description="Maximum seconds per visual concept"
    )
    
    @field_validator('max_concept_duration')
    @classmethod
    def validate_max_greater_than_min(cls, v, info):
        """Ensure max_concept_duration > min_concept_duration"""
        if 'min_concept_duration' in info.data:
            min_duration = info.data['min_concept_duration']
            if v <= min_duration:
                raise ValueError(
                    f'max_concept_duration ({v}) must be greater than min_concept_duration ({min_duration})'
                )
        return v


class Settings(BaseModel):
    """Application settings with environment variable support."""
    
    # Database settings
    database_path: str = Field(default="data/databases/video_generator.db", description="Path to SQLite database")
    
    # Media settings
    output_directory: str = Field(default="data/episode_data", description="Output directory for generated content")
    image_quality: str = Field(default="high", description="Image generation quality")
    video_fps: int = Field(default=24, description="Video frames per second")
    audio_codec: str = Field(default="aac", description="Audio codec for video generation")
    
    # AI Model settings
    gemini_api_key: Optional[str] = Field(default=None, description="Gemini AI API key")
    model_name: str = Field(default="gemini-2.0-flash", description="Default AI model name")
    model_provider: str = Field(default="google_genai", description="AI model provider")
    
    # Text-to-Speech settings
    tts_model: str = Field(default="gemini-2.5-flash-preview-tts", description="TTS model name")
    tts_voice: str = Field(default="Kore", description="TTS voice name")
    audio_sample_rate: int = Field(default=24000, description="Audio sample rate")
    audio_channels: int = Field(default=1, description="Audio channels (1=mono, 2=stereo)")
    
    # Image generation settings
    image_model: str = Field(default="gemini-2.0-flash-preview-image-generation", description="Image generation model")
    image_format: str = Field(default="png", description="Image file format")
    
    # Web scraping settings
    request_timeout: int = Field(default=10, description="HTTP request timeout in seconds")
    retry_count: int = Field(default=3, description="Number of retry attempts")
    delay_range_min: int = Field(default=1, description="Minimum delay between requests")
    delay_range_max: int = Field(default=3, description="Maximum delay between requests")
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        description="User agent for web requests"
    )
    
    # Processing settings
    min_transcript_length: int = Field(default=500, description="Minimum transcript length for validation")
    max_batch_size: int = Field(default=10, description="Maximum episodes to process in batch")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    
    # Video configuration
    video_config: VideoConfig = Field(default_factory=VideoConfig, description="Video generation configuration")
    
    class Config:
        env_file = ".env"
        env_prefix = "ANIME_GEN_"
        case_sensitive = False


class EpisodeConfigs:
    """
    Episode configurations and metadata for different anime shows.
    
    This class provides centralized configuration for anime shows including
    episode counts, titles, and metadata. It supports multiple seasons per
    show and includes specific episode information where available.
    
    Attributes:
        DEFAULT_CONFIGS (dict): Dictionary containing show configurations
                               with season and episode information
    
    Methods:
        get_show_config: Get configuration for a specific show
        get_episode_config: Get configuration for a specific episode
        get_season_episodes: Get the number of episodes in a season
    
    Example Usage:
        >>> config = EpisodeConfigs.get_episode_config("My Hero Academia", 1, 1)
        >>> print(config['title'])
        Izuku_Midoriya_Origin
        
        >>> episode_count = EpisodeConfigs.get_season_episodes("My Hero Academia", 1)
        >>> print(f"Season 1 has {episode_count} episodes")
        Season 1 has 13 episodes
    """
    
    DEFAULT_CONFIGS = {
        "My Hero Academia": {
            "seasons": {
                1: {"episodes": 13, "titles": {
                    1: "Izuku_Midoriya_Origin",
                    2: "What_It_Takes_to_Be_a_Hero", 
                    3: "Roaring_Muscles",
                    4: "Start_Line",
                    5: "What_I_Can_Do_for_Now",
                    6: "Rage_You_Damn_Nerd",
                    7: "Deku_vs_Kacchan",
                    8: "Bakugo's_Start_Line",
                    9: "Yeah_Just_Do_Your_Best_Ida",
                    10: "Encounter_with_the_Unknown",
                    11: "Game_Over",
                    12: "All_Might",
                    13: "In_Each_of_Our_Hearts"
                }},
                2: {"episodes": 25, "titles": {}},
                3: {"episodes": 25, "titles": {}},
                4: {"episodes": 25, "titles": {}},
                5: {"episodes": 25, "titles": {}},
                6: {"episodes": 25, "titles": {}},
                7: {"episodes": 21, "titles": {}}
            }
        },
        "Attack on Titan": {
            "seasons": {
                1: {"episodes": 25, "titles": {}},
                2: {"episodes": 12, "titles": {}},
                3: {"episodes": 22, "titles": {}},
                4: {"episodes": 28, "titles": {}}
            }
        },
        "Frieren: Beyond Journey's End": {
            "seasons": {
                1: {"episodes": 28, "titles": {}}
            }
        }
    }
    
    @classmethod
    def get_show_config(cls, show_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific anime show.
        
        Args:
            show_name (str): The name of the anime show (case-sensitive)
            
        Returns:
            Optional[Dict[str, Any]]: Show configuration including seasons data,
                                     or None if show not found
            
        Example:
            >>> config = EpisodeConfigs.get_show_config("My Hero Academia")
            >>> print(config['seasons'].keys())
            dict_keys([1, 2, 3, 4, 5, 6, 7])
        """
        return cls.DEFAULT_CONFIGS.get(show_name)
    
    @classmethod
    def get_episode_config(cls, show_name: str, season: int, episode: int) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific episode.
        
        Args:
            show_name (str): The name of the anime show
            season (int): Season number (1-based)
            episode (int): Episode number (1-based)
            
        Returns:
            Optional[Dict[str, Any]]: Episode configuration containing:
                - show: Show name
                - season: Season number
                - episode: Episode number  
                - title: Episode title (if available)
                - max_episodes: Total episodes in the season
                Returns None if episode not found
        
        Example:
            >>> config = EpisodeConfigs.get_episode_config("My Hero Academia", 1, 1)
            >>> print(f"Title: {config['title']}")
            Title: Izuku_Midoriya_Origin
        """
        show_config = cls.get_show_config(show_name)
        if not show_config:
            return None
        
        season_config = show_config.get("seasons", {}).get(season)
        if not season_config:
            return None
        
        return {
            "show": show_name,
            "season": season,
            "episode": episode,
            "title": season_config.get("titles", {}).get(episode),
            "max_episodes": season_config.get("episodes", 13)
        }
    
    @classmethod
    def get_season_episodes(cls, show_name: str, season: int) -> Optional[int]:
        """
        Get the total number of episodes in a specific season.
        
        Args:
            show_name (str): The name of the anime show
            season (int): Season number (1-based)
            
        Returns:
            Optional[int]: Number of episodes in the season, or None if
                          season not found
        
        Example:
            >>> episode_count = EpisodeConfigs.get_season_episodes("My Hero Academia", 1)
            >>> print(f"Season 1 has {episode_count} episodes")
            Season 1 has 13 episodes
        """
        episode_config = cls.get_episode_config(show_name, season, 1)
        if episode_config:
            return episode_config["max_episodes"]
        return None


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global application settings instance.
    
    Returns:
        Settings: The global Settings instance with current configuration
        
    Example:
        >>> settings = get_settings()
        >>> print(f"Database path: {settings.database_path}")
        Database path: data/databases/video_generator.db
    """
    return settings


def update_settings(**kwargs) -> None:
    """
    Update application settings dynamically.
    
    Args:
        **kwargs: Keyword arguments representing setting names and values
                 to update. Only existing settings attributes will be updated.
                 
    Raises:
        AttributeError: Implicitly raised if trying to set non-existent attributes
        
    Example:
        >>> update_settings(log_level="DEBUG", video_fps=30)
        >>> settings = get_settings()
        >>> print(settings.log_level)
        DEBUG
        
    Note:
        Only updates settings that already exist as attributes on the
        Settings class. Invalid attribute names are silently ignored.
    """
    global settings
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
