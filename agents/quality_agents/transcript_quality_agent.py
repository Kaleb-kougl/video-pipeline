"""
Transcript Quality Agent - Validates transcript discovery and content quality.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TranscriptQualityReport:
    """Quality report for transcript content."""

    overall_score: float
    content_completeness: float
    format_consistency: float
    character_dialogue_ratio: float
    scene_description_quality: float
    source_reliability: float
    issues: list[str]
    recommendations: list[str]

    @property
    def is_acceptable(self) -> bool:
        """Returns True if transcript meets minimum quality standards."""
        return self.overall_score >= 0.6


class TranscriptQualityAgent:
    """Agent responsible for validating transcript quality at discovery."""

    def __init__(self):
        """Initialize the transcript quality agent."""
        self.min_content_length = 500  # Minimum character count
        self.max_content_length = 100000  # Maximum reasonable length
        self.dialogue_markers = [":", '"', '"', '"', """, """]
        self.scene_markers = [
            "[",
            "]",
            "(",
            ")",
            "*",
            "SCENE:",
            "CUT TO:",
            "FADE IN:",
            "INT.",
            "EXT.",
        ]

    def validate_transcript_discovery(self, transcript_data: dict) -> TranscriptQualityReport:
        """
        Validate the quality of discovered transcript data.

        Args:
            transcript_data: Dictionary containing transcript info

        Returns:
            TranscriptQualityReport: Detailed quality assessment
        """
        issues = []
        recommendations = []

        # Extract content and metadata
        content = transcript_data.get("transcript", "")
        url = transcript_data.get("url", "")
        source = transcript_data.get("source", "unknown")

        logger.info(f"Validating transcript from {source}: {len(content)} characters")

        # 1. Content completeness validation
        completeness_score = self._assess_content_completeness(content, issues, recommendations)

        # 2. Format consistency validation
        format_score = self._assess_format_consistency(content, issues, recommendations)

        # 3. Character dialogue ratio
        dialogue_score = self._assess_dialogue_ratio(content, issues, recommendations)

        # 4. Scene description quality
        scene_score = self._assess_scene_descriptions(content, issues, recommendations)

        # 5. Source reliability
        source_score = self._assess_source_reliability(url, source, issues, recommendations)

        # Calculate overall score
        weights = {
            "completeness": 0.3,
            "format": 0.2,
            "dialogue": 0.2,
            "scene": 0.15,
            "source": 0.15,
        }

        overall_score = (
            completeness_score * weights["completeness"]
            + format_score * weights["format"]
            + dialogue_score * weights["dialogue"]
            + scene_score * weights["scene"]
            + source_score * weights["source"]
        )

        return TranscriptQualityReport(
            overall_score=overall_score,
            content_completeness=completeness_score,
            format_consistency=format_score,
            character_dialogue_ratio=dialogue_score,
            scene_description_quality=scene_score,
            source_reliability=source_score,
            issues=issues,
            recommendations=recommendations,
        )

    def _assess_content_completeness(
        self, content: str, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess if the transcript content is complete and substantial."""
        score = 1.0

        # Check minimum length
        if len(content) < self.min_content_length:
            score -= 0.4
            issues.append(
                f"Content too short: {len(content)} chars (min: {self.min_content_length})"
            )
            recommendations.append("Try alternative transcript sources for more complete content")

        # Check maximum length (might indicate duplicate/corrupted content)
        if len(content) > self.max_content_length:
            score -= 0.2
            issues.append(
                f"Content unusually long: {len(content)} chars (max: {self.max_content_length})"
            )
            recommendations.append("Verify content isn't duplicated or corrupted")

        # Check for common incomplete indicators
        incomplete_indicators = [
            "transcript not available",
            "coming soon",
            "transcript in progress",
            "[missing]",
            "[incomplete]",
        ]

        for indicator in incomplete_indicators:
            if indicator.lower() in content.lower():
                score -= 0.3
                issues.append(f"Content appears incomplete: contains '{indicator}'")
                recommendations.append("Search for alternative transcript sources")

        return max(0.0, score)

    def _assess_format_consistency(
        self, content: str, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess the consistency of transcript formatting."""
        score = 1.0

        # Check for consistent dialogue formatting
        lines = content.split("\n")
        dialogue_lines = [
            line for line in lines if any(marker in line for marker in self.dialogue_markers)
        ]

        if dialogue_lines:
            # Check consistency in character name formatting
            character_patterns = []
            for line in dialogue_lines[:10]:  # Sample first 10 dialogue lines
                if ":" in line:
                    char_name = line.split(":")[0].strip()
                    if char_name.isupper():
                        character_patterns.append("UPPER")
                    elif char_name.istitle():
                        character_patterns.append("Title")
                    else:
                        character_patterns.append("mixed")

            if len(set(character_patterns)) > 1:
                score -= 0.2
                issues.append("Inconsistent character name formatting")
                recommendations.append("Consider normalizing character name format")
        else:
            score -= 0.3
            issues.append("No clear dialogue structure detected")
            recommendations.append("Verify transcript format and try alternative sources")

        # Check for consistent scene breaks
        scene_breaks = len(
            [line for line in lines if any(marker in line.upper() for marker in self.scene_markers)]
        )
        total_lines = len([line for line in lines if line.strip()])

        if total_lines > 50 and scene_breaks == 0:
            score -= 0.1
            issues.append("No scene breaks detected in long transcript")
            recommendations.append("Content may lack proper scene structure")

        return max(0.0, score)

    def _assess_dialogue_ratio(
        self, content: str, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess the ratio of dialogue to total content."""
        lines = content.split("\n")
        dialogue_lines = len(
            [line for line in lines if any(marker in line for marker in self.dialogue_markers)]
        )
        total_lines = len([line for line in lines if line.strip()])

        if total_lines == 0:
            return 0.0

        dialogue_ratio = dialogue_lines / total_lines

        # Good dialogue ratio is between 0.3 and 0.8
        if dialogue_ratio < 0.2:
            issues.append(f"Low dialogue ratio: {dialogue_ratio:.2f}")
            recommendations.append("Content may be missing dialogue or be incorrectly formatted")
            return 0.3
        elif dialogue_ratio > 0.9:
            issues.append(f"Very high dialogue ratio: {dialogue_ratio:.2f}")
            recommendations.append("Content may be missing scene descriptions")
            return 0.7
        else:
            return 1.0

    def _assess_scene_descriptions(
        self, content: str, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess the quality of scene descriptions."""
        score = 1.0

        # Look for action/scene description indicators
        action_indicators = [
            "[",
            "]",
            "(",
            ")",
            "walks",
            "runs",
            "looks",
            "enters",
            "exits",
            "suddenly",
            "meanwhile",
            "later",
            "cut to",
            "fade in",
            "fade out",
        ]

        action_count = sum(content.lower().count(indicator) for indicator in action_indicators)
        content_length = len(content.split())

        if content_length > 0:
            action_ratio = action_count / content_length

            if action_ratio < 0.05:
                score -= 0.3
                issues.append("Very few scene descriptions detected")
                recommendations.append("Content may lack visual context for video generation")
            elif action_ratio > 0.5:
                score -= 0.1
                issues.append("Very high scene description ratio")
                recommendations.append("Verify content balance between dialogue and action")

        return max(0.0, score)

    def _assess_source_reliability(
        self, url: str, source: str, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess the reliability of the transcript source."""
        score = 1.0

        # Preferred sources (higher reliability)
        preferred_sources = [
            "fandom.com",
            "wikia.com",
            "transcripts.foreverdreaming.org",
            "springfieldspringfield.co.uk",
        ]

        # Questionable sources (lower reliability)
        questionable_sources = ["fan-made", "user-generated", "unofficial", "auto-generated"]

        url_lower = url.lower()
        source_lower = source.lower()

        # Check for preferred sources
        if any(preferred in url_lower for preferred in preferred_sources):
            score += 0.0  # Already at max
        elif any(questionable in source_lower for questionable in questionable_sources):
            score -= 0.3
            issues.append(f"Source may be unreliable: {source}")
            recommendations.append("Consider verifying content against official sources")

        # Check URL structure
        if not url or url == "unknown":
            score -= 0.2
            issues.append("No source URL provided")
            recommendations.append("Source traceability is important for quality validation")

        return max(0.0, score)

    def validate_batch_discovery(self, transcript_results: list[dict]) -> dict[str, any]:
        """
        Validate a batch of transcript discovery results.

        Args:
            transcript_results: List of transcript discovery results

        Returns:
            Dictionary with batch validation summary
        """
        if not transcript_results:
            return {
                "overall_quality": 0.0,
                "acceptable_count": 0,
                "total_count": 0,
                "issues": ["No transcripts found"],
                "recommendations": ["Verify show names and episode numbers"],
            }

        reports = [self.validate_transcript_discovery(result) for result in transcript_results]
        acceptable_reports = [r for r in reports if r.is_acceptable]

        overall_quality = sum(r.overall_score for r in reports) / len(reports)

        # Aggregate common issues
        all_issues = []
        all_recommendations = []
        for report in reports:
            all_issues.extend(report.issues)
            all_recommendations.extend(report.recommendations)

        # Remove duplicates while preserving order
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
            "issues": unique_issues[:10],  # Limit to top 10 issues
            "recommendations": unique_recommendations[:10],
            "detailed_reports": reports,
        }
