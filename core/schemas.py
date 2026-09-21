"""
Pydantic schemas for data validation and structure definition.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T")


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


class EpisodeStatus(Enum):
    """
    Where one episode stands in a season run.

    This is the state machine the ``episodes.status`` column records. It is
    deliberately *not* :class:`TaskStatus`: that enum describes an in-memory
    task object, while these four values are persisted and are what a resumed
    run reads to decide whether an episode still needs its paid work done.

    Only :data:`SUCCEEDED` means "do not do this again". :data:`IN_PROGRESS` is
    what a crashed run leaves behind - the process died between starting the
    episode and recording an outcome, so nothing may be assumed about how far
    it got, and a resume retries it.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunStatus(Enum):
    """
    Where one season run stands.

    :data:`RUNNING` is also what a crashed run is left as - a process that dies
    cannot write its own epitaph, so "running" on a run nothing is working on
    is exactly the signal ``--resume`` looks for.
    """

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class EpisodeOutcome(BaseModel):
    """What happened to one episode inside a season run."""

    episode: int = Field(description="Episode number")
    status: EpisodeStatus = Field(description="Terminal state of this episode in this run")
    skipped: bool = Field(
        default=False,
        description="True when a resumed run found this episode already succeeded and did no work",
    )
    attempts: int = Field(default=0, description="Total recorded attempts across all runs")
    error: str | None = Field(default=None, description="Failure reason, when it failed")


class SeasonRunReport(BaseModel):
    """
    The outcome of one (possibly resumed) season batch.

    ``skipped`` is the number the whole feature exists for: episodes a resumed
    run recognised as already finished and did not pay for again.
    """

    run_id: str = Field(description="Identity of this run; a resumed run reuses it")
    show: str = Field(description="Show name")
    season: int = Field(description="Season number")
    resumed: bool = Field(default=False, description="Whether this run continued an earlier one")
    status: RunStatus = Field(description="Terminal state of the run")
    requested: int = Field(description="Episodes in the requested range")
    succeeded: int = Field(description="Episodes that finished successfully in this run")
    failed: int = Field(description="Episodes that failed in this run")
    skipped: int = Field(default=0, description="Episodes already complete, so not re-run")
    episodes: list[EpisodeOutcome] = Field(
        default_factory=list, description="Per-episode outcomes in requested order"
    )


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
    # No `max_length` here on purpose. A schema constraint would be sent to the
    # provider as `maxItems` and enforced by pydantic on the way back, which
    # turns a merely verbose model response into a hard ValidationError that
    # fails the whole episode -- a worse outcome than the cost it would prevent,
    # and an unevaluated change to the prompt contract besides. The list is
    # bounded where it is spent instead: see `enforce_scene_cap` below, applied
    # in `WorkflowOrchestrator.generate_all_media`. The full list is still
    # persisted; only the number of *images* is capped.
    plot_points: list[str] = Field(
        description="Single sentence summaries of major plot points in this episode of the show"
    )


def enforce_scene_cap(scenes: Sequence[T], limit: int, *, context: str) -> list[T]:
    """
    Bound a model-decided scene list to at most ``limit`` entries.

    Every scene becomes one paid image call, and the scene count is decided by a
    nondeterministic model response, so this is the one place that stops a
    single Gemini reply from setting the image bill for a video. Callers must
    use the returned list for *everything* downstream -- prompts, durations and
    the sentence list handed to ``mp4_file_enhanced`` -- because the encoder
    looks images up by index and zips sentences against durations; capping one
    of the three and not the others produces a missing-file crash or a silently
    mistimed video.

    Truncation is plain "keep the first ``limit``". It is order-preserving,
    deterministic and trivially auditable against the log line. Its known
    weakness is that it drops the end of the story, which is why the default cap
    (``VideoConfig.max_scenes``) is set high enough to bind only on a runaway
    response rather than on ordinary output: a sampler that kept the narrative
    span would trade that rare, loudly-logged case for permanent index
    arithmetic on every run.

    Dropping scenes is never silent -- a truncation logs at WARNING with both
    the produced and the kept count.

    Args:
        scenes: The model-produced items, one per intended image.
        limit: Maximum number to keep; must be at least 1.
        context: Human-readable identifier for the log line (e.g. an episode ref).

    Returns:
        list: ``scenes`` unchanged when it already fits, otherwise its first
        ``limit`` entries.

    Raises:
        ValueError: If ``limit`` is less than 1.
    """
    if limit < 1:
        raise ValueError(f"scene cap must be at least 1, got {limit}")

    produced = len(scenes)
    if produced <= limit:
        return list(scenes)

    logger.warning(
        "Scene cap applied for %s: model produced %d scenes, generating %d "
        "(dropped %d). Each scene is one paid image call; raise "
        "video_config.max_scenes to keep more.",
        context,
        produced,
        limit,
        produced - limit,
    )
    return list(scenes[:limit])


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
