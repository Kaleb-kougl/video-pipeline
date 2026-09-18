"""
Workflow Quality Agent - Validates overall workflow quality and coordination.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class WorkflowQualityReport:
    """Quality report for overall workflow execution."""

    overall_score: float
    process_completeness: float
    error_handling: float
    timing_efficiency: float
    resource_utilization: float
    output_quality: float
    coordination_quality: float
    issues: list[str]
    recommendations: list[str]

    @property
    def is_acceptable(self) -> bool:
        """Returns True if workflow meets minimum quality standards."""
        return self.overall_score >= 0.7


class WorkflowQualityAgent:
    """Agent responsible for validating overall workflow quality."""

    def __init__(self):
        """Initialize the workflow quality agent."""
        self.expected_stages = [
            "transcript_discovery",
            "content_generation",
            "video_generation",
            "quality_validation",
        ]
        self.max_reasonable_duration = timedelta(hours=2)
        self.min_reasonable_duration = timedelta(minutes=5)

    def validate_workflow_execution(self, workflow_data: dict) -> WorkflowQualityReport:
        """
        Validate the quality of workflow execution.

        Args:
            workflow_data: Dictionary containing workflow execution data

        Returns:
            WorkflowQualityReport: Detailed quality assessment
        """
        issues = []
        recommendations = []

        logger.info("Validating workflow execution quality")

        # 1. Process completeness validation
        completeness_score = self._assess_process_completeness(
            workflow_data, issues, recommendations
        )

        # 2. Error handling validation
        error_score = self._assess_error_handling(workflow_data, issues, recommendations)

        # 3. Timing efficiency validation
        timing_score = self._assess_timing_efficiency(workflow_data, issues, recommendations)

        # 4. Resource utilization validation
        resource_score = self._assess_resource_utilization(workflow_data, issues, recommendations)

        # 5. Output quality validation
        output_score = self._assess_output_quality(workflow_data, issues, recommendations)

        # 6. Coordination quality validation
        coordination_score = self._assess_coordination_quality(
            workflow_data, issues, recommendations
        )

        # Calculate overall score
        weights = {
            "completeness": 0.25,
            "error_handling": 0.20,
            "timing": 0.15,
            "resource": 0.10,
            "output": 0.20,
            "coordination": 0.10,
        }

        overall_score = (
            completeness_score * weights["completeness"]
            + error_score * weights["error_handling"]
            + timing_score * weights["timing"]
            + resource_score * weights["resource"]
            + output_score * weights["output"]
            + coordination_score * weights["coordination"]
        )

        return WorkflowQualityReport(
            overall_score=overall_score,
            process_completeness=completeness_score,
            error_handling=error_score,
            timing_efficiency=timing_score,
            resource_utilization=resource_score,
            output_quality=output_score,
            coordination_quality=coordination_score,
            issues=issues,
            recommendations=recommendations,
        )

    def _assess_process_completeness(
        self, workflow_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess completeness of workflow stages."""
        score = 1.0

        stages_executed = workflow_data.get("stages_executed", [])

        # Check if all expected stages were executed
        missing_stages = set(self.expected_stages) - set(stages_executed)
        if missing_stages:
            score -= 0.2 * len(missing_stages)
            issues.append(f"Missing workflow stages: {', '.join(missing_stages)}")
            recommendations.append("Ensure all required workflow stages are executed")

        # Check stage execution success
        stage_results = workflow_data.get("stage_results", {})
        failed_stages = []

        for stage in stages_executed:
            stage_result = stage_results.get(stage, {})
            if not stage_result.get("success", False):
                failed_stages.append(stage)

        if failed_stages:
            score -= 0.15 * len(failed_stages)
            issues.append(f"Failed workflow stages: {', '.join(failed_stages)}")
            recommendations.append("Investigate and fix failed workflow stages")

        # Check for stage output quality
        for stage in stages_executed:
            stage_result = stage_results.get(stage, {})
            output_quality = stage_result.get("output_quality", 0)

            if output_quality < 0.6:
                score -= 0.05
                issues.append(f"Low output quality in stage: {stage}")
                recommendations.append(f"Improve {stage} stage output quality")

        return max(0.0, score)

    def _assess_error_handling(
        self, workflow_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess quality of error handling throughout workflow."""
        score = 1.0

        errors = workflow_data.get("errors", [])
        error_recovery = workflow_data.get("error_recovery", {})

        # Assess error frequency
        if len(errors) > 5:
            score -= 0.3
            issues.append(f"High error count: {len(errors)}")
            recommendations.append("Investigate root causes of frequent errors")
        elif len(errors) > 2:
            score -= 0.1
            issues.append(f"Multiple errors occurred: {len(errors)}")
            recommendations.append("Monitor error patterns for improvement opportunities")

        # Assess error severity
        critical_errors = [e for e in errors if e.get("severity") == "critical"]
        if critical_errors:
            score -= 0.2 * min(len(critical_errors), 3)
            issues.append(f"Critical errors encountered: {len(critical_errors)}")
            recommendations.append("Address critical errors immediately")

        # Assess error recovery effectiveness
        if errors and error_recovery:
            recovery_rate = error_recovery.get("successful_recoveries", 0) / len(errors)
            if recovery_rate < 0.5:
                score -= 0.15
                issues.append("Poor error recovery rate")
                recommendations.append("Improve error recovery mechanisms")
        elif errors and not error_recovery:
            score -= 0.2
            issues.append("No error recovery attempted")
            recommendations.append("Implement error recovery strategies")

        # Check for unhandled exceptions
        unhandled_exceptions = workflow_data.get("unhandled_exceptions", [])
        if unhandled_exceptions:
            score -= 0.25
            issues.append(f"Unhandled exceptions: {len(unhandled_exceptions)}")
            recommendations.append("Add proper exception handling for all workflow stages")

        return max(0.0, score)

    def _assess_timing_efficiency(
        self, workflow_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess timing efficiency of workflow execution."""
        score = 1.0

        start_time = workflow_data.get("start_time")
        end_time = workflow_data.get("end_time")

        if start_time and end_time:
            try:
                if isinstance(start_time, str):
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                else:
                    start_dt = start_time

                if isinstance(end_time, str):
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                else:
                    end_dt = end_time

                duration = end_dt - start_dt

                # Check if duration is reasonable
                if duration > self.max_reasonable_duration:
                    score -= 0.3
                    issues.append(f"Workflow took too long: {duration}")
                    recommendations.append("Optimize workflow performance and identify bottlenecks")
                elif duration < self.min_reasonable_duration:
                    score -= 0.1
                    issues.append(f"Workflow completed suspiciously fast: {duration}")
                    recommendations.append("Verify all stages executed properly")

            except (ValueError, TypeError) as e:
                score -= 0.1
                issues.append(f"Invalid timestamp format: {e}")
                recommendations.append("Use proper timestamp format for timing analysis")
        else:
            score -= 0.2
            issues.append("Missing timing information")
            recommendations.append("Include start and end times for performance analysis")

        # Check stage timing distribution
        stage_timings = workflow_data.get("stage_timings", {})
        if stage_timings:
            total_time = sum(stage_timings.values())
            if total_time > 0:
                # Check for stages that take disproportionate time
                for stage, time_taken in stage_timings.items():
                    time_ratio = time_taken / total_time
                    if time_ratio > 0.7:  # One stage taking more than 70% of time
                        score -= 0.1
                        issues.append(f"Stage '{stage}' taking excessive time: {time_ratio:.1%}")
                        recommendations.append(f"Optimize {stage} stage performance")

        return max(0.0, score)

    def _assess_resource_utilization(
        self, workflow_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess resource utilization efficiency."""
        score = 1.0

        resource_usage = workflow_data.get("resource_usage", {})

        # Check memory usage
        memory_usage = resource_usage.get("memory_peak", 0)
        if memory_usage > 8 * 1024 * 1024 * 1024:  # More than 8GB
            score -= 0.2
            issues.append(f"High memory usage: {memory_usage / (1024**3):.1f} GB")
            recommendations.append("Optimize memory usage in processing stages")

        # Check CPU usage patterns
        cpu_usage = resource_usage.get("cpu_average", 0)
        if cpu_usage > 0.9:  # More than 90% CPU
            score -= 0.1
            issues.append(f"High CPU usage: {cpu_usage:.1%}")
            recommendations.append("Consider parallel processing or optimization")
        elif cpu_usage < 0.1:  # Less than 10% CPU
            score -= 0.05
            issues.append("Very low CPU utilization")
            recommendations.append("May indicate inefficient processing or waiting")

        # Check disk I/O
        disk_usage = resource_usage.get("disk_io", {})
        if disk_usage:
            read_mb = disk_usage.get("read_mb", 0)
            write_mb = disk_usage.get("write_mb", 0)

            if read_mb > 10000 or write_mb > 10000:  # More than 10GB
                score -= 0.1
                issues.append("High disk I/O usage")
                recommendations.append("Optimize file operations and caching")

        # Check API call efficiency
        api_calls = resource_usage.get("api_calls", {})
        if api_calls:
            total_calls = sum(api_calls.values())
            if total_calls > 100:
                score -= 0.1
                issues.append(f"High API call count: {total_calls}")
                recommendations.append("Optimize API usage and implement caching")

        return max(0.0, score)

    def _assess_output_quality(
        self, workflow_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess quality of workflow outputs."""
        score = 1.0

        final_outputs = workflow_data.get("final_outputs", {})

        # Check output completeness
        expected_outputs = ["video_file", "metadata", "quality_report"]
        missing_outputs = []

        for output in expected_outputs:
            if output not in final_outputs or not final_outputs[output]:
                missing_outputs.append(output)

        if missing_outputs:
            score -= 0.2 * len(missing_outputs)
            issues.append(f"Missing outputs: {', '.join(missing_outputs)}")
            recommendations.append("Ensure all expected outputs are generated")

        # Check output quality scores
        quality_scores = workflow_data.get("quality_scores", {})
        for output_type, quality_score in quality_scores.items():
            if quality_score < 0.6:
                score -= 0.1
                issues.append(f"Low quality score for {output_type}: {quality_score}")
                recommendations.append(f"Improve {output_type} generation quality")

        # Check for output validation
        validation_results = workflow_data.get("validation_results", {})
        if not validation_results:
            score -= 0.15
            issues.append("No output validation performed")
            recommendations.append("Implement output validation for all workflow products")
        else:
            failed_validations = [
                k for k, v in validation_results.items() if not v.get("passed", True)
            ]
            if failed_validations:
                score -= 0.1 * len(failed_validations)
                issues.append(f"Failed validations: {', '.join(failed_validations)}")
                recommendations.append("Address validation failures before finalizing outputs")

        return max(0.0, score)

    def _assess_coordination_quality(
        self, workflow_data: dict, issues: list[str], recommendations: list[str]
    ) -> float:
        """Assess quality of coordination between workflow stages."""
        score = 1.0

        stage_handoffs = workflow_data.get("stage_handoffs", [])

        # Check handoff success rate
        if stage_handoffs:
            failed_handoffs = [h for h in stage_handoffs if not h.get("success", True)]
            if failed_handoffs:
                failure_rate = len(failed_handoffs) / len(stage_handoffs)
                score -= failure_rate * 0.3
                issues.append(f"Failed stage handoffs: {len(failed_handoffs)}")
                recommendations.append("Improve data passing between workflow stages")

        # Check data consistency between stages
        data_consistency = workflow_data.get("data_consistency", {})
        for stage_pair, consistency_score in data_consistency.items():
            if consistency_score < 0.8:
                score -= 0.1
                issues.append(f"Data inconsistency between {stage_pair}: {consistency_score}")
                recommendations.append("Ensure consistent data formats between stages")

        # Check parallel stage coordination
        parallel_stages = workflow_data.get("parallel_stages", [])
        if parallel_stages:
            coordination_issues = workflow_data.get("coordination_issues", [])
            if coordination_issues:
                score -= 0.1 * min(len(coordination_issues), 3)
                issues.extend(coordination_issues[:3])
                recommendations.append("Improve parallel stage synchronization")

        return max(0.0, score)

    def validate_workflow_batch(self, workflow_results: list[dict]) -> dict:
        """
        Validate a batch of workflow executions.

        Args:
            workflow_results: List of workflow execution results

        Returns:
            Dictionary with batch validation summary
        """
        if not workflow_results:
            return {
                "overall_quality": 0.0,
                "acceptable_count": 0,
                "total_count": 0,
                "issues": ["No workflows executed"],
                "recommendations": ["Check workflow orchestration system"],
            }

        reports = [self.validate_workflow_execution(result) for result in workflow_results]
        acceptable_reports = [r for r in reports if r.is_acceptable]

        overall_quality = sum(r.overall_score for r in reports) / len(reports)

        # Calculate performance metrics
        total_duration = timedelta()
        successful_workflows = 0

        for result in workflow_results:
            start_time = result.get("start_time")
            end_time = result.get("end_time")

            if start_time and end_time:
                try:
                    if isinstance(start_time, str):
                        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    else:
                        start_dt = start_time

                    if isinstance(end_time, str):
                        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    else:
                        end_dt = end_time

                    total_duration += end_dt - start_dt

                except (ValueError, TypeError):
                    pass

            if result.get("success", False):
                successful_workflows += 1

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
            "success_rate": successful_workflows / len(workflow_results) if workflow_results else 0,
            "average_duration": str(total_duration / len(workflow_results))
            if workflow_results
            else "0:00:00",
            "quality_distribution": {
                "excellent": len([r for r in reports if r.overall_score >= 0.8]),
                "good": len([r for r in reports if 0.7 <= r.overall_score < 0.8]),
                "poor": len([r for r in reports if r.overall_score < 0.7]),
            },
            "average_scores": {
                "process_completeness": sum(r.process_completeness for r in reports) / len(reports),
                "error_handling": sum(r.error_handling for r in reports) / len(reports),
                "timing_efficiency": sum(r.timing_efficiency for r in reports) / len(reports),
                "output_quality": sum(r.output_quality for r in reports) / len(reports),
            },
            "issues": unique_issues[:10],
            "recommendations": unique_recommendations[:10],
            "detailed_reports": reports,
        }
