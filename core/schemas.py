"""
Pydantic schemas for data validation and structure definition.
"""

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(Enum):
    """
    Enumeration for task status tracking.

    Represents the possible states of processing tasks
    for episode transcript discovery and analysis.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingTask:
    """
    Data class for tracking processing tasks.

    Represents a single episode processing task with status tracking
    and error information for batch processing operations.
    """

    task_id: str
    status: TaskStatus
    show_name: str
    season: int
    episode: int
    created_at: str
    completed_at: str | None = None
    error_message: str | None = None


class Episode_Summary_Schema(BaseModel):
    """
    Summary of a given show episode.

    Structured schema for episode summary data including plot points
    and transcript information for content generation.
    """

    show: str = Field(description="The title of the show")
    season: str = Field(description="The numerical season of the show")
    episode: str = Field(description="The numerical episode of the show")
    youtube_transcript: str = Field(description="Summary of the entire episode.")
    plot_points: list[str] = Field(
        description="Single sentence summaries of major plot points in this episode of the show"
    )


class EpisodeConfig(BaseModel):
    """
    Configuration for a specific episode.

    Contains episode-specific configuration parameters for
    transcript discovery and processing operations.
    """

    season: int = Field(description="Season number")
    episode: int = Field(description="Episode number")
    title: str | None = Field(description="Episode title", default=None)
    max_episodes: int | None = Field(description="Maximum episodes in season", default=None)


class ShowConfig(BaseModel):
    """
    Configuration for a show.

    Contains show-level configuration including season mappings
    and show-specific processing parameters.
    """

    name: str = Field(description="Show name")
    seasons: dict = Field(description="Season configurations")


class TranscriptResult(BaseModel):
    """
    Result from transcript discovery.

    Contains the discovered transcript content along with metadata
    about the source and quality assessment for validation.
    """

    transcript: str = Field(description="Full transcript text")
    title: str = Field(description="Page/episode title")
    url: str = Field(description="Source URL")
    source: str = Field(description="Source name (e.g., 'subslikescript')")
    episode_info: dict = Field(description="Extracted episode information")
    content_length: int = Field(description="Length of transcript content")
    quality_score: float = Field(description="Quality score from 0.0 to 1.0")
    found_via_search: bool = Field(
        description="Whether found via search or URL patterns", default=False
    )


class ProcessingResult(BaseModel):
    """
    Result from episode processing.

    Contains the outcome of episode processing operations including
    success status, processed data, and error information.
    """

    success: bool = Field(description="Whether processing was successful")
    job_id: str | None = Field(description="Job identifier", default=None)
    data: dict | None = Field(description="Processed episode data", default=None)
    error: str | None = Field(description="Error message if failed", default=None)
    source_info: TranscriptResult | None = Field(
        description="Information about transcript source", default=None
    )


class VideoStructureConfig(BaseModel):
    """
    Configuration for video timing structure.

    Defines the time allocation for different narrative components
    in generated video content for optimal pacing and engagement.
    """

    total_duration: int = Field(description="Total video duration in seconds")
    opening_hook: int = Field(description="Opening hook duration in seconds")
    character_arcs: int = Field(description="Character arcs duration in seconds")
    plot_progression: int = Field(description="Plot progression duration in seconds")
    relationship_evolution: int = Field(description="Relationship evolution duration in seconds")
    climax_resolution: int = Field(description="Climax resolution duration in seconds")


class VisualTimingConfig(BaseModel):
    """
    Configuration for visual concept timing.

    Defines timing parameters for visual elements in video generation
    including concept duration and transition timing.
    """

    concept_duration: float = Field(description="Seconds per visual concept")
    total_concepts: int = Field(description="Total number of visual concepts")
    transition_time: float = Field(default=0.5, description="Transition time between concepts")


class BatchProcessingResult(BaseModel):
    """
    Result from batch processing multiple episodes.

    Aggregated results from processing multiple episodes in a season
    including success/failure counts and per-episode details.
    """

    season: int = Field(description="Season number")
    total_episodes: int = Field(description="Total episodes processed")
    successful: int = Field(description="Number of successful episodes")
    failed: int = Field(description="Number of failed episodes")
    episodes: dict = Field(description="Per-episode results")


class ExportFormat(Enum):
    """
    Enumeration for video export formats.

    Represents the supported platform-specific video formats
    for content export and optimization.
    """

    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    TWITTER = "twitter"
    STANDARD = "standard"


class VideoSpec(BaseModel):
    """
    Specification for video export parameters.

    Defines technical specifications and constraints for platform-specific
    video exports including format, resolution, and file size limits.
    """

    format_type: ExportFormat = Field(description="Target export format")
    max_duration: int = Field(description="Maximum duration in seconds")
    aspect_ratio: str = Field(description="Video aspect ratio (e.g., '9:16', '16:9')")
    resolution: tuple = Field(description="Video resolution (width, height)")
    max_file_size: int = Field(description="Maximum file size in bytes")
