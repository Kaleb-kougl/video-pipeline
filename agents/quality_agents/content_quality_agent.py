"""
Content Quality Agent - Validates AI-generated content quality.
"""

import re
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContentQualityReport:
    """Quality report for AI-generated content."""
    overall_score: float
    script_coherence: float
    scene_descriptions: float
    character_consistency: float
    dialogue_quality: float
    visual_descriptions: float
    technical_accuracy: float
    issues: List[str]
    recommendations: List[str]
    
    @property
    def is_acceptable(self) -> bool:
        """Returns True if content meets minimum quality standards."""
        return self.overall_score >= 0.7


class ContentQualityAgent:
    """Agent responsible for validating AI-generated content quality."""
    
    def __init__(self):
        """Initialize the content quality agent."""
        self.required_sections = ['scenes', 'characters', 'dialogue', 'visual_elements']
        self.min_scene_count = 3
        self.max_scene_count = 50
        self.character_name_patterns = re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b|\b[A-Z]{2,}\b')
        
    def validate_ai_content(self, content_data: Dict, original_transcript: str = "") -> ContentQualityReport:
        """
        Validate the quality of AI-generated content.
        
        Args:
            content_data: Dictionary containing AI-generated content
            original_transcript: Original transcript for comparison
            
        Returns:
            ContentQualityReport: Detailed quality assessment
        """
        issues = []
        recommendations = []
        
        logger.info("Validating AI-generated content quality")
        
        # 1. Script coherence validation
        coherence_score = self._assess_script_coherence(content_data, issues, recommendations)
        
        # 2. Scene descriptions validation
        scene_score = self._assess_scene_descriptions(content_data, issues, recommendations)
        
        # 3. Character consistency validation
        character_score = self._assess_character_consistency(content_data, original_transcript, issues, recommendations)
        
        # 4. Dialogue quality validation
        dialogue_score = self._assess_dialogue_quality(content_data, issues, recommendations)
        
        # 5. Visual descriptions validation
        visual_score = self._assess_visual_descriptions(content_data, issues, recommendations)
        
        # 6. Technical accuracy validation
        technical_score = self._assess_technical_accuracy(content_data, issues, recommendations)
        
        # Calculate overall score
        weights = {
            'coherence': 0.25,
            'scenes': 0.20,
            'characters': 0.20,
            'dialogue': 0.15,
            'visual': 0.15,
            'technical': 0.05
        }
        
        overall_score = (
            coherence_score * weights['coherence'] +
            scene_score * weights['scenes'] +
            character_score * weights['characters'] +
            dialogue_score * weights['dialogue'] +
            visual_score * weights['visual'] +
            technical_score * weights['technical']
        )
        
        return ContentQualityReport(
            overall_score=overall_score,
            script_coherence=coherence_score,
            scene_descriptions=scene_score,
            character_consistency=character_score,
            dialogue_quality=dialogue_score,
            visual_descriptions=visual_score,
            technical_accuracy=technical_score,
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_script_coherence(self, content_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess overall script coherence and structure."""
        score = 1.0
        
        # Check for required sections
        missing_sections = []
        for section in self.required_sections:
            if section not in content_data or not content_data[section]:
                missing_sections.append(section)
        
        if missing_sections:
            score -= 0.1 * len(missing_sections)
            issues.append(f"Missing required sections: {', '.join(missing_sections)}")
            recommendations.append("Regenerate content with all required sections")
        
        # Check scene count
        scenes = content_data.get('scenes', [])
        if isinstance(scenes, list):
            scene_count = len(scenes)
            if scene_count < self.min_scene_count:
                score -= 0.3
                issues.append(f"Too few scenes: {scene_count} (min: {self.min_scene_count})")
                recommendations.append("Break content into more detailed scenes")
            elif scene_count > self.max_scene_count:
                score -= 0.2
                issues.append(f"Too many scenes: {scene_count} (max: {self.max_scene_count})")
                recommendations.append("Consolidate similar scenes")
        
        # Check for logical flow
        if isinstance(scenes, list) and len(scenes) > 1:
            flow_issues = self._check_scene_flow(scenes)
            if flow_issues:
                score -= 0.1 * len(flow_issues)
                issues.extend(flow_issues)
                recommendations.append("Review scene transitions for logical flow")
        
        return max(0.0, score)
    
    def _assess_scene_descriptions(self, content_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess quality of scene descriptions."""
        score = 1.0
        scenes = content_data.get('scenes', [])
        
        if not scenes:
            issues.append("No scenes found in content")
            recommendations.append("Generate proper scene breakdown")
            return 0.0
        
        inadequate_scenes = 0
        for i, scene in enumerate(scenes):
            if isinstance(scene, dict):
                description = scene.get('description', '')
                if len(description) < 50:
                    inadequate_scenes += 1
            elif isinstance(scene, str):
                if len(scene) < 50:
                    inadequate_scenes += 1
        
        if inadequate_scenes > 0:
            ratio = inadequate_scenes / len(scenes)
            score -= ratio * 0.5
            issues.append(f"{inadequate_scenes} scenes have inadequate descriptions")
            recommendations.append("Expand scene descriptions with more visual detail")
        
        # Check for visual richness
        visual_keywords = ['shows', 'appears', 'looks', 'wearing', 'background', 'lighting', 'color', 'movement']
        total_visual_mentions = 0
        
        for scene in scenes:
            scene_text = str(scene).lower()
            total_visual_mentions += sum(scene_text.count(keyword) for keyword in visual_keywords)
        
        visual_density = total_visual_mentions / len(scenes) if scenes else 0
        if visual_density < 2:
            score -= 0.2
            issues.append("Scenes lack sufficient visual descriptions")
            recommendations.append("Add more visual details for video generation")
        
        return max(0.0, score)
    
    def _assess_character_consistency(self, content_data: Dict, original_transcript: str, issues: List[str], recommendations: List[str]) -> float:
        """Assess character consistency between original and generated content."""
        score = 1.0
        
        # Extract characters from original transcript
        original_characters = self._extract_characters(original_transcript)
        
        # Extract characters from generated content
        generated_characters = set()
        characters_section = content_data.get('characters', [])
        
        if isinstance(characters_section, list):
            for char in characters_section:
                if isinstance(char, dict):
                    generated_characters.add(char.get('name', '').strip())
                elif isinstance(char, str):
                    generated_characters.add(char.strip())
        
        # Check for character consistency
        if original_characters:
            missing_chars = original_characters - generated_characters
            extra_chars = generated_characters - original_characters
            
            if missing_chars:
                score -= 0.2
                issues.append(f"Missing characters from original: {', '.join(list(missing_chars)[:5])}")
                recommendations.append("Include all major characters from the original transcript")
            
            if len(extra_chars) > len(original_characters) * 0.5:
                score -= 0.1
                issues.append("Too many additional characters introduced")
                recommendations.append("Focus on main characters from the original content")
        
        # Check character development
        if isinstance(characters_section, list):
            underdeveloped_chars = 0
            for char in characters_section:
                if isinstance(char, dict):
                    description = char.get('description', '')
                    if len(description) < 30:
                        underdeveloped_chars += 1
            
            if underdeveloped_chars > 0:
                score -= 0.1
                issues.append(f"{underdeveloped_chars} characters lack proper descriptions")
                recommendations.append("Provide more detailed character descriptions")
        
        return max(0.0, score)
    
    def _assess_dialogue_quality(self, content_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess quality of dialogue in generated content."""
        score = 1.0
        
        # Extract dialogue from scenes
        all_dialogue = []
        scenes = content_data.get('scenes', [])
        
        for scene in scenes:
            if isinstance(scene, dict):
                dialogue = scene.get('dialogue', [])
                if isinstance(dialogue, list):
                    all_dialogue.extend(dialogue)
                elif isinstance(dialogue, str):
                    all_dialogue.append(dialogue)
        
        if not all_dialogue:
            issues.append("No dialogue found in generated content")
            recommendations.append("Include character dialogue in scene descriptions")
            return 0.3
        
        # Check dialogue quality metrics
        short_lines = sum(1 for line in all_dialogue if len(str(line)) < 20)
        if short_lines > len(all_dialogue) * 0.7:
            score -= 0.2
            issues.append("Too many very short dialogue lines")
            recommendations.append("Expand dialogue with more natural conversation")
        
        # Check for character voice consistency
        character_dialogue = {}
        for line in all_dialogue:
            if isinstance(line, dict) and 'character' in line:
                char = line['character']
                if char not in character_dialogue:
                    character_dialogue[char] = []
                character_dialogue[char].append(line.get('text', ''))
        
        # Check if major characters have sufficient dialogue
        if len(character_dialogue) < 2:
            score -= 0.1
            issues.append("Limited character dialogue variety")
            recommendations.append("Include dialogue from multiple characters")
        
        return max(0.0, score)
    
    def _assess_visual_descriptions(self, content_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess quality of visual descriptions for video generation."""
        score = 1.0
        
        visual_elements = content_data.get('visual_elements', [])
        scenes = content_data.get('scenes', [])
        
        # Check for visual elements section
        if not visual_elements:
            score -= 0.3
            issues.append("No visual elements section found")
            recommendations.append("Include detailed visual elements for video generation")
        
        # Check visual richness in scenes
        visual_keywords = [
            'background', 'setting', 'location', 'lighting', 'color', 'costume',
            'expression', 'gesture', 'movement', 'camera', 'angle', 'shot'
        ]
        
        total_visual_density = 0
        for scene in scenes:
            scene_text = str(scene).lower()
            visual_count = sum(scene_text.count(keyword) for keyword in visual_keywords)
            total_visual_density += visual_count
        
        if scenes:
            avg_visual_density = total_visual_density / len(scenes)
            if avg_visual_density < 3:
                score -= 0.2
                issues.append("Insufficient visual details for video generation")
                recommendations.append("Add more specific visual descriptions (settings, costumes, expressions)")
        
        # Check for technical video specifications
        technical_specs = ['resolution', 'duration', 'transitions', 'effects']
        missing_specs = [spec for spec in technical_specs if spec not in str(content_data).lower()]
        
        if len(missing_specs) > 2:
            score -= 0.1
            issues.append("Missing technical video specifications")
            recommendations.append("Include video technical details (duration, transitions, effects)")
        
        return max(0.0, score)
    
    def _assess_technical_accuracy(self, content_data: Dict, issues: List[str], recommendations: List[str]) -> float:
        """Assess technical accuracy of the generated content structure."""
        score = 1.0
        
        # Check JSON/data structure validity
        try:
            # Verify all sections are properly structured
            for section_name in ['scenes', 'characters', 'dialogue', 'visual_elements']:
                section = content_data.get(section_name)
                if section is not None and not isinstance(section, (list, dict, str)):
                    score -= 0.2
                    issues.append(f"Invalid data type for {section_name} section")
                    recommendations.append(f"Ensure {section_name} section uses proper data structure")
        except Exception as e:
            score -= 0.3
            issues.append(f"Content structure error: {str(e)}")
            recommendations.append("Fix content data structure and formatting")
        
        # Check for required fields in scenes
        scenes = content_data.get('scenes', [])
        if isinstance(scenes, list):
            required_scene_fields = ['description']
            for i, scene in enumerate(scenes):
                if isinstance(scene, dict):
                    missing_fields = [field for field in required_scene_fields if field not in scene]
                    if missing_fields:
                        score -= 0.05
                        issues.append(f"Scene {i+1} missing fields: {', '.join(missing_fields)}")
        
        return max(0.0, score)
    
    def _extract_characters(self, text: str) -> Set[str]:
        """Extract character names from text."""
        characters = set()
        
        # Look for dialogue patterns (Character: dialogue)
        dialogue_pattern = re.compile(r'^([A-Z][A-Za-z\s]+?):', re.MULTILINE)
        matches = dialogue_pattern.findall(text)
        characters.update(match.strip() for match in matches)
        
        # Look for character name patterns
        name_matches = self.character_name_patterns.findall(text)
        characters.update(name_matches)
        
        # Filter out common false positives
        false_positives = {'SCENE', 'CUT TO', 'FADE IN', 'FADE OUT', 'INT', 'EXT', 'NARRATOR'}
        characters = {char for char in characters if char.upper() not in false_positives and len(char) > 2}
        
        return characters
    
    def _check_scene_flow(self, scenes: List) -> List[str]:
        """Check for logical flow between scenes."""
        flow_issues = []
        
        for i in range(len(scenes) - 1):
            current_scene = str(scenes[i]).lower()
            next_scene = str(scenes[i + 1]).lower()
            
            # Check for abrupt transitions
            transition_words = ['then', 'next', 'meanwhile', 'later', 'suddenly', 'after']
            has_transition = any(word in next_scene for word in transition_words)
            
            # Check for location continuity
            locations_current = re.findall(r'\b(?:room|house|school|street|park|building)\b', current_scene)
            locations_next = re.findall(r'\b(?:room|house|school|street|park|building)\b', next_scene)
            
            if locations_current and locations_next and locations_current != locations_next and not has_transition:
                flow_issues.append(f"Abrupt location change between scenes {i+1} and {i+2}")
        
        return flow_issues
    
    def validate_content_batch(self, content_results: List[Dict]) -> Dict:
        """
        Validate a batch of AI-generated content.
        
        Args:
            content_results: List of AI-generated content dictionaries
            
        Returns:
            Dictionary with batch validation summary
        """
        if not content_results:
            return {
                'overall_quality': 0.0,
                'acceptable_count': 0,
                'total_count': 0,
                'issues': ['No content generated'],
                'recommendations': ['Verify AI content generation process']
            }
        
        reports = [self.validate_ai_content(result) for result in content_results]
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
            'overall_quality': overall_quality,
            'acceptable_count': len(acceptable_reports),
            'total_count': len(reports),
            'quality_distribution': {
                'excellent': len([r for r in reports if r.overall_score >= 0.8]),
                'good': len([r for r in reports if 0.7 <= r.overall_score < 0.8]),
                'poor': len([r for r in reports if r.overall_score < 0.7])
            },
            'average_scores': {
                'script_coherence': sum(r.script_coherence for r in reports) / len(reports),
                'scene_descriptions': sum(r.scene_descriptions for r in reports) / len(reports),
                'character_consistency': sum(r.character_consistency for r in reports) / len(reports),
                'dialogue_quality': sum(r.dialogue_quality for r in reports) / len(reports),
                'visual_descriptions': sum(r.visual_descriptions for r in reports) / len(reports)
            },
            'issues': unique_issues[:10],
            'recommendations': unique_recommendations[:10],
            'detailed_reports': reports
        }
