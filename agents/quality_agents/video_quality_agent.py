"""
Video Quality Agent - Validates video generation quality and output.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VideoQualityReport:
    """Quality report for video generation output."""

    overall_score: float
    technical_quality: float
    content_accuracy: float
    visual_coherence: float
    audio_quality: float
    file_integrity: float
    timing_accuracy: float
    issues: list[str]
    recommendations: list[str]

    @property
    def is_acceptable(self) -> bool:
        """Returns True if video meets minimum quality standards."""
        return self.overall_score >= 0.6


class VideoQualityAgent:
    """Agent responsible for validating video generation quality."""

    def __init__(self):
        """Initialize the video quality agent."""
        self.supported_formats = [".mp4", ".avi", ".mov", ".mkv"]
        self.min_duration = 10  # seconds
        self.max_duration = 1800  # 30 minutes
        self.min_resolution = (480, 360)  # minimum acceptable resolution
        self.target_fps = 24

    def validate_video_output(
        self, video_data: dict, content_source: dict = None
    ) -> VideoQualityReport:
        """
        Validate the quality of generated video output.

        Args:
            video_data: Dictionary containing video file info and metadata
            content_source: Original content used for generation (for comparison)

        Returns:
            VideoQualityReport: Detailed quality assessment
        """
        issues = []
        recommendations = []

        video_path = video_data.get("file_path", "")
        logger.info(f"Validating video output: {video_path}")

        # 1. Technical quality validation
        technical_score = self._assess_technical_quality(video_data, issues, recommendations)

        # 2. Content accuracy validation
        content_score = self._assess_content_accuracy(
            video_data, content_source, issues, recommendations
        )

        # 3. Visual coherence validation
        visual_score = self._assess_visual_coherence(video_data, issues, recommendations)

        # 4. Audio quality validation
        audio_score = self._assess_audio_quality(video_data, issues, recommendations)

        # 5. File integrity validation
        integrity_score = self._assess_file_integrity(video_data, issues, recommendations)

        # 6. Timing accuracy validation
        timing_score = self._assess_timing_accuracy(
            video_data, content_source, issues, recommendations
        )

        # Calculate overall score
        weights = {
            "technical": 0.25,
            "content": 0.20,
            "visual": 0.20,
            "audio": 0.15,
            "integrity": 0.10,
            "timing": 0.10,
        }

        overall_score = (
            technical_score * weights["technical"]
            + content_score * weights["content"]
            + visual_score * weights["visual"]
            + audio_score * weights["audio"]
            + integrity_score * weights["integrity"]
            + timing_score * weights["timing"]
        )

        return VideoQualityReport(
            overall_score=overall_score,
            technical_quality=technical_score,
            content_accuracy=content_score,
            visual_coherence=visual_score,
            audio_quality=audio_score,
            file_integrity=integrity_score,
            timing_accuracy=timing_score,
            issues=issues,
            recommendations=recommendations,
        )

    def _assess_technical_quality(
        self, video_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess technical quality of the video file."""
        score = 1.0

        file_path = video_data.get("file_path", "")

        # Check file existence
        if not file_path or not os.path.exists(file_path):
            score = 0.0
            issues.append("Video file not found or path invalid")
            recommendations.append("Verify video generation completed successfully")
            return score

        # Check file format
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_formats:
            score -= 0.2
            issues.append(f"Unsupported video format: {file_ext}")
            recommendations.append(
                f"Convert to supported format: {', '.join(self.supported_formats)}"
            )

        # Check file size
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 1024 * 1024:  # Less than 1MB
                score -= 0.3
                issues.append(f"Video file very small: {file_size / 1024:.1f} KB")
                recommendations.append("Check if video generation completed properly")
            elif file_size > 500 * 1024 * 1024:  # More than 500MB
                score -= 0.1
                issues.append(f"Video file very large: {file_size / (1024 * 1024):.1f} MB")
                recommendations.append("Consider optimizing video compression")
        except OSError:
            score -= 0.2
            issues.append("Cannot access video file size")
            recommendations.append("Check file permissions and integrity")

        # Check video metadata if available
        metadata = video_data.get("metadata", {})

        # Resolution check
        width = metadata.get("width", 0)
        height = metadata.get("height", 0)
        if width and height:
            if width < self.min_resolution[0] or height < self.min_resolution[1]:
                score -= 0.2
                issues.append(f"Low resolution: {width}x{height}")
                recommendations.append(
                    f"Increase resolution to at least {self.min_resolution[0]}x{self.min_resolution[1]}"
                )

        # Frame rate check
        fps = metadata.get("fps", 0)
        if fps and fps < 15:
            score -= 0.1
            issues.append(f"Low frame rate: {fps} fps")
            recommendations.append("Increase frame rate for smoother playback")
        elif fps and fps > 60:
            score -= 0.05
            issues.append(f"Very high frame rate: {fps} fps")
            recommendations.append("Consider reducing frame rate to save file size")

        # Duration check
        duration = metadata.get("duration", 0)
        if duration:
            if duration < self.min_duration:
                score -= 0.2
                issues.append(f"Video too short: {duration}s")
                recommendations.append("Ensure adequate content length")
            elif duration > self.max_duration:
                score -= 0.1
                issues.append(f"Video very long: {duration}s")
                recommendations.append("Consider breaking into shorter segments")

        return max(0.0, score)

    def _assess_content_accuracy(
        self, video_data: dict, content_source: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess how accurately the video represents the source content."""
        score = 1.0

        if not content_source:
            issues.append("No source content provided for comparison")
            recommendations.append("Provide source content for accuracy validation")
            return 0.7  # Neutral score when no comparison possible

        # Check scene count accuracy
        generated_scenes = video_data.get("scenes", [])
        source_scenes = content_source.get("scenes", [])

        if source_scenes and generated_scenes:
            scene_diff = abs(len(generated_scenes) - len(source_scenes))
            if scene_diff > len(source_scenes) * 0.3:  # More than 30% difference
                score -= 0.2
                issues.append(
                    f"Scene count mismatch: generated {len(generated_scenes)}, expected ~{len(source_scenes)}"
                )
                recommendations.append("Adjust scene generation to match source content")

        # Check character representation
        source_characters = set()
        if "characters" in content_source:
            for char in content_source["characters"]:
                if isinstance(char, dict):
                    source_characters.add(char.get("name", ""))
                elif isinstance(char, str):
                    source_characters.add(char)

        generated_characters = set()
        video_metadata = video_data.get("metadata", {})
        if "characters" in video_metadata:
            generated_characters.update(video_metadata["characters"])

        if source_characters:
            missing_chars = source_characters - generated_characters
            if missing_chars:
                score -= 0.1 * min(len(missing_chars), 3) / 3  # Cap penalty
                issues.append(f"Missing characters in video: {', '.join(list(missing_chars)[:3])}")
                recommendations.append("Ensure all main characters are represented visually")

        # Check dialogue inclusion
        source_dialogue_count = len(content_source.get("dialogue", []))
        video_dialogue_count = video_metadata.get("dialogue_scenes", 0)

        if source_dialogue_count > 0:
            dialogue_ratio = (
                video_dialogue_count / source_dialogue_count if source_dialogue_count else 0
            )
            if dialogue_ratio < 0.5:
                score -= 0.15
                issues.append("Insufficient dialogue representation in video")
                recommendations.append("Include more dialogue scenes from source content")

        return max(0.0, score)

    def _assess_visual_coherence(
        self, video_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess visual coherence and consistency of the video."""
        score = 1.0

        metadata = video_data.get("metadata", {})
        scenes = video_data.get("scenes", [])

        # Check visual consistency between scenes
        if len(scenes) > 1:
            visual_inconsistencies = self._detect_visual_inconsistencies(scenes)
            if visual_inconsistencies:
                score -= 0.1 * min(len(visual_inconsistencies), 5) / 5
                issues.extend(visual_inconsistencies[:3])
                recommendations.append("Improve visual consistency between scenes")

        # Check transition quality
        transitions = metadata.get("transitions", [])
        if scenes and len(transitions) < len(scenes) - 1:
            score -= 0.1
            issues.append("Missing transitions between scenes")
            recommendations.append("Add smooth transitions between all scenes")

        # Check visual effects quality
        effects_quality = metadata.get("effects_quality", 0)
        if effects_quality and effects_quality < 0.5:
            score -= 0.2
            issues.append("Poor visual effects quality")
            recommendations.append("Improve visual effects generation or reduce complexity")

        # Check color consistency
        color_profile = metadata.get("color_profile")
        if color_profile and color_profile.get("consistency_score", 1.0) < 0.6:
            score -= 0.1
            issues.append("Inconsistent color grading between scenes")
            recommendations.append("Apply consistent color correction across all scenes")

        return max(0.0, score)

    def _assess_audio_quality(
        self, video_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess audio quality of the video."""
        score = 1.0

        metadata = video_data.get("metadata", {})
        audio_info = metadata.get("audio", {})

        # Check if audio exists
        has_audio = audio_info.get("has_audio", True)
        if not has_audio:
            score -= 0.3
            issues.append("Video has no audio track")
            recommendations.append("Add audio track with dialogue and/or background music")

        # Check audio quality metrics
        if has_audio:
            sample_rate = audio_info.get("sample_rate", 0)
            if sample_rate and sample_rate < 22050:
                score -= 0.2
                issues.append(f"Low audio sample rate: {sample_rate} Hz")
                recommendations.append("Use higher quality audio (44.1kHz or 48kHz)")

            bit_rate = audio_info.get("bit_rate", 0)
            if bit_rate and bit_rate < 128:
                score -= 0.1
                issues.append(f"Low audio bit rate: {bit_rate} kbps")
                recommendations.append("Increase audio bit rate for better quality")

            # Check audio levels
            volume_level = audio_info.get("average_volume", 0)
            if volume_level and volume_level < 0.3:
                score -= 0.1
                issues.append("Audio volume too low")
                recommendations.append("Increase audio volume levels")
            elif volume_level and volume_level > 0.9:
                score -= 0.1
                issues.append("Audio volume too high (may cause distortion)")
                recommendations.append("Reduce audio volume to prevent clipping")

        # Check dialogue clarity
        dialogue_clarity = audio_info.get("dialogue_clarity", 0)
        if dialogue_clarity and dialogue_clarity < 0.6:
            score -= 0.15
            issues.append("Poor dialogue clarity")
            recommendations.append("Improve dialogue audio processing or voice synthesis")

        return max(0.0, score)

    def _assess_file_integrity(
        self, video_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess file integrity and corruption issues."""
        score = 1.0

        file_path = video_data.get("file_path", "")

        if not file_path or not os.path.exists(file_path):
            return 0.0

        try:
            # Check if file can be opened
            with open(file_path, "rb") as f:
                # Read first and last 1KB to check basic integrity
                header = f.read(1024)
                f.seek(-1024, 2)
                footer = f.read(1024)

                if len(header) < 100 or len(footer) < 100:
                    score -= 0.3
                    issues.append("Video file appears corrupted or incomplete")
                    recommendations.append("Regenerate video file")

        except Exception as e:
            score -= 0.5
            issues.append(f"File integrity check failed: {str(e)}")
            recommendations.append("Check file system and regenerate video")

        # Check for metadata corruption
        metadata = video_data.get("metadata", {})
        if metadata:
            required_fields = ["duration", "width", "height"]
            missing_fields = [field for field in required_fields if not metadata.get(field)]

            if missing_fields:
                score -= 0.1 * len(missing_fields)
                issues.append(f"Missing video metadata: {', '.join(missing_fields)}")
                recommendations.append("Ensure complete metadata extraction during generation")

        return max(0.0, score)

    def _assess_timing_accuracy(
        self, video_data: dict, content_source: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess timing accuracy relative to source content."""
        score = 1.0

        if not content_source:
            return 0.7  # Neutral score when no comparison possible

        metadata = video_data.get("metadata", {})
        actual_duration = metadata.get("duration", 0)

        # Estimate expected duration from source content
        source_scenes = content_source.get("scenes", [])
        estimated_duration = len(source_scenes) * 10  # Assume ~10 seconds per scene

        if actual_duration and estimated_duration:
            duration_ratio = actual_duration / estimated_duration

            if duration_ratio < 0.5:
                score -= 0.3
                issues.append(
                    f"Video too short: {actual_duration}s vs expected ~{estimated_duration}s"
                )
                recommendations.append("Increase scene duration or add more content")
            elif duration_ratio > 2.0:
                score -= 0.2
                issues.append(
                    f"Video too long: {actual_duration}s vs expected ~{estimated_duration}s"
                )
                recommendations.append("Reduce scene length or optimize pacing")

        # Check scene timing distribution
        scenes = video_data.get("scenes", [])
        if scenes:
            scene_durations = [
                scene.get("duration", 0) for scene in scenes if isinstance(scene, dict)
            ]
            if scene_durations:
                avg_scene_duration = sum(scene_durations) / len(scene_durations)
                if avg_scene_duration < 3:
                    score -= 0.1
                    issues.append("Scenes too short on average")
                    recommendations.append("Increase individual scene durations")
                elif avg_scene_duration > 30:
                    score -= 0.1
                    issues.append("Scenes too long on average")
                    recommendations.append("Break long scenes into shorter segments")

        return max(0.0, score)

    def _detect_visual_inconsistencies(self, scenes: list[dict]) -> list[str]:
        """Detect visual inconsistencies between scenes."""
        inconsistencies = []

        # Check for drastic style changes
        styles = []
        for scene in scenes:
            if isinstance(scene, dict):
                style = scene.get("visual_style", "")
                if style:
                    styles.append(style)

        unique_styles = set(styles)
        if len(unique_styles) > len(styles) * 0.5:  # Too many different styles
            inconsistencies.append("Inconsistent visual styles between scenes")

        # Check for character appearance consistency
        characters_per_scene = []
        for scene in scenes:
            if isinstance(scene, dict):
                characters = scene.get("characters", [])
                characters_per_scene.append(set(characters))

        # More sophisticated consistency checks could be added here

        return inconsistencies

    def validate_video_batch(self, video_results: list[dict]) -> dict:
        """
        Validate a batch of video generation results.

        Args:
            video_results: List of video generation results

        Returns:
            Dictionary with batch validation summary
        """
        if not video_results:
            return {
                "overall_quality": 0.0,
                "acceptable_count": 0,
                "total_count": 0,
                "issues": ["No videos generated"],
                "recommendations": ["Check video generation process"],
            }

        reports = [self.validate_video_output(result) for result in video_results]
        acceptable_reports = [r for r in reports if r.is_acceptable]

        overall_quality = sum(r.overall_score for r in reports) / len(reports)

        # Aggregate issues and recommendations
        all_issues = []
        all_recommendations = []
        for report in reports:
            all_issues.extend(report.issues)
            all_recommendations.extend(report.recommendations)

        unique_issues = list(dict.fromkeys(all_issues))
        unique_recommendations = list(dict.fromkeys(all_recommendations))

        return {
            "overall_quality": overall_quality,
            "acceptable_count": len(acceptable_reports),
            "total_count": len(reports),
            "quality_distribution": {
                "excellent": len([r for r in reports if r.overall_score >= 0.8]),
                "good": len([r for r in reports if 0.6 <= r.overall_score < 0.8]),
                "poor": len([r for r in reports if r.overall_score < 0.6]),
            },
            "average_scores": {
                "technical_quality": sum(r.technical_quality for r in reports) / len(reports),
                "content_accuracy": sum(r.content_accuracy for r in reports) / len(reports),
                "visual_coherence": sum(r.visual_coherence for r in reports) / len(reports),
                "audio_quality": sum(r.audio_quality for r in reports) / len(reports),
                "file_integrity": sum(r.file_integrity for r in reports) / len(reports),
            },
            "issues": unique_issues[:10],
            "recommendations": unique_recommendations[:10],
            "detailed_reports": reports,
        }
