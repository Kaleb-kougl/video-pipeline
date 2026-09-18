#!/usr/bin/env python3
"""
Transcript Discovery Beautiful Soup Validation Tool

This script validates the Beautiful Soup parsing implementation used in the transcript discovery
system against best practices and Context7 documentation. It tests different parsing scenarios
and provides recommendations for improvement.

Based on Context7 Beautiful Soup documentation:
- https://github.com/wention/beautifulsoup4
"""

import logging
import requests
from bs4 import BeautifulSoup, SoupStrainer
from typing import Dict, List, Optional, Any
import time
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TranscriptParsingValidator:
    """Validates Beautiful Soup parsing implementation for transcript discovery.
    
    This class provides comprehensive validation of HTML parsing techniques
    used in transcript discovery, ensuring adherence to best practices and
    optimal performance across different source websites.
    """
    
    def __init__(self):
        """Initialize the validator with test configurations.
        
        Sets up test sources, selectors, and best practices configuration
        for comprehensive validation of Beautiful Soup parsing implementation.
        """
        self.test_sources = {
            'subslikescript': {
                'base_url': 'https://subslikescript.com',
                'transcript_selector': '.full-script',
                'title_selector': 'h1',
                'search_result_selector': 'a[href*="series"]',
                'test_url': 'https://subslikescript.com/series/My_Hero_Academia-5626028/season-1/episode-1-Izuku_Midoriya_Origin'
            },
            'transcripts_wiki': {
                'base_url': 'https://transcripts.fandom.com',
                'transcript_selector': '.mw-parser-output',
                'title_selector': '.page-header__title',
                'search_result_selector': 'a[href*="/wiki/"]'
            }
        }
        
        # Best practices from Context7 documentation
        self.parsing_best_practices = {
            'use_explicit_parser': 'html.parser',  # Python's built-in parser
            'handle_encoding': True,
            'use_efficient_selectors': True,
            'validate_elements': True,
            'strip_whitespace': True
        }
    
    def validate_current_implementation(self, html_content: str) -> Dict[str, Any]:
        """
        Validate the current Beautiful Soup implementation against best practices.
        
        Args:
            html_content (str): HTML content to parse
            
        Returns:
            dict: Validation results with recommendations
        """
        logger.info("🔍 Validating current Beautiful Soup implementation...")
        
        results = {
            'parsing_success': False,
            'issues_found': [],
            'recommendations': [],
            'extracted_data': {},
            'performance_metrics': {}
        }
        
        try:
            start_time = time.time()
            
            # Test current implementation (from web_utils.py)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract title (current implementation)
            title = soup.find('h1')
            if title:
                title_text = title.get_text()
                results['extracted_data']['title'] = title_text
            else:
                results['issues_found'].append("Title element not found with current selector")
            
            # Extract transcript (current implementation)
            transcript_element = soup.find(class_="full-script")
            if transcript_element:
                transcript_text = transcript_element.get_text()
                results['extracted_data']['transcript'] = transcript_text[:200] + "..." if len(transcript_text) > 200 else transcript_text
                results['extracted_data']['transcript_length'] = len(transcript_text)
            else:
                results['issues_found'].append("Transcript element not found with current selector")
            
            parsing_time = time.time() - start_time
            results['performance_metrics']['parsing_time'] = parsing_time
            results['parsing_success'] = True
            
        except Exception as e:
            results['issues_found'].append(f"Parsing failed: {str(e)}")
        
        # Analyze implementation against best practices
        self._analyze_implementation(results)
        
        return results
    
    def validate_improved_implementation(self, html_content: str) -> Dict[str, Any]:
        """
        Test improved Beautiful Soup implementation using Context7 best practices.
        
        Args:
            html_content (str): HTML content to parse
            
        Returns:
            dict: Improved parsing results
        """
        logger.info("🚀 Testing improved Beautiful Soup implementation...")
        
        results = {
            'parsing_success': False,
            'improvements_applied': [],
            'extracted_data': {},
            'performance_metrics': {},
            'quality_scores': {}
        }
        
        try:
            start_time = time.time()
            
            # IMPROVEMENT 1: Use explicit parser specification (Context7 best practice)
            # BeautifulSoup(markup, "html.parser") - Python's built-in parser
            soup = BeautifulSoup(html_content, 'html.parser')
            results['improvements_applied'].append("Explicit parser specification")
            
            # IMPROVEMENT 2: Multiple selector strategies for robustness
            title_selectors = ['h1', '.page-title', '.episode-title', 'title']
            title_text = None
            
            for selector in title_selectors:
                title_element = soup.select_one(selector)
                if title_element:
                    # IMPROVEMENT 3: Use get_text() with strip parameter (Context7 recommendation)
                    title_text = title_element.get_text(strip=True)
                    results['improvements_applied'].append(f"Title found with selector: {selector}")
                    break
            
            results['extracted_data']['title'] = title_text
            
            # IMPROVEMENT 4: Multiple transcript selectors with quality scoring
            transcript_selectors = [
                '.full-script',
                '.mw-parser-output', 
                '.transcript-content',
                '.episode-transcript',
                'main',
                'article'
            ]
            
            best_transcript = None
            best_quality_score = 0
            
            for selector in transcript_selectors:
                elements = soup.select(selector)
                for element in elements:
                    # IMPROVEMENT 5: Content quality assessment
                    text_content = element.get_text(strip=True)
                    quality_score = self._calculate_content_quality(text_content)
                    
                    if quality_score > best_quality_score:
                        best_transcript = text_content
                        best_quality_score = quality_score
                        results['improvements_applied'].append(f"Better transcript found with selector: {selector}")
            
            results['extracted_data']['transcript'] = best_transcript[:200] + "..." if best_transcript and len(best_transcript) > 200 else best_transcript
            results['extracted_data']['transcript_length'] = len(best_transcript) if best_transcript else 0
            results['quality_scores']['transcript_quality'] = best_quality_score
            
            # IMPROVEMENT 6: Extract metadata using multiple strategies
            metadata = self._extract_metadata_improved(soup)
            results['extracted_data']['metadata'] = metadata
            
            # IMPROVEMENT 7: Performance optimization using SoupStrainer (Context7 feature)
            # For large documents, parse only relevant sections
            if len(html_content) > 100000:  # Large document
                relevant_tags = SoupStrainer(["h1", "h2", "h3", "div", "article", "main", "p"])
                optimized_soup = BeautifulSoup(html_content, 'html.parser', parse_only=relevant_tags)
                results['improvements_applied'].append("SoupStrainer optimization for large documents")
            
            parsing_time = time.time() - start_time
            results['performance_metrics']['parsing_time'] = parsing_time
            results['parsing_success'] = True
            
        except Exception as e:
            logger.error(f"Improved parsing failed: {e}")
            results['error'] = str(e)
        
        return results
    
    def _calculate_content_quality(self, text_content: str) -> float:
        """
        Calculate quality score for transcript content.
        
        Args:
            text_content (str): Text content to evaluate
            
        Returns:
            float: Quality score (0.0 to 1.0)
        """
        if not text_content:
            return 0.0
        
        score = 0.0
        
        # Length scoring (longer content generally better for transcripts)
        if len(text_content) > 1000:
            score += 0.3
        elif len(text_content) > 500:
            score += 0.2
        elif len(text_content) > 100:
            score += 0.1
        
        # Content indicators for transcripts
        transcript_indicators = [
            r'\b(?:character|dialogue|scene|episode)\b',
            r'\b(?:says?|said|tells?|told|speaks?|spoke)\b',
            r'[A-Z][A-Z\s]+:',  # Character names in caps
            r'\([^)]+\)',       # Stage directions in parentheses
            r'\[[^\]]+\]'       # Action descriptions in brackets
        ]
        
        for pattern in transcript_indicators:
            if re.search(pattern, text_content, re.IGNORECASE):
                score += 0.1
        
        # Penalize overly repetitive content
        words = text_content.split()
        if words:
            unique_words = set(words)
            diversity_ratio = len(unique_words) / len(words)
            if diversity_ratio > 0.3:
                score += 0.2
        
        return min(score, 1.0)
    
    def _extract_metadata_improved(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract metadata using improved Beautiful Soup techniques.
        
        Args:
            soup (BeautifulSoup): Parsed HTML document
            
        Returns:
            dict: Extracted metadata
        """
        metadata = {}
        
        # Extract season/episode info using multiple strategies
        season_episode_patterns = [
            r'[Ss]eason\s*(\d+).*[Ee]pisode\s*(\d+)',
            r'S(\d+)E(\d+)',
            r'(\d+)x(\d+)'
        ]
        
        # Search in title, URL, and text content
        text_sources = []
        
        # Get page title
        if soup.title:
            text_sources.append(soup.title.get_text(strip=True))
        
        # Get main heading
        h1 = soup.find('h1')
        if h1:
            text_sources.append(h1.get_text(strip=True))
        
        # Get breadcrumb navigation
        breadcrumbs = soup.select('.breadcrumb, .breadcrumbs, nav a')
        for breadcrumb in breadcrumbs:
            text_sources.append(breadcrumb.get_text(strip=True))
        
        # Extract season/episode from combined text
        for text in text_sources:
            for pattern in season_episode_patterns:
                match = re.search(pattern, text)
                if match:
                    metadata['season'] = match.group(1)
                    metadata['episode'] = match.group(2)
                    break
            if 'season' in metadata:
                break
        
        # Extract character list using improved selectors
        character_elements = soup.select('span.character, .character-name, .speaker')
        characters = [elem.get_text(strip=True) for elem in character_elements]
        if characters:
            metadata['characters'] = list(set(characters))  # Remove duplicates
        
        # Extract episode duration if available
        duration_text = soup.select_one('.duration, .runtime, .episode-length')
        if duration_text:
            metadata['duration'] = duration_text.get_text(strip=True)
        
        return metadata
    
    def _analyze_implementation(self, results: Dict[str, Any]) -> None:
        """Analyze current implementation and add recommendations."""
        
        # Check for common issues
        if not results['extracted_data'].get('title'):
            results['recommendations'].append(
                "Use multiple title selectors: ['h1', '.page-title', '.episode-title', 'title']"
            )
        
        if not results['extracted_data'].get('transcript'):
            results['recommendations'].append(
                "Use multiple transcript selectors with fallback options"
            )
        
        # Performance recommendations
        if results['performance_metrics'].get('parsing_time', 0) > 1.0:
            results['recommendations'].append(
                "Consider using SoupStrainer for large documents to improve parsing speed"
            )
        
        # General best practices
        results['recommendations'].extend([
            "Use explicit parser specification: BeautifulSoup(html, 'html.parser')",
            "Implement content quality scoring for better source selection",
            "Use get_text(strip=True) to remove whitespace automatically",
            "Add robust error handling for missing elements",
            "Consider using CSS selectors (.select()) for complex queries"
        ])
    
    def test_parsing_with_sample_html(self) -> None:
        """Test parsing with sample HTML content."""
        
        # Sample HTML content resembling transcript pages
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>My Hero Academia - Season 1, Episode 1: Izuku Midoriya Origin</title>
        </head>
        <body>
            <h1>My Hero Academia Season 1 Episode 1</h1>
            <div class="episode-info">
                <span class="season">Season 1</span>
                <span class="episode">Episode 1</span>
            </div>
            <div class="full-script">
                <p><span class="character">IZUKU:</span> Ever since I was four, I've been dreaming of this moment...</p>
                <p><span class="character">NARRATOR:</span> In a world where 80% of the population has some kind of superpower...</p>
                <p>(Scene: Izuku watching a hero video)</p>
                <p><span class="character">ALL MIGHT:</span> Fear not, for I am here!</p>
                <p>The episode continues with Izuku's journey to become a hero despite being quirkless.</p>
            </div>
        </body>
        </html>
        """
        
        print("\n" + "="*80)
        print("🧪 BEAUTIFUL SOUP PARSING VALIDATION RESULTS")
        print("="*80)
        
        # Test current implementation
        print("\n📊 CURRENT IMPLEMENTATION RESULTS:")
        current_results = self.validate_current_implementation(sample_html)
        self._print_results(current_results)
        
        # Test improved implementation
        print("\n🚀 IMPROVED IMPLEMENTATION RESULTS:")
        improved_results = self.validate_improved_implementation(sample_html)
        self._print_results(improved_results)
        
        # Performance comparison
        if (current_results.get('performance_metrics') and 
            improved_results.get('performance_metrics')):
            print("\n⚡ PERFORMANCE COMPARISON:")
            current_time = current_results['performance_metrics'].get('parsing_time', 0)
            improved_time = improved_results['performance_metrics'].get('parsing_time', 0)
            
            print(f"Current implementation: {current_time:.4f}s")
            print(f"Improved implementation: {improved_time:.4f}s")
            
            if improved_time < current_time:
                improvement = ((current_time - improved_time) / current_time) * 100
                print(f"✅ Performance improvement: {improvement:.1f}% faster")
            else:
                degradation = ((improved_time - current_time) / current_time) * 100
                print(f"⚠️  Performance impact: {degradation:.1f}% slower (due to additional quality checks)")
    
    def _print_results(self, results: Dict[str, Any]) -> None:
        """Print validation results in a formatted way."""
        
        if results.get('parsing_success'):
            print("✅ Parsing Status: SUCCESS")
        else:
            print("❌ Parsing Status: FAILED")
        
        # Print extracted data
        if results.get('extracted_data'):
            print("\n📄 Extracted Data:")
            for key, value in results['extracted_data'].items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")
        
        # Print quality scores if available
        if results.get('quality_scores'):
            print("\n🎯 Quality Scores:")
            for key, score in results['quality_scores'].items():
                print(f"  {key}: {score:.2f}")
        
        # Print improvements applied
        if results.get('improvements_applied'):
            print("\n🔧 Improvements Applied:")
            for improvement in results['improvements_applied']:
                print(f"  ✓ {improvement}")
        
        # Print issues found
        if results.get('issues_found'):
            print("\n⚠️  Issues Found:")
            for issue in results['issues_found']:
                print(f"  • {issue}")
        
        # Print recommendations
        if results.get('recommendations'):
            print("\n💡 Recommendations:")
            for rec in results['recommendations']:
                print(f"  • {rec}")
        
        print("-" * 60)


def main():
    """Run the Beautiful Soup parsing validation."""
    print("🔍 Beautiful Soup Transcript Parsing Validation")
    print("Based on Context7 documentation: https://github.com/wention/beautifulsoup4")
    
    validator = TranscriptParsingValidator()
    validator.test_parsing_with_sample_html()
    
    print("\n📚 KEY BEAUTIFUL SOUP BEST PRACTICES FROM CONTEXT7:")
    print("1. Always specify parser explicitly: BeautifulSoup(html, 'html.parser')")
    print("2. Use get_text(strip=True) to remove whitespace automatically")
    print("3. Implement multiple selector strategies for robustness")
    print("4. Use SoupStrainer for performance optimization on large documents")
    print("5. Handle encoding issues by letting BeautifulSoup auto-detect")
    print("6. Use CSS selectors (.select()) for complex element queries")
    print("7. Validate elements exist before calling methods on them")
    print("8. Consider content quality scoring for better source selection")
    
    print("\n🔧 RECOMMENDED IMPROVEMENTS FOR TRANSCRIPT DISCOVERY:")
    print("1. Implement fallback selectors for different transcript sites")
    print("2. Add content quality assessment to choose best source")
    print("3. Use structured data extraction for metadata")
    print("4. Implement retry logic with exponential backoff")
    print("5. Add content validation to ensure transcript quality")


if __name__ == "__main__":
    main()
