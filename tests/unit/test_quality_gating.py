"""
Tests for the content quality gate decision in the workflow orchestrator, and
for issue deduplication in the quality coordinator.

Background: three sites in ``WorkflowOrchestrator`` used to call
``qa_agent.validate_content(...)`` and throw the result away, so they read like
quality gates but gated nothing. The calls were removed rather than wired up,
because the score they produce is not gateable. The first test below pins the
measurement that justifies that decision - if someone makes the legacy shim
score honestly, this test fails and the gate can be reconsidered.
"""

import inspect

from agents.quality_agent import QualityAssuranceAgent
from agents.quality_agents.quality_coordinator import QualityCoordinator


def _realistic_summary_and_plot_points() -> tuple[str, list[str]]:
    """Well-formed content of the shape the orchestrator actually produces."""
    summary = (
        "In this episode of Demon Slayer, Tanjiro Kamado tracks a demon through "
        "the misty forest of Natagumo Mountain while his companions regroup. "
    ) * 20
    plot_points = [
        "Tanjiro Kamado arrives at Natagumo Mountain and senses a powerful "
        "demon presence lurking in the misty forest.",
        "Nezuko Kamado is captured by spider threads while Zenitsu Agatsuma "
        "panics in the dark woods below the ridge.",
        "Giyu Tomioka appears and demonstrates Water Breathing techniques "
        "against the spider demon family.",
        "Tanjiro unlocks Hinokami Kagura, the Dance of the Fire God, in a "
        "brilliant burst of flame.",
        "Rui the demon is defeated as dawn breaks over the mountain and the "
        "survivors regroup at the base camp.",
    ]
    return summary, plot_points


class TestLegacyValidateContentIsNotGateable:
    """The legacy shim's score reflects its own shape, not content quality."""

    def test_good_content_still_scores_below_the_content_gate(self):
        """
        Even well-formed content cannot clear the content_generation gate.

        ``validate_content`` only receives a summary and plot points, so it
        fabricates a payload whose ``characters``, ``dialogue`` and
        ``visual_elements`` are always empty. Those carry 50% of the content
        score's weight, so the result is capped well below the 0.70 threshold.
        Gating on it would abort every run.
        """
        summary, plot_points = _realistic_summary_and_plot_points()
        result = QualityAssuranceAgent().validate_content(summary, plot_points)

        # quality_score is int(overall_score * 10), i.e. a 0-10 scale.
        gate = QualityCoordinator().quality_gates["content_generation"]
        assert gate["min_score"] == 0.7
        assert gate["critical"] is True
        assert result["quality_score"] / 10 < gate["min_score"], (
            "The legacy shim now clears the content gate; the decision to drop "
            "the orchestrator's gate calls should be revisited."
        )

    def test_the_always_empty_sections_are_what_costs_the_score(self):
        """The deductions come from sections the shim can never populate."""
        summary, plot_points = _realistic_summary_and_plot_points()
        issues = QualityAssuranceAgent().validate_content(summary, plot_points)["issues"]

        joined = " ".join(issues)
        assert "characters" in joined
        assert "dialogue" in joined.lower()
        assert "visual_elements" in joined or "visual elements" in joined.lower()


class TestOrchestratorHasNoFakeGate:
    """The orchestrator must not compute a quality score and discard it."""

    def test_no_discarded_validate_content_calls_remain(self):
        from agents import workflow_orchestrator

        source = inspect.getsource(workflow_orchestrator)
        # Strip comments so the explanatory notes do not count as calls.
        code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        assert "qa_agent.validate_content(" not in code
        assert "_quality_check" not in code


class TestQualityCoordinatorDeduplicatesIssues:
    """``critical_issues`` must not repeat the same issue twice."""

    def test_critical_issues_are_deduplicated(self):
        coordinator = QualityCoordinator()

        class _Report:
            overall_score = 0.0
            issues = ["CRITICAL: duplicated problem", "CRITICAL: duplicated problem"]
            recommendations = ["fix it", "fix it"]

        # Two stages both fail and both report the identical issue string.
        coordinator.transcript_agent.validate_transcript_discovery = lambda *a, **k: _Report()
        coordinator.workflow_agent.validate_workflow_execution = lambda *a, **k: _Report()

        report = coordinator.validate_complete_workflow(
            transcript_data={"transcript": "x"},
            workflow_data={"steps": []},
            show_name="Test Show",
        )

        assert report.critical_issues.count("CRITICAL: duplicated problem") == 1
        # Both stages still fail their gates - dedup must not hide failures.
        assert set(report.failed_quality_gates) == {
            "transcript_discovery",
            "workflow_execution",
        }
        assert report.recommendations.count("fix it") == 1
