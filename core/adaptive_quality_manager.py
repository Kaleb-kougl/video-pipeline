#!/usr/bin/env python3
"""
Adaptive Quality Manager - Phase 2 Quality Enhancement

Dynamically adjusts quality settings based on context, system resources,
deadline pressure, and performance optimization feedback to maintain
optimal balance between quality and performance.
"""

import copy
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

import psutil


@dataclass
class QualityProfile:
    """Quality profile configuration for video generation."""

    name: str
    image_quality: float  # 0.0 to 1.0
    video_resolution: tuple[int, int]  # (width, height)
    compression_level: int  # 1-9 for PNG, 0-100 for JPEG
    processing_priority: str  # 'speed', 'balanced', 'quality'
    max_concurrent_jobs: int
    memory_limit_mb: int


class SystemResources(NamedTuple):
    """Current system resource availability."""

    memory_gb: float
    cpu_cores: int
    cpu_usage_percent: float
    available_disk_gb: float


class AdaptiveQualityManager:
    """
    Dynamic quality adjustment based on context, resources, and deadlines.

    This class provides:
    - Context-aware quality profile selection
    - System resource monitoring and adaptation
    - Deadline pressure calculation and quality adjustment
    - Performance optimization based on historical data
    - Memory constraint enforcement (<4GB peak usage)
    """

    def __init__(self) -> None:
        """Initialize the Adaptive Quality Manager with default profiles."""
        self.quality_profiles = {
            "draft": QualityProfile(
                name="draft",
                image_quality=0.6,
                video_resolution=(1280, 720),
                compression_level=70,
                processing_priority="speed",
                max_concurrent_jobs=6,
                memory_limit_mb=1024,
            ),
            "preview": QualityProfile(
                name="preview",
                image_quality=0.8,
                video_resolution=(1920, 1080),
                compression_level=85,
                processing_priority="balanced",
                max_concurrent_jobs=4,
                memory_limit_mb=2048,
            ),
            "production": QualityProfile(
                name="production",
                image_quality=1.0,
                video_resolution=(1920, 1080),
                compression_level=95,
                processing_priority="quality",
                max_concurrent_jobs=2,
                memory_limit_mb=4096,
            ),
        }

        self.quality_history: list[dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)

        self.logger.info("Adaptive Quality Manager initialized with default profiles")

    async def select_quality_profile(
        self,
        context: str,
        deadline: datetime | None = None,
        target_duration: int | None = None,
        use_optimization: bool = False,
    ) -> QualityProfile:
        """
        Select optimal quality profile based on context and constraints.

        Args:
            context: Quality context ('draft', 'preview', 'production')
            deadline: Optional deadline for completion
            target_duration: Optional target video duration
            use_optimization: Whether to use historical optimization data

        Returns:
            Optimized quality profile for the given constraints

        Raises:
            KeyError: If context is not recognized
        """
        if context not in self.quality_profiles:
            raise KeyError(f"Unknown quality context: {context}")

        self.logger.info(f"Selecting quality profile for context: {context}")

        # Get current system resources
        system_resources = self._get_system_resources()

        # Calculate time pressure from deadline
        time_pressure = self._calculate_time_pressure(deadline) if deadline else 0.0

        # Start with base profile for context
        base_profile = self.quality_profiles[context]

        # Apply resource and time-based adjustments
        adjusted_profile = self._adjust_profile_for_resources(
            copy.deepcopy(base_profile), system_resources, time_pressure
        )

        # Apply memory constraints (<4GB enforcement)
        validated_profile = self._validate_memory_constraints(adjusted_profile)

        # Apply historical optimization if requested
        if use_optimization and self.quality_history:
            optimized_profile = self._apply_historical_optimization(validated_profile)
        else:
            optimized_profile = validated_profile

        self.logger.info(
            f"Selected profile: {optimized_profile.name} "
            f"(quality: {optimized_profile.image_quality:.2f}, "
            f"memory: {optimized_profile.memory_limit_mb}MB, "
            f"time_pressure: {time_pressure:.2f})"
        )

        return optimized_profile

    def _get_system_resources(self) -> SystemResources:
        """
        Get current system resource availability using psutil.

        Returns:
            SystemResources with current memory, CPU, and disk availability
        """
        try:
            memory = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
            cpu_usage = psutil.cpu_percent(interval=0.1)  # Quick sample
            disk = psutil.disk_usage("/")

            resources = SystemResources(
                memory_gb=memory.available / (1024**3),
                cpu_cores=cpu_count,
                cpu_usage_percent=cpu_usage,
                available_disk_gb=disk.free / (1024**3),
            )

            self.logger.debug(
                f"System resources: {resources.memory_gb:.1f}GB memory, "
                f"{resources.cpu_cores} cores, {resources.cpu_usage_percent:.1f}% CPU"
            )

            return resources

        except Exception as e:
            self.logger.error(f"Error getting system resources: {e}")
            # Return conservative fallback values
            return SystemResources(
                memory_gb=4.0,
                cpu_cores=2,
                cpu_usage_percent=50.0,
                available_disk_gb=10.0,
            )

    def _calculate_time_pressure(self, deadline: datetime | None) -> float:
        """
        Calculate time pressure from deadline.

        Args:
            deadline: Target completion deadline

        Returns:
            Time pressure score (0.0-1.0), where 1.0 is maximum pressure
        """
        if not deadline:
            return 0.0

        try:
            now = datetime.now()
            time_remaining = deadline - now

            # If deadline has passed, maximum pressure
            if time_remaining.total_seconds() <= 0:
                return 1.0

            # Calculate pressure based on time remaining
            # 0-1 hour: high pressure (0.8-1.0)
            # 1-6 hours: medium pressure (0.4-0.8)
            # 6+ hours: low pressure (0.0-0.4)
            hours_remaining = time_remaining.total_seconds() / 3600

            if hours_remaining <= 1:
                pressure = 0.8 + (1 - hours_remaining) * 0.2
            elif hours_remaining <= 6:
                pressure = 0.4 + (6 - hours_remaining) / 5 * 0.4
            else:
                pressure = max(0.0, 0.4 - (hours_remaining - 6) / 24 * 0.4)

            return max(0.0, min(1.0, pressure))

        except Exception as e:
            self.logger.error(f"Error calculating time pressure: {e}")
            return 0.0

    def _adjust_profile_for_resources(
        self, profile: QualityProfile, resources: SystemResources, time_pressure: float
    ) -> QualityProfile:
        """
        Adjust quality profile based on system resources and time pressure.

        Args:
            profile: Base quality profile to adjust
            resources: Current system resources
            time_pressure: Time pressure score (0.0-1.0)

        Returns:
            Adjusted quality profile
        """
        try:
            # Memory-based adjustments
            if resources.memory_gb < 4.0:
                # Reduce quality for low memory systems
                profile.image_quality *= 0.8
                profile.memory_limit_mb = min(
                    profile.memory_limit_mb, int(resources.memory_gb * 800)
                )  # Use 80% of available memory
                profile.max_concurrent_jobs = max(1, profile.max_concurrent_jobs // 2)

            if resources.memory_gb < 2.0:
                # Severe memory constraints
                profile.image_quality = min(profile.image_quality, 0.6)
                profile.video_resolution = (1280, 720)  # Reduce resolution
                profile.max_concurrent_jobs = 1

            # CPU-based adjustments
            if resources.cpu_cores <= 2:
                # Low CPU cores - limit concurrency strictly
                profile.max_concurrent_jobs = min(profile.max_concurrent_jobs, resources.cpu_cores)

            if resources.cpu_usage_percent > 80:
                # High CPU usage - further reduce concurrent jobs
                profile.max_concurrent_jobs = max(1, profile.max_concurrent_jobs - 1)

            # Time pressure adjustments (respect resource constraints)
            if time_pressure > 0.7:
                # High time pressure - prioritize speed
                profile.processing_priority = "speed"
                profile.compression_level = max(60, profile.compression_level - 20)
                # Only increase concurrent jobs if resources allow
                max_allowed_jobs = min(resources.cpu_cores, 8)
                if (
                    profile.max_concurrent_jobs < max_allowed_jobs
                    and resources.cpu_usage_percent < 70
                ):
                    profile.max_concurrent_jobs = min(
                        max_allowed_jobs, profile.max_concurrent_jobs + 1
                    )

            elif time_pressure > 0.4:
                # Medium time pressure - balanced approach
                profile.processing_priority = "balanced"

            # Disk space adjustments
            if resources.available_disk_gb < 10.0:
                # Low disk space - increase compression
                profile.compression_level = max(50, profile.compression_level - 30)

            self.logger.debug(
                f"Adjusted profile for resources: memory={resources.memory_gb:.1f}GB, "
                f"pressure={time_pressure:.2f}"
            )

            return profile

        except Exception as e:
            self.logger.error(f"Error adjusting profile for resources: {e}")
            return profile  # Return original on error

    def _validate_memory_constraints(self, profile: QualityProfile) -> QualityProfile:
        """
        Validate and enforce memory constraints (<4GB peak usage).

        Args:
            profile: Quality profile to validate

        Returns:
            Profile with enforced memory constraints
        """
        # Enforce 4GB memory limit
        if profile.memory_limit_mb > 4096:
            self.logger.warning(
                f"Memory limit {profile.memory_limit_mb}MB exceeds 4GB constraint, "
                f"reducing to 4096MB"
            )
            profile.memory_limit_mb = 4096

            # Adjust other settings proportionally
            if profile.memory_limit_mb == 4096:
                profile.image_quality = min(profile.image_quality, 0.95)
                profile.max_concurrent_jobs = min(profile.max_concurrent_jobs, 4)

        return profile

    def _apply_historical_optimization(self, profile: QualityProfile) -> QualityProfile:
        """
        Apply optimization based on historical performance data.

        Args:
            profile: Base profile to optimize

        Returns:
            Optimized profile based on performance history
        """
        if not self.quality_history:
            return profile

        try:
            # Analyze recent performance history (last 10 entries)
            recent_history = self.quality_history[-10:]

            # Find successful configurations
            successful_configs = [
                entry
                for entry in recent_history
                if entry.get("processing_metrics", {}).get("success", False)
            ]

            if successful_configs:
                # Calculate average successful memory usage
                avg_memory = sum(
                    config["processing_metrics"]["memory_usage_mb"] for config in successful_configs
                ) / len(successful_configs)

                # Adjust memory limit based on successful usage patterns
                if avg_memory < profile.memory_limit_mb * 0.7:
                    # Reduce memory limit if consistently using less
                    profile.memory_limit_mb = int(avg_memory * 1.2)

                # Find failed configurations to avoid
                failed_configs = [
                    entry
                    for entry in recent_history
                    if not entry.get("processing_metrics", {}).get("success", True)
                ]

                if failed_configs:
                    # Reduce settings that commonly fail
                    avg_failed_memory = sum(
                        config["processing_metrics"].get("memory_usage_mb", 0)
                        for config in failed_configs
                    ) / len(failed_configs)

                    if avg_failed_memory > 4000:  # Failed due to memory
                        profile.memory_limit_mb = min(profile.memory_limit_mb, 3000)
                        profile.max_concurrent_jobs = max(1, profile.max_concurrent_jobs - 1)

            return profile

        except Exception as e:
            self.logger.error(f"Error applying historical optimization: {e}")
            return profile

    def record_quality_metrics(
        self, profile: QualityProfile, processing_metrics: dict[str, Any]
    ) -> None:
        """
        Record quality metrics for future optimization.

        Args:
            profile: Quality profile that was used
            processing_metrics: Performance metrics from processing
        """
        try:
            entry = {
                "timestamp": datetime.now(),
                "profile_name": profile.name,
                "profile_settings": {
                    "image_quality": profile.image_quality,
                    "memory_limit_mb": profile.memory_limit_mb,
                    "max_concurrent_jobs": profile.max_concurrent_jobs,
                    "processing_priority": profile.processing_priority,
                },
                "processing_metrics": processing_metrics,
            }

            self.quality_history.append(entry)

            # Keep only recent history (last 100 entries)
            if len(self.quality_history) > 100:
                self.quality_history = self.quality_history[-100:]

            self.logger.debug(
                f"Recorded quality metrics for {profile.name}: "
                f"success={processing_metrics.get('success', 'unknown')}"
            )

        except Exception as e:
            self.logger.error(f"Error recording quality metrics: {e}")
