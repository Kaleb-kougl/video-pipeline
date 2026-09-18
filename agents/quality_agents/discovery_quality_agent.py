"""
Discovery Quality Agent - Validates episode discovery and metadata quality.
"""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryQualityReport:
    """Quality report for episode discovery results."""
    overall_score: float
    metadata_completeness: float
    data_accuracy: float
    source_reliability: float
    consistency_score: float
    freshness_score: float
    issues: List[str]
    recommendations: List[str]
    
    @property
    def is_acceptable(self) -> bool:
        """Returns True if discovery meets minimum quality standards."""
        return self.overall_score >= 0.6


class DiscoveryQualityAgent:
    """Agent responsible for validating episode discovery quality."""
    
    def __init__(self):
        """Initialize the discovery quality agent."""
        self.required_fields = ['title', 'season', 'episode', 'url']
        self.optional_fields = ['air_date', 'description', 'duration', 'rating']
        self.trusted_sources = [
            'fandom.com', 'wikia.com', 'imdb.com', 'tvdb.com',
            'anidb.net', 'myanimelist.net'
        ]
        self.title_pattern = re.compile(r'^[A-Za-z0-9\s\-:!\?\.\'\"]+$')
        
    def validate_episode_discovery(self, discovery_data: Dict, show_name: str = "") -> DiscoveryQualityReport:
        """
        Validate the quality of episode discovery results.
        
        Args:
            discovery_data: Dictionary containing discovered episode data
            show_name: Name of the show for context
            
        Returns:
            DiscoveryQualityReport: Detailed quality assessment
        """
        issues = []
        recommendations = []
        
        logger.info(f"Validating episode discovery for: {show_name}")
        
        # 1. Metadata completeness validation
        completeness_score = self._assess_metadata_completeness(discovery_data, issues, recommendations)
        
        # 2. Data accuracy validation
        accuracy_score = self._assess_data_accuracy(discovery_data, show_name, issues, recommendations)
        
        # 3. Source reliability validation
        reliability_score = self._assess_source_reliability(discovery_data, issues, recommendations)
        
        # 4. Consistency validation
        consistency_score = self._assess_data_consistency(discovery_data, issues, recommendations)
        
        # 5. Data freshness validation
        freshness_score = self._assess_data_freshness(discovery_data, issues, recommendations)
        
        # Calculate overall score
        weights = {
            'completeness': 0.25,
            'accuracy': 0.25,
            'reliability': 0.20,
            'consistency': 0.20,
            'freshness': 0.10
        }
        
        overall_score = (
            completeness_score * weights['completeness'] +
            accuracy_score * weights['accuracy'] +
            reliability_score * weights['reliability'] +
            consistency_score * weights['consistency'] +
            freshness_score * weights['freshness']
        )
        
        return DiscoveryQualityReport(
            overall_score=overall_score,
            metadata_completeness=completeness_score,
            data_accuracy=accuracy_score,
            source_reliability=reliability_score,
            consistency_score=consistency_score,
            freshness_score=freshness_score,
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_metadata_completeness(self, discovery_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess completeness of discovered metadata."""
        score = 1.0
        
        # Check required fields
        missing_required = []
        for field in self.required_fields:
            if field not in discovery_data or not discovery_data[field]:
                missing_required.append(field)
        
        if missing_required:
            score -= 0.2 * len(missing_required)
            issues.append(f"Missing required fields: {', '.join(missing_required)}")
            recommendations.append("Ensure all required metadata fields are collected")
        
        # Check optional fields (bonus for completeness)
        present_optional = sum(1 for field in self.optional_fields 
                             if field in discovery_data and discovery_data[field])
        optional_bonus = (present_optional / len(self.optional_fields)) * 0.2
        score = min(1.0, score + optional_bonus)
        
        if present_optional < len(self.optional_fields) * 0.5:
            recommendations.append("Try to collect more optional metadata for better quality")
        
        # Check field content quality
        for field, value in discovery_data.items():
            if isinstance(value, str):
                if len(value.strip()) == 0:
                    score -= 0.05
                    issues.append(f"Empty string value for field: {field}")
                elif len(value) < 3:
                    score -= 0.03
                    issues.append(f"Very short value for field {field}: '{value}'")
        
        return max(0.0, score)
    
    def _assess_data_accuracy(self, discovery_data: Dict, show_name: str, issues: List[str], recommendations: List[str]) -> float:
        """Assess accuracy of discovered data."""
        score = 1.0
        
        # Validate episode title format
        title = discovery_data.get('title', '')
        if title:
            if not self.title_pattern.match(title):
                score -= 0.1
                issues.append(f"Title contains unusual characters: '{title}'")
                recommendations.append("Verify title accuracy from multiple sources")
            
            if len(title) > 100:
                score -= 0.05
                issues.append("Episode title unusually long")
                recommendations.append("Check if title includes extra information")
        
        # Validate season/episode numbers
        season = discovery_data.get('season')
        episode = discovery_data.get('episode')
        
        if season is not None:
            try:
                season_num = int(season)
                if season_num < 1 or season_num > 50:
                    score -= 0.1
                    issues.append(f"Unusual season number: {season_num}")
                    recommendations.append("Verify season number accuracy")
            except (ValueError, TypeError):
                score -= 0.2
                issues.append(f"Invalid season format: {season}")
                recommendations.append("Ensure season is a valid number")
        
        if episode is not None:
            try:
                episode_num = int(episode)
                if episode_num < 1 or episode_num > 200:
                    score -= 0.1
                    issues.append(f"Unusual episode number: {episode_num}")
                    recommendations.append("Verify episode number accuracy")
            except (ValueError, TypeError):
                score -= 0.2
                issues.append(f"Invalid episode format: {episode}")
                recommendations.append("Ensure episode is a valid number")
        
        # Validate URL format
        url = discovery_data.get('url', '')
        if url:
            if not url.startswith(('http://', 'https://')):
                score -= 0.15
                issues.append("URL missing proper protocol")
                recommendations.append("Ensure URLs include http/https protocol")
            
            if len(url) > 500:
                score -= 0.05
                issues.append("URL unusually long")
                recommendations.append("Check for URL parameter issues")
        
        # Validate air date format
        air_date = discovery_data.get('air_date', '')
        if air_date:
            if not self._validate_date_format(air_date):
                score -= 0.1
                issues.append(f"Invalid air date format: {air_date}")
                recommendations.append("Use standard date format (YYYY-MM-DD)")
        
        # Check show name consistency
        if show_name and title:
            show_words = set(show_name.lower().split())
            title_words = set(title.lower().split())
            
            # Check if show name appears in title (common pattern)
            common_words = show_words.intersection(title_words)
            if len(common_words) == 0 and len(show_words) > 1:
                score -= 0.05
                issues.append("Episode title may not match show name")
                recommendations.append("Verify episode belongs to correct show")
        
        return max(0.0, score)
    
    def _assess_source_reliability(self, discovery_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess reliability of the data source."""
        score = 1.0
        
        url = discovery_data.get('url', '').lower()
        source = discovery_data.get('source', '').lower()
        
        # Check for trusted sources
        is_trusted = any(trusted in url for trusted in self.trusted_sources)
        
        if is_trusted:
            score += 0.0  # Already at max, but this is good
        else:
            score -= 0.2
            issues.append("Source not in trusted list")
            recommendations.append("Cross-reference with trusted sources when possible")
        
        # Check for specific reliability indicators
        unreliable_indicators = [
            'user-generated', 'fan-made', 'unofficial', 'unverified',
            'wiki.', 'blogspot.', 'wordpress.', 'tumblr.'
        ]
        
        for indicator in unreliable_indicators:
            if indicator in url or indicator in source:
                score -= 0.1
                issues.append(f"Source may be unreliable: contains '{indicator}'")
                recommendations.append("Verify information with official sources")
                break
        
        # Check for missing source information
        if not url and not source:
            score -= 0.3
            issues.append("No source information provided")
            recommendations.append("Always include source URLs for traceability")
        
        return max(0.0, score)
    
    def _assess_data_consistency(self, discovery_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess internal consistency of the data."""
        score = 1.0
        
        # Check season/episode consistency
        season = discovery_data.get('season')
        episode = discovery_data.get('episode')
        title = discovery_data.get('title', '')
        
        if season and episode and title:
            # Look for season/episode indicators in title
            season_patterns = [
                rf'season\s*{season}',
                rf's{season}',
                rf'{season}x{episode}',
                rf's{season}e{episode}'
            ]
            
            episode_patterns = [
                rf'episode\s*{episode}',
                rf'ep\s*{episode}',
                rf'e{episode}'
            ]
            
            title_lower = title.lower()
            has_season_indicator = any(re.search(pattern, title_lower) for pattern in season_patterns)
            has_episode_indicator = any(re.search(pattern, title_lower) for pattern in episode_patterns)
            
            if not has_season_indicator and not has_episode_indicator:
                score -= 0.1
                issues.append("Title doesn't contain season/episode indicators")
                recommendations.append("Verify title matches season/episode numbers")
        
        # Check URL consistency with metadata
        url = discovery_data.get('url', '').lower()
        if url and season and episode:
            url_has_season = any(str(season) in url or f's{season}' in url or f'season{season}' in url for season in [season])
            url_has_episode = any(str(episode) in url or f'e{episode}' in url or f'episode{episode}' in url for episode in [episode])
            
            if not url_has_season and not url_has_episode:
                score -= 0.05
                issues.append("URL may not match season/episode numbers")
                recommendations.append("Verify URL corresponds to correct episode")
        
        # Check description consistency
        description = discovery_data.get('description', '')
        if description and title:
            # Very basic check - description shouldn't be identical to title
            if description.strip() == title.strip():
                score -= 0.05
                issues.append("Description identical to title")
                recommendations.append("Ensure description provides additional context")
        
        return max(0.0, score)
    
    def _assess_data_freshness(self, discovery_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess how fresh/recent the discovered data is."""
        score = 1.0
        
        # Check if there's a discovery timestamp
        discovery_time = discovery_data.get('discovery_timestamp')
        if discovery_time:
            try:
                if isinstance(discovery_time, str):
                    discovery_dt = datetime.fromisoformat(discovery_time.replace('Z', '+00:00'))
                else:
                    discovery_dt = discovery_time
                
                age_hours = (datetime.now() - discovery_dt).total_seconds() / 3600
                
                if age_hours > 24 * 7:  # Older than a week
                    score -= 0.2
                    issues.append("Discovery data is more than a week old")
                    recommendations.append("Consider re-discovering for updated information")
                elif age_hours > 24:  # Older than a day
                    score -= 0.1
                    issues.append("Discovery data is more than a day old")
                    recommendations.append("May want to refresh for latest information")
                    
            except (ValueError, TypeError):
                score -= 0.1
                issues.append("Invalid discovery timestamp format")
                recommendations.append("Use proper timestamp format for tracking freshness")
        else:
            score -= 0.1
            issues.append("No discovery timestamp provided")
            recommendations.append("Include discovery timestamps for data freshness tracking")
        
        # Check air date relevance
        air_date = discovery_data.get('air_date')
        if air_date and self._validate_date_format(air_date):
            try:
                air_dt = datetime.strptime(air_date, '%Y-%m-%d')
                future_days = (air_dt - datetime.now()).days
                
                if future_days > 365:  # More than a year in the future
                    score -= 0.1
                    issues.append("Air date is far in the future")
                    recommendations.append("Verify air date accuracy")
                    
            except ValueError:
                pass  # Already handled in accuracy assessment
        
        return max(0.0, score)
    
    def _validate_date_format(self, date_string: str) -> bool:
        """Validate if date string is in acceptable format."""
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%d %B %Y'
        ]
        
        for fmt in date_formats:
            try:
                datetime.strptime(date_string, fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    def validate_discovery_batch(self, discovery_results: List[Dict], show_name: str = "") -> Dict:
        """
        Validate a batch of episode discovery results.
        
        Args:
            discovery_results: List of episode discovery results
            show_name: Name of the show for context
            
        Returns:
            Dictionary with batch validation summary
        """
        if not discovery_results:
            return {
                'overall_quality': 0.0,
                'acceptable_count': 0,
                'total_count': 0,
                'issues': ['No episodes discovered'],
                'recommendations': ['Check discovery parameters and sources']
            }
        
        reports = [self.validate_episode_discovery(result, show_name) for result in discovery_results]
        acceptable_reports = [r for r in reports if r.is_acceptable]
        
        overall_quality = sum(r.overall_score for r in reports) / len(reports)
        
        # Check for season/episode sequence consistency
        seasons_episodes = []
        for result in discovery_results:
            season = result.get('season')
            episode = result.get('episode')
            if season is not None and episode is not None:
                try:
                    seasons_episodes.append((int(season), int(episode)))
                except (ValueError, TypeError):
                    pass
        
        sequence_issues = self._check_sequence_consistency(seasons_episodes)
        
        # Aggregate issues and recommendations
        all_issues = []
        all_recommendations = []
        for report in reports:
            all_issues.extend(report.issues)
            all_recommendations.extend(report.recommendations)
        
        all_issues.extend(sequence_issues)
        if sequence_issues:
            all_recommendations.append("Review episode sequence for gaps or duplicates")
        
        unique_issues = list(dict.fromkeys(all_issues))
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        
        return {
            'overall_quality': overall_quality,
            'acceptable_count': len(acceptable_reports),
            'total_count': len(reports),
            'quality_distribution': {
                'excellent': len([r for r in reports if r.overall_score >= 0.8]),
                'good': len([r for r in reports if 0.6 <= r.overall_score < 0.8]),
                'poor': len([r for r in reports if r.overall_score < 0.6])
            },
            'average_scores': {
                'metadata_completeness': sum(r.metadata_completeness for r in reports) / len(reports),
                'data_accuracy': sum(r.data_accuracy for r in reports) / len(reports),
                'source_reliability': sum(r.source_reliability for r in reports) / len(reports),
                'consistency_score': sum(r.consistency_score for r in reports) / len(reports),
                'freshness_score': sum(r.freshness_score for r in reports) / len(reports)
            },
            'sequence_analysis': {
                'total_episodes': len(seasons_episodes),
                'unique_seasons': len(set(s for s, e in seasons_episodes)),
                'sequence_issues': sequence_issues
            },
            'issues': unique_issues[:10],
            'recommendations': unique_recommendations[:10],
            'detailed_reports': reports
        }
    
    def _check_sequence_consistency(self, seasons_episodes: List[Tuple[int, int]]) -> List[str]:
        """Check for consistency in season/episode sequences."""
        issues = []
        
        if not seasons_episodes:
            return issues
        
        # Group by season
        by_season = {}
        for season, episode in seasons_episodes:
            if season not in by_season:
                by_season[season] = []
            by_season[season].append(episode)
        
        # Check each season for gaps or duplicates
        for season, episodes in by_season.items():
            episodes_sorted = sorted(episodes)
            
            # Check for duplicates
            if len(episodes) != len(set(episodes)):
                duplicates = [ep for ep in set(episodes) if episodes.count(ep) > 1]
                issues.append(f"Season {season} has duplicate episodes: {duplicates}")
            
            # Check for gaps in sequence
            if len(episodes_sorted) > 1:
                expected_range = list(range(episodes_sorted[0], episodes_sorted[-1] + 1))
                missing_episodes = set(expected_range) - set(episodes_sorted)
                if missing_episodes:
                    issues.append(f"Season {season} missing episodes: {sorted(missing_episodes)}")
        
        return issues
