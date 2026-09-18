"""
Quality Assurance Agent - Main interface for quality validation.

This agent now serves as a simplified interface to the comprehensive
quality agent system located in quality_agents/ directory.
"""

import logging

from .quality_agents.quality_coordinator import QualityCoordinator

logger = logging.getLogger(__name__)


class QualityAssuranceAgent:
    """
    Main quality assurance agent that coordinates all quality validation.

    This agent provides a simplified interface to the comprehensive quality
    validation system while maintaining backward compatibility.
    """

    def __init__(self):
        """
        Initialize the quality assurance agent.

        Sets up the quality coordinator that manages all specialized
        quality validation agents for comprehensive workflow quality assurance.
        """
        self.coordinator = QualityCoordinator()

    def validate_transcript_quality(self, transcript_data: dict) -> dict:
        """
        Validate transcript quality using specialized transcript quality agent.

        Args:
            transcript_data: Dictionary containing transcript information

        Returns:
            Dictionary with validation results
        """
        logger.info("Validating transcript quality")

        report = self.coordinator.validate_stage_quality("transcript", transcript_data)

        return {
            "overall_score": report.overall_score,
            "is_acceptable": report.is_acceptable,
            "issues": report.issues,
            "recommendations": report.recommendations,
            "detailed_scores": {
                "content_completeness": report.content_completeness,
                "format_consistency": report.format_consistency,
                "dialogue_ratio": report.character_dialogue_ratio,
                "scene_quality": report.scene_description_quality,
                "source_reliability": report.source_reliability,
            },
        }

    def validate_content_quality(self, content_data: dict, original_transcript: str = "") -> dict:
        """
        Validate AI-generated content quality.

        Args:
            content_data: Dictionary containing AI-generated content
            original_transcript: Original transcript for comparison

        Returns:
            Dictionary with validation results
        """
        logger.info("Validating AI content quality")

        context = {"original_transcript": original_transcript}
        report = self.coordinator.validate_stage_quality("content", content_data, context)

        return {
            "overall_score": report.overall_score,
            "is_acceptable": report.is_acceptable,
            "issues": report.issues,
            "recommendations": report.recommendations,
            "detailed_scores": {
                "script_coherence": report.script_coherence,
                "scene_descriptions": report.scene_descriptions,
                "character_consistency": report.character_consistency,
                "dialogue_quality": report.dialogue_quality,
                "visual_descriptions": report.visual_descriptions,
                "technical_accuracy": report.technical_accuracy,
            },
        }

    def validate_complete_workflow(
        self,
        transcript_data: dict = None,
        content_data: dict = None,
        video_data: dict = None,
        discovery_data: dict = None,
        workflow_data: dict = None,
        show_name: str = "",
    ) -> dict:
        """
        Validate quality across the complete workflow.

        Args:
            transcript_data: Transcript discovery results
            content_data: AI-generated content results
            video_data: Video generation results
            discovery_data: Episode discovery results
            workflow_data: Workflow execution data
            show_name: Show name for context

        Returns:
            Dictionary with comprehensive validation results
        """
        logger.info(f"Performing complete workflow quality validation for: {show_name}")

        report = self.coordinator.validate_complete_workflow(
            transcript_data=transcript_data,
            content_data=content_data,
            video_data=video_data,
            discovery_data=discovery_data,
            workflow_data=workflow_data,
            show_name=show_name,
        )

        return {
            "overall_score": report.overall_score,
            "meets_standards": report.meets_standards,
            "stage_scores": report.stage_scores,
            "critical_issues": report.critical_issues,
            "recommendations": self.coordinator.get_quality_recommendations(report),
            "passed_quality_gates": report.passed_quality_gates,
            "failed_quality_gates": report.failed_quality_gates,
            "quality_trends": report.quality_trends,
        }

    # Legacy methods for backward compatibility
    def validate_content(self, summary: str, plot_points: list[str]) -> dict:
        """
        Legacy method for backward compatibility.

        .. warning::
            **This score must not be used as a quality gate.** The method only
            receives a summary string and a list of plot points, so it has to
            invent a content payload whose ``characters``, ``dialogue`` and
            ``visual_elements`` sections are *always* empty. Those three
            sections carry 50% of :class:`ContentQualityAgent`'s weight and
            also trip the "missing required sections" coherence penalty, so
            even well-formed input tops out around ``quality_score`` 6/10
            (0.60) - below the 0.70 ``content_generation`` gate defined in
            :class:`QualityCoordinator`. The number therefore measures the
            shape of this shim, not the quality of the content.

            For real gating use :meth:`validate_content_quality` with a fully
            populated payload, or :meth:`validate_complete_workflow`.

        Args:
            summary: Episode summary
            plot_points: List of plot points

        Returns:
            Dictionary with validation results
        """
        # Convert legacy format to new format
        content_data = {
            "scenes": [{"description": point} for point in plot_points],
            "summary": summary,
            "characters": [],
            "dialogue": [],
            "visual_elements": [],
        }

        result = self.validate_content_quality(content_data)

        # Convert back to legacy format
        return {
            "quality_score": int(result["overall_score"] * 10),
            "issues": result["issues"],
            "suggestions": result["recommendations"],
        }

    def check_file_integrity(self, file_paths: list[str]) -> list[str]:
        """
        Legacy method for file integrity checking.

        Args:
            file_paths: List of file paths to check

        Returns:
            List of issues found
        """
        import os

        issues = []

        for file_path in file_paths:
            if not os.path.exists(file_path):
                issues.append(f"Missing file: {file_path}")
            elif os.path.getsize(file_path) == 0:
                issues.append(f"Empty file: {file_path}")

        return issues
