"""
Core system components for the Anime Video Generator.

This package contains essential data structures, schemas, and registries
that provide the foundation for transcript processing and video generation.
"""

from .show_registry import show_registry, ShowRegistry, ShowMetadata
from .schemas import (
    TaskStatus, ProcessingTask, Episode_Summary_Schema, EpisodeConfig,
    ShowConfig, TranscriptResult, ProcessingResult, VideoStructureConfig,
    VisualTimingConfig, BatchProcessingResult, ExportFormat, VideoSpec
)
from .metadata_schemas import BaseMetadata, CharacterMetadata, InteractionMetadata

__all__ = [
    'show_registry', 'ShowRegistry', 'ShowMetadata',
    'TaskStatus', 'ProcessingTask', 'Episode_Summary_Schema', 'EpisodeConfig',
    'ShowConfig', 'TranscriptResult', 'ProcessingResult', 'VideoStructureConfig',
    'VisualTimingConfig', 'BatchProcessingResult', 'ExportFormat', 'VideoSpec',
    'BaseMetadata', 'CharacterMetadata', 'InteractionMetadata'
]
