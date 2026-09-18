"""
Quality Coordinator - Orchestrates all quality agents and provides unified quality management.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .transcript_quality_agent import TranscriptQualityAgent, TranscriptQualityReport
from .content_quality_agent import ContentQualityAgent, ContentQualityReport
from .video_quality_agent import VideoQualityAgent, VideoQualityReport
from .discovery_quality_agent import DiscoveryQualityAgent, DiscoveryQualityReport
from .workflow_quality_agent import WorkflowQualityAgent, WorkflowQualityReport

logger = logging.getLogger(__name__)


@dataclass
class UnifiedQualityReport:
    """Unified quality report across all workflow stages."""
    overall_score: float
    stage_scores: Dict[str, float]
    stage_reports: Dict[str, Any]
    critical_issues: List[str]
    recommendations: List[str]
    quality_trends: Dict[str, Any]
    passed_quality_gates: List[str]
    failed_quality_gates: List[str]
    
    @property
    def meets_standards(self) -> bool:
        """Returns True if all quality gates pass minimum standards."""
        return len(self.failed_quality_gates) == 0 and self.overall_score >= 0.7


class QualityCoordinator:
    """
    Coordinates all quality agents and provides unified quality management.
    """
    
    def __init__(self):
        """
        Initialize the quality coordinator with all quality agents.
        
        Sets up all specialized quality agents, quality gates configuration,
        and historical quality tracking for comprehensive workflow validation.
        """
        self.transcript_agent = TranscriptQualityAgent()
        self.content_agent = ContentQualityAgent()
        self.video_agent = VideoQualityAgent()
        self.discovery_agent = DiscoveryQualityAgent()
        self.workflow_agent = WorkflowQualityAgent()
        
        # Quality gates configuration
        self.quality_gates = {
            'transcript_discovery': {'min_score': 0.6, 'critical': True},
            'content_generation': {'min_score': 0.7, 'critical': True},
            'video_generation': {'min_score': 0.6, 'critical': True},
            'episode_discovery': {'min_score': 0.6, 'critical': False},
            'workflow_execution': {'min_score': 0.7, 'critical': True}
        }
        
        # Historical quality data for trend analysis
        self.quality_history = []
        
    def validate_complete_workflow(self, 
                                 transcript_data: Dict = None,
                                 content_data: Dict = None,
                                 video_data: Dict = None,
                                 discovery_data: Dict = None,
                                 workflow_data: Dict = None,
                                 show_name: str = "") -> UnifiedQualityReport:
        """
        Validate quality across all workflow stages.
        
        Performs comprehensive quality validation across all stages of the video
        generation workflow, checking quality gates and providing actionable recommendations.
        
        Args:
            transcript_data (Dict, optional): Transcript discovery results
            content_data (Dict, optional): AI-generated content results
            video_data (Dict, optional): Video generation results
            discovery_data (Dict, optional): Episode discovery results
            workflow_data (Dict, optional): Workflow execution data
            show_name (str): Show name for context
            
        Returns:
            UnifiedQualityReport: Comprehensive quality assessment with scores and recommendations
        """
        logger.info(f"Performing unified quality validation for: {show_name}")
        
        stage_scores = {}
        stage_reports = {}
        all_issues = []
        all_recommendations = []
        passed_gates = []
        failed_gates = []
        
        # 1. Validate transcript discovery if data provided
        if transcript_data:
            transcript_report = self.transcript_agent.validate_transcript_discovery(transcript_data)
            stage_scores['transcript_discovery'] = transcript_report.overall_score
            stage_reports['transcript_discovery'] = transcript_report
            all_issues.extend(transcript_report.issues)
            all_recommendations.extend(transcript_report.recommendations)
            
            # Check quality gate
            min_score = self.quality_gates['transcript_discovery']['min_score']
            if transcript_report.overall_score >= min_score:
                passed_gates.append('transcript_discovery')
            else:
                failed_gates.append('transcript_discovery')
                if self.quality_gates['transcript_discovery']['critical']:
                    all_issues.append(f"CRITICAL: Transcript quality below threshold ({transcript_report.overall_score:.2f} < {min_score})")
        
        # 2. Validate content generation if data provided
        if content_data:
            original_transcript = transcript_data.get('transcript', '') if transcript_data else ''
            content_report = self.content_agent.validate_ai_content(content_data, original_transcript)
            stage_scores['content_generation'] = content_report.overall_score
            stage_reports['content_generation'] = content_report
            all_issues.extend(content_report.issues)
            all_recommendations.extend(content_report.recommendations)
            
            # Check quality gate
            min_score = self.quality_gates['content_generation']['min_score']
            if content_report.overall_score >= min_score:
                passed_gates.append('content_generation')
            else:
                failed_gates.append('content_generation')
                if self.quality_gates['content_generation']['critical']:
                    all_issues.append(f"CRITICAL: Content quality below threshold ({content_report.overall_score:.2f} < {min_score})")
        
        # 3. Validate video generation if data provided
        if video_data:
            video_report = self.video_agent.validate_video_output(video_data, content_data)
            stage_scores['video_generation'] = video_report.overall_score
            stage_reports['video_generation'] = video_report
            all_issues.extend(video_report.issues)
            all_recommendations.extend(video_report.recommendations)
            
            # Check quality gate
            min_score = self.quality_gates['video_generation']['min_score']
            if video_report.overall_score >= min_score:
                passed_gates.append('video_generation')
            else:
                failed_gates.append('video_generation')
                if self.quality_gates['video_generation']['critical']:
                    all_issues.append(f"CRITICAL: Video quality below threshold ({video_report.overall_score:.2f} < {min_score})")
        
        # 4. Validate episode discovery if data provided
        if discovery_data:
            discovery_report = self.discovery_agent.validate_episode_discovery(discovery_data, show_name)
            stage_scores['episode_discovery'] = discovery_report.overall_score
            stage_reports['episode_discovery'] = discovery_report
            all_issues.extend(discovery_report.issues)
            all_recommendations.extend(discovery_report.recommendations)
            
            # Check quality gate
            min_score = self.quality_gates['episode_discovery']['min_score']
            if discovery_report.overall_score >= min_score:
                passed_gates.append('episode_discovery')
            else:
                failed_gates.append('episode_discovery')
                if self.quality_gates['episode_discovery']['critical']:
                    all_issues.append(f"CRITICAL: Discovery quality below threshold ({discovery_report.overall_score:.2f} < {min_score})")
        
        # 5. Validate workflow execution if data provided
        if workflow_data:
            workflow_report = self.workflow_agent.validate_workflow_execution(workflow_data)
            stage_scores['workflow_execution'] = workflow_report.overall_score
            stage_reports['workflow_execution'] = workflow_report
            all_issues.extend(workflow_report.issues)
            all_recommendations.extend(workflow_report.recommendations)
            
            # Check quality gate
            min_score = self.quality_gates['workflow_execution']['min_score']
            if workflow_report.overall_score >= min_score:
                passed_gates.append('workflow_execution')
            else:
                failed_gates.append('workflow_execution')
                if self.quality_gates['workflow_execution']['critical']:
                    all_issues.append(f"CRITICAL: Workflow quality below threshold ({workflow_report.overall_score:.2f} < {min_score})")
        
        # Calculate overall score
        if stage_scores:
            # Weight scores by importance
            weights = {
                'transcript_discovery': 0.20,
                'content_generation': 0.25,
                'video_generation': 0.25,
                'episode_discovery': 0.15,
                'workflow_execution': 0.15
            }
            
            weighted_sum = 0
            total_weight = 0
            
            for stage, score in stage_scores.items():
                weight = weights.get(stage, 0.1)
                weighted_sum += score * weight
                total_weight += weight
            
            overall_score = weighted_sum / total_weight if total_weight > 0 else 0
        else:
            overall_score = 0
        
        # Identify critical issues
        critical_issues = [issue for issue in all_issues if issue.startswith('CRITICAL:')]
        
        # Remove duplicates while preserving order
        unique_issues = list(dict.fromkeys(all_issues))
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        
        # Analyze quality trends
        quality_trends = self._analyze_quality_trends(stage_scores)
        
        # Store quality data for historical analysis
        quality_record = {
            'timestamp': datetime.now(),
            'overall_score': overall_score,
            'stage_scores': stage_scores,
            'show_name': show_name,
            'passed_gates': len(passed_gates),
            'failed_gates': len(failed_gates)
        }
        self.quality_history.append(quality_record)
        
        # Keep only last 100 records
        if len(self.quality_history) > 100:
            self.quality_history = self.quality_history[-100:]
        
        return UnifiedQualityReport(
            overall_score=overall_score,
            stage_scores=stage_scores,
            stage_reports=stage_reports,
            critical_issues=critical_issues,
            recommendations=unique_recommendations[:15],  # Limit to top 15
            quality_trends=quality_trends,
            passed_quality_gates=passed_gates,
            failed_quality_gates=failed_gates
        )
    
    def validate_stage_quality(self, stage: str, data: Dict, context: Dict = None) -> Any:
        """
        Validate quality for a specific workflow stage.
        
        Args:
            stage: Stage name ('transcript', 'content', 'video', 'discovery', 'workflow')
            data: Stage-specific data to validate
            context: Additional context for validation
            
        Returns:
            Stage-specific quality report
        """
        context = context or {}
        
        if stage == 'transcript':
            return self.transcript_agent.validate_transcript_discovery(data)
        elif stage == 'content':
            original_transcript = context.get('original_transcript', '')
            return self.content_agent.validate_ai_content(data, original_transcript)
        elif stage == 'video':
            content_source = context.get('content_source', {})
            return self.video_agent.validate_video_output(data, content_source)
        elif stage == 'discovery':
            show_name = context.get('show_name', '')
            return self.discovery_agent.validate_episode_discovery(data, show_name)
        elif stage == 'workflow':
            return self.workflow_agent.validate_workflow_execution(data)
        else:
            raise ValueError(f"Unknown stage: {stage}")
    
    def check_quality_gates(self, stage_scores: Dict[str, float]) -> Dict[str, bool]:
        """
        Check if quality gates are met for given scores.
        
        Args:
            stage_scores: Dictionary of stage names to quality scores
            
        Returns:
            Dictionary of stage names to gate pass/fail status
        """
        gate_results = {}
        
        for stage, score in stage_scores.items():
            if stage in self.quality_gates:
                min_score = self.quality_gates[stage]['min_score']
                gate_results[stage] = score >= min_score
            else:
                gate_results[stage] = True  # No gate defined, assume pass
        
        return gate_results
    
    def get_quality_recommendations(self, unified_report: UnifiedQualityReport) -> List[str]:
        """
        Get prioritized quality improvement recommendations.
        
        Args:
            unified_report: Unified quality report
            
        Returns:
            List of prioritized recommendations
        """
        recommendations = []
        
        # Critical issues first
        if unified_report.failed_quality_gates:
            critical_gates = [gate for gate in unified_report.failed_quality_gates 
                            if self.quality_gates.get(gate, {}).get('critical', False)]
            if critical_gates:
                recommendations.append(f"URGENT: Address critical quality gates: {', '.join(critical_gates)}")
        
        # Stage-specific recommendations based on lowest scores
        sorted_stages = sorted(unified_report.stage_scores.items(), key=lambda x: x[1])
        
        for stage, score in sorted_stages[:3]:  # Focus on worst 3 stages
            if score < 0.7:
                if stage == 'transcript_discovery':
                    recommendations.append("Improve transcript source selection and validation")
                elif stage == 'content_generation':
                    recommendations.append("Enhance AI content generation prompts and validation")
                elif stage == 'video_generation':
                    recommendations.append("Optimize video generation parameters and quality checks")
                elif stage == 'episode_discovery':
                    recommendations.append("Expand episode discovery sources and metadata validation")
                elif stage == 'workflow_execution':
                    recommendations.append("Optimize workflow coordination and error handling")
        
        # Add general recommendations
        if unified_report.overall_score < 0.8:
            recommendations.append("Consider implementing additional quality checkpoints")
        
        # Remove duplicates and limit
        unique_recommendations = list(dict.fromkeys(recommendations))
        return unique_recommendations[:10]
    
    def _analyze_quality_trends(self, current_scores: Dict[str, float]) -> Dict[str, Any]:
        """Analyze quality trends based on historical data."""
        trends = {}
        
        if len(self.quality_history) < 2:
            return {'status': 'insufficient_data', 'message': 'Need more data for trend analysis'}
        
        # Calculate recent averages
        recent_records = self.quality_history[-10:]  # Last 10 records
        
        for stage in current_scores.keys():
            stage_history = [record['stage_scores'].get(stage, 0) for record in recent_records 
                           if stage in record['stage_scores']]
            
            if len(stage_history) >= 2:
                recent_avg = sum(stage_history) / len(stage_history)
                current_score = current_scores[stage]
                
                if current_score > recent_avg * 1.1:
                    trend = 'improving'
                elif current_score < recent_avg * 0.9:
                    trend = 'declining'
                else:
                    trend = 'stable'
                
                trends[stage] = {
                    'trend': trend,
                    'current_score': current_score,
                    'recent_average': recent_avg,
                    'change_percent': ((current_score - recent_avg) / recent_avg) * 100
                }
        
        # Overall trend analysis
        overall_history = [record['overall_score'] for record in recent_records]
        if overall_history:
            overall_avg = sum(overall_history) / len(overall_history)
            current_overall = sum(current_scores.values()) / len(current_scores) if current_scores else 0
            
            trends['overall'] = {
                'trend': 'improving' if current_overall > overall_avg * 1.05 else 
                        'declining' if current_overall < overall_avg * 0.95 else 'stable',
                'current_score': current_overall,
                'recent_average': overall_avg
            }
        
        return trends
    
    def get_quality_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for quality monitoring dashboard.
        
        Returns:
            Dictionary with dashboard data
        """
        if not self.quality_history:
            return {'status': 'no_data', 'message': 'No quality data available'}
        
        recent_records = self.quality_history[-20:]  # Last 20 records
        
        # Calculate averages
        stage_averages = {}
        all_stages = set()
        for record in recent_records:
            all_stages.update(record['stage_scores'].keys())
        
        for stage in all_stages:
            scores = [record['stage_scores'].get(stage, 0) for record in recent_records 
                     if stage in record['stage_scores']]
            stage_averages[stage] = sum(scores) / len(scores) if scores else 0
        
        # Quality gate pass rates
        gate_pass_rates = {}
        for stage in all_stages:
            if stage in self.quality_gates:
                min_score = self.quality_gates[stage]['min_score']
                passes = sum(1 for record in recent_records 
                           if record['stage_scores'].get(stage, 0) >= min_score)
                gate_pass_rates[stage] = passes / len(recent_records) if recent_records else 0
        
        # Recent trends
        recent_trend = 'stable'
        if len(recent_records) >= 5:
            early_avg = sum(record['overall_score'] for record in recent_records[:5]) / 5
            late_avg = sum(record['overall_score'] for record in recent_records[-5:]) / 5
            
            if late_avg > early_avg * 1.1:
                recent_trend = 'improving'
            elif late_avg < early_avg * 0.9:
                recent_trend = 'declining'
        
        return {
            'total_evaluations': len(self.quality_history),
            'recent_evaluations': len(recent_records),
            'stage_averages': stage_averages,
            'gate_pass_rates': gate_pass_rates,
            'recent_trend': recent_trend,
            'last_evaluation': self.quality_history[-1]['timestamp'].isoformat() if self.quality_history else None,
            'quality_gates_config': self.quality_gates
        }
