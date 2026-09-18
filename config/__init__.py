"""
Configuration management for the anime video generation system.

This package provides centralized configuration management including:
    - Application settings with environment variable support
    - Video generation configuration with validation
    - Episode-specific configurations for different anime shows
    - Database and media processing settings
    - AI model and API configuration

Modules:
    settings: Core configuration classes and settings management

Classes (from settings module):
    Settings: Main application configuration with Pydantic validation
    VideoConfig: Video generation specific configuration
    EpisodeConfigs: Episode configurations for various anime shows

Functions (from settings module):
    get_settings: Get the global application settings instance
    update_settings: Update application settings dynamically

Example Usage:
    from config import get_settings, VideoConfig
    
    settings = get_settings()
    video_config = settings.video_config
    print(f"Default duration: {video_config.default_duration_minutes} minutes")
"""

# Configuration management imports
from .settings import (
    Settings,
    VideoConfig, 
    EpisodeConfigs,
    get_settings,
    update_settings,
    settings
)

__all__ = [
    'Settings',
    'VideoConfig',
    'EpisodeConfigs', 
    'get_settings',
    'update_settings',
    'settings'
]
