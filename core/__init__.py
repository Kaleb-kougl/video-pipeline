"""
Core system components for the Anime Video Generator.

This package contains essential data structures, schemas, and registries
that provide the foundation for transcript processing and video generation.
"""

from .metadata_schemas import BaseMetadata, CharacterMetadata, InteractionMetadata
from .schemas import (
    BatchProcessingResult,
    Episode_Summary_Schema,
    EpisodeConfig,
    ExportFormat,
    ProcessingResult,
    ProcessingTask,
    ShowConfig,
    TaskStatus,
    TranscriptResult,
    VideoSpec,
    VideoStructureConfig,
    VisualTimingConfig,
)
from .show_registry import ShowMetadata, ShowRegistry, show_registry

__all__ = [
    "show_registry",
    "ShowRegistry",
    "ShowMetadata",
    "TaskStatus",
    "ProcessingTask",
    "Episode_Summary_Schema",
    "EpisodeConfig",
    "ShowConfig",
    "TranscriptResult",
    "ProcessingResult",
    "VideoStructureConfig",
    "VisualTimingConfig",
    "BatchProcessingResult",
    "ExportFormat",
    "VideoSpec",
    "BaseMetadata",
    "CharacterMetadata",
    "InteractionMetadata",
]
