"""
**DEPRECATED** Enhanced Agent for discovering anime episode transcripts with improved Beautiful Soup parsing.

⚠️  DEPRECATION NOTICE: This agent's find_episode_transcript() method is deprecated.
    For new code, use the cleaner separation of concerns:
    1. discovery_agent.search_episode_enhanced() - to find URLs
    2. transcript_agent.parse_discovered_url() - to parse content

This implementation uses Context7 Beautiful Soup best practices for robust
transcript discovery and parsing across multiple sources.
"""

import logging
import re

# Import from the core module - we'll handle this with absolute imports
import sys
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, SoupStrainer

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from core.schemas import TranscriptResult
except ImportError:
    # Fallback for when running as standalone
    TranscriptResult = dict

logger = logging.getLogger(__name__)


class TranscriptDiscoveryAgent:
    """
    **DEPRECATED USAGE**: This agent's discovery methods are deprecated in favor of separate agents.

    ✅ CURRENT USAGE: Use parse_discovered_url() to parse URLs found by the discovery agent
    ❌ DEPRECATED: Using find_episode_transcript() for combined discovery + parsing

    This agent implements Context7 Beautiful Soup best practices:
    - Explicit parser specification
    - Multiple selector strategies
    - Content quality assessment
    - Robust error handling
    - Performance optimization

    Recommended workflow:
    1. discovery_agent.search_episode_enhanced() - finds URLs with search functionality
    2. transcript_agent.parse_discovered_url() - parses content from discovered URLs
    """

    def __init__(self):
        """
        Initialize with enhanced parsing configurations.

        Sets up multi-source transcript parsing capabilities with Beautiful Soup
        configurations, session management, and show name mappings.
        """

        # Multi-source configuration with improved selectors
        self.sources = {
            "subslikescript": {
                "base_url": "https://subslikescript.com",
                "selectors": {
                    "transcript": [
                        ".full-script",
                        ".transcript-content",
                        "main .content",
                        "article",
                    ],
                    "title": ["h1", ".page-title", ".episode-title", "title"],
                    "search_results": ['a[href*="series"]', ".search-result a", ".result-link"],
                    "metadata": [".episode-info", ".show-info", ".breadcrumb"],
                },
                "quality_indicators": [
                    "character dialogue",
                    "scene descriptions",
                    "episode content",
                ],
            },
            "transcripts_wiki": {
                "base_url": "https://transcripts.fandom.com",
                "selectors": {
                    "transcript": [".mw-parser-output", ".transcript", ".episode-content", "main"],
                    "title": [".page-header__title", "h1", ".firstHeading", "title"],
                    "search_results": ['a[href*="/wiki/"]', ".unified-search__result a"],
                    "metadata": [".episode-nav", ".infobox", ".episode-info"],
                },
                "quality_indicators": ["wiki content", "structured data", "episode information"],
            },
            "anime_transcripts": {
                "base_url": "https://anime-transcripts.com",
                "selectors": {
                    "transcript": [".transcript-content", ".episode-transcript", "main .content"],
                    "title": [".episode-title", "h1", ".page-title"],
                    "search_results": ['a[href*="/episode/"]', ".episode-link"],
                    "metadata": [".episode-info", ".show-metadata"],
                },
                "quality_indicators": ["anime content", "episode transcript", "dialogue"],
            },
        }

        # Enhanced session configuration
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
            }
        )

        self.retry_count = 3
        self.delay_range = (1, 3)

        # Common show name mappings to URL slugs (preserved for compatibility)
        self.show_mappings = {
            "My Hero Academia": [
                "my-hero-academia",
                "boku-no-hero-academia",
                "mha",
                "My_Hero_Academia-5626028",
            ],
            "Attack on Titan": ["attack-on-titan", "shingeki-no-kyojin", "aot"],
            "Demon Slayer": ["demon-slayer", "kimetsu-no-yaiba"],
            "One Piece": ["one-piece"],
            "Naruto": ["naruto", "naruto-shippuden"],
            "Dragon Ball": ["dragon-ball", "dragon-ball-z", "dragon-ball-super"],
            "Death Note": ["death-note"],
            "Fullmetal Alchemist": ["fullmetal-alchemist", "fma"],
            "Hunter x Hunter": ["hunter-x-hunter", "hxh"],
            "Tokyo Ghoul": ["tokyo-ghoul"],
            "Jujutsu Kaisen": ["jujutsu-kaisen"],
            "Chainsaw Man": ["chainsaw-man"],
            "Frieren: Beyond Journey's End": [
                "Frieren_Beyond_Journeys_End-22248376",
                "frieren-beyond-journeys-end",
            ],
        }

        # Request session with retry and delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

        self.retry_count = 3
        self.delay_range = (1, 3)  # Random delay between requests

    def get_show_slugs(self, show_name: str) -> list[str]:
        """
        Get possible URL slugs for a show name with comprehensive pattern generation.

        Args:
            show_name (str): The show name to generate slugs for

        Returns:
            List[str]: List of possible URL slugs for the show
        """
        # Check if we have predefined mappings
        if show_name in self.show_mappings:
            return self.show_mappings[show_name]

        slugs = []
        original = show_name.strip()

        # Basic cleanup
        cleaned = original.lower()

        # Handle common patterns and special characters
        replacements = [
            # Remove/replace punctuation
            (":", ""),
            ("'", ""),
            ('"', ""),
            ("!", ""),
            ("?", ""),
            (".", ""),
            (",", ""),
            ("&", "and"),
            ("+", "plus"),
            ("~", ""),
            ("/", "-"),
            ("\\", "-"),
            ("(", ""),
            (")", ""),
            ("[", ""),
            ("]", ""),
            ("{", ""),
            ("}", ""),
        ]

        # Generate multiple variations
        for old, new in replacements:
            cleaned = cleaned.replace(old, new)

        # Remove extra spaces and normalize
        cleaned = " ".join(cleaned.split())

        # Pattern 1: Standard dash-separated
        slugs.append(cleaned.replace(" ", "-"))

        # Pattern 2: Underscore-separated
        slugs.append(cleaned.replace(" ", "_"))

        # Pattern 3: No separators (concatenated)
        slugs.append(cleaned.replace(" ", ""))

        # Pattern 4: Title case with dashes
        title_case = "-".join(word.capitalize() for word in cleaned.split())
        slugs.append(title_case)

        # Pattern 5: Handle subtitle patterns (e.g., "Title: Subtitle" -> "title-subtitle")
        if ":" in original:
            parts = [part.strip() for part in original.split(":")]
            if len(parts) == 2:
                main_title, subtitle = parts
                # Main title only
                main_cleaned = self._clean_title_part(main_title)
                slugs.append(main_cleaned.replace(" ", "-"))
                slugs.append(main_cleaned.replace(" ", "_"))

                # Subtitle only
                sub_cleaned = self._clean_title_part(subtitle)
                slugs.append(sub_cleaned.replace(" ", "-"))
                slugs.append(sub_cleaned.replace(" ", "_"))

                # Combined variations
                combined = f"{main_cleaned} {sub_cleaned}"
                slugs.append(combined.replace(" ", "-"))
                slugs.append(combined.replace(" ", "_"))

        # Pattern 6: Acronyms (first letter of each word)
        words = cleaned.split()
        if len(words) > 1:
            acronym = "".join(word[0] for word in words if word)
            slugs.append(acronym)
            slugs.append(acronym.upper())

        # Pattern 7: Remove common words
        common_words = {
            "the",
            "a",
            "an",
            "of",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
        }
        filtered_words = [word for word in words if word not in common_words]
        if len(filtered_words) != len(words):
            filtered_title = " ".join(filtered_words)
            slugs.append(filtered_title.replace(" ", "-"))
            slugs.append(filtered_title.replace(" ", "_"))

        # Pattern 8: Handle numbers (convert to words and vice versa)
        number_map = {
            "1": "one",
            "2": "two",
            "3": "three",
            "4": "four",
            "5": "five",
            "6": "six",
            "7": "seven",
            "8": "eight",
            "9": "nine",
            "10": "ten",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
        }

        for old_num, new_num in number_map.items():
            if old_num in cleaned:
                numbered_variant = cleaned.replace(old_num, new_num)
                slugs.append(numbered_variant.replace(" ", "-"))
                slugs.append(numbered_variant.replace(" ", "_"))

        # Remove duplicates while preserving order
        unique_slugs = []
        seen = set()
        for slug in slugs:
            if slug and slug not in seen:
                unique_slugs.append(slug)
                seen.add(slug)

        return unique_slugs

    def _clean_title_part(self, title_part: str) -> str:
        """
        Helper method to clean individual title parts.

        Args:
            title_part (str): The title part to clean

        Returns:
            str: Cleaned title part with special characters removed
        """
        cleaned = title_part.lower().strip()

        # Remove special characters
        for char in ":'\"!?.,&+~()[]{}":
            cleaned = cleaned.replace(char, "")

        # Normalize spaces
        cleaned = " ".join(cleaned.split())

        return cleaned

    def format_episode_title(self, title: str) -> str:
        """
        Format episode title for URL usage.

        Args:
            title (str): Episode title to format

        Returns:
            str: Formatted title slug suitable for URLs
        """
        if not title:
            return ""

        # Remove special characters and format for URL
        slug = title.lower()
        slug = "".join(c for c in slug if c.isalnum() or c in " -_")
        slug = slug.replace(" ", "-")
        slug = "-".join(filter(None, slug.split("-")))  # Remove empty parts

        return slug

    def find_episode_transcript(
        self,
        show_name: str,
        season: int,
        episode: int,
        episode_title: str | None = None,
        use_discovery: bool = True,
    ) -> dict[str, Any] | None:
        """
        Enhanced transcript discovery with improved Beautiful Soup parsing.

        **DEPRECATED**: This method combines discovery and parsing in one call.
        For new code, use the cleaner separation:
        1. discovery_agent.search_episode_enhanced() - to find URLs
        2. transcript_agent.parse_discovered_url() - to parse content

        Args:
            show_name (str): Show name
            season (int): Season number
            episode (int): Episode number
            episode_title (str, optional): Episode title for better matching
            use_discovery (bool): Whether to use dynamic pattern discovery (kept for compatibility)

        Returns:
            dict: Best transcript result or None if not found
        """
        logger.info(f"Enhanced search for {show_name} S{season}E{episode}")

        all_results = []

        # Multi-source search with quality assessment
        for source_name, _source_config in self.sources.items():
            logger.info(f"Searching {source_name}...")

            try:
                result = self._search_source_enhanced(
                    source_name, show_name, season, episode, episode_title
                )
                if result:
                    all_results.append(result)
                    logger.info(f"Found on {source_name} (quality: {result['quality_score']:.2f})")

            except Exception:
                # Deliberately broad, and deliberately the *only* broad handler
                # left on this path: one misbehaving source must not abort a
                # multi-source search. `logger.exception` keeps the traceback so
                # a bug that reaches here is still diagnosable.
                logger.exception(f"Error searching {source_name}")
                continue

        if not all_results:
            logger.warning(f"No transcripts found for {show_name} S{season}E{episode}")
            return None

        # Select best result based on comprehensive scoring
        best_result = self._select_best_result(all_results)

        logger.info(
            f"Selected best result from {best_result['source']} "
            f"(quality: {best_result['quality_score']:.2f})"
        )

        return best_result

    def _search_source_enhanced(
        self,
        source_name: str,
        show_name: str,
        season: int,
        episode: int,
        episode_title: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Enhanced source search with improved Beautiful Soup parsing.

        Args:
            source_name (str): Name of the source to search
            show_name (str): Name of the show
            season (int): Season number
            episode (int): Episode number
            episode_title (Optional[str]): Optional episode title for better matching

        Returns:
            Optional[Dict[str, Any]]: Parsed transcript result or None if not found
        """
        source_config = self.sources[source_name]

        # Generate test URLs based on common patterns
        test_urls = self._generate_test_urls(source_config, show_name, season, episode)

        for url in test_urls:
            try:
                result = self._fetch_and_parse_enhanced(url, source_config, source_name)
                if result and result["quality_score"] > 0.3:  # Minimum quality threshold
                    return result

            except requests.exceptions.RequestException as e:
                # A URL that will not load is the *expected* failure here: the
                # candidate URLs are guesses from naming patterns and most of
                # them 404. Narrowed from `except Exception` so that a parser
                # bug no longer masquerades as "this guess was wrong".
                logger.debug(f"Failed to fetch {url}: {e}")
                continue

        return None

    def _fetch_and_parse_enhanced(
        self, url: str, source_config: dict[str, Any], source_name: str
    ) -> dict[str, Any] | None:
        """
        Enhanced HTML fetching and Beautiful Soup parsing with Context7 best practices.

        Retries transient HTTP failures and empty bodies with jittered
        exponential backoff (see ``utils.retry``). A parse failure is *not* a
        transient error and is no longer swallowed: it propagates so the bug can
        be fixed rather than reappearing as "this source has no transcript".

        Raises:
            requests.exceptions.RequestException: If every attempt failed with a
                transient HTTP error. The caller treats this as "this URL is not
                available" and moves on to the next candidate.
        """

        # Imported here rather than at module scope: this module only puts the
        # project root on sys.path at import time (see the bootstrap above), so
        # a top-level first-party import would be an E402 and would break the
        # standalone-execution path the bootstrap exists to support.
        from utils.retry import with_http_retries

        def _attempt() -> dict[str, Any] | None:
            # Fetch HTML content
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            html_content = response.text
            if not html_content:
                return None

            # BEST PRACTICE 1: Explicit parser specification (Context7 recommendation)
            # Use SoupStrainer for performance optimization on large documents
            if len(html_content) > 100000:
                # Parse only relevant tags for better performance
                relevant_tags = SoupStrainer(
                    ["h1", "h2", "h3", "div", "article", "main", "p", "span"]
                )
                soup = BeautifulSoup(html_content, "html.parser", parse_only=relevant_tags)
                logger.debug(
                    f"Used SoupStrainer optimization for large document: {len(html_content)} chars"
                )
            else:
                soup = BeautifulSoup(html_content, "html.parser")

            # Enhanced content extraction with multiple strategies
            return self._extract_content_enhanced(soup, source_config, url, source_name)

        return with_http_retries(
            _attempt,
            attempts=self.retry_count,
            delay_range=self.delay_range,
            logger=logger,
            description=f"Transcript fetch from {url}",
        )

    def _extract_content_enhanced(
        self, soup: BeautifulSoup, source_config: dict[str, Any], url: str, source_name: str
    ) -> dict[str, Any] | None:
        """Enhanced content extraction using Context7 Beautiful Soup best practices."""

        result = {
            "source": source_name,
            "url": url,
            "title": None,
            "transcript": None,
            "metadata": {},
            "quality_score": 0.0,
            "content_length": 0,
            "extraction_method": "enhanced_parsing",
            "found_via_search": True,  # This URL was discovered via search
        }

        # BEST PRACTICE 2: Multiple selector strategies for robustness
        selectors = source_config["selectors"]

        # Extract title with fallback selectors
        for title_selector in selectors["title"]:
            title_element = soup.select_one(title_selector)
            if title_element:
                # BEST PRACTICE 3: Use get_text(strip=True) to remove whitespace
                result["title"] = title_element.get_text(strip=True)
                break

        # Extract transcript with quality assessment
        best_transcript = None
        best_quality = 0.0

        for transcript_selector in selectors["transcript"]:
            elements = soup.select(transcript_selector)

            for element in elements:
                # Extract text content with proper whitespace handling
                text_content = element.get_text("\n", strip=True)  # Preserve line breaks

                if not text_content or len(text_content) < 100:
                    continue

                # BEST PRACTICE 4: Content quality assessment
                quality_score = self._calculate_content_quality_enhanced(
                    text_content, source_config.get("quality_indicators", [])
                )

                if quality_score > best_quality:
                    best_transcript = text_content
                    best_quality = quality_score

        if not best_transcript:
            return None

        result["transcript"] = best_transcript
        result["content_length"] = len(best_transcript)
        result["quality_score"] = best_quality

        # Enhanced metadata extraction
        result["metadata"] = self._extract_metadata_enhanced(soup, selectors.get("metadata", []))

        # Add episode_info field for TranscriptResult schema compatibility
        result["episode_info"] = result["metadata"].copy()  # Use metadata as episode_info

        return result

    def _calculate_content_quality_enhanced(
        self, text_content: str, quality_indicators: list[str]
    ) -> float:
        """Enhanced content quality assessment based on multiple factors."""

        if not text_content:
            return 0.0

        score = 0.0
        text_lower = text_content.lower()

        # Length scoring (progressive)
        length = len(text_content)
        if length > 5000:
            score += 0.4
        elif length > 2000:
            score += 0.3
        elif length > 1000:
            score += 0.2
        elif length > 500:
            score += 0.1

        # Transcript content indicators
        transcript_patterns = [
            (r"\b(?:character|dialogue|scene|episode|transcript)\b", 0.1),
            (r"\b(?:says?|said|tells?|told|speaks?|spoke|replies?|replied)\b", 0.1),
            (r"[A-Z][A-Z\s]+:", 0.15),  # Character names in caps
            (r"\([^)]+\)", 0.1),  # Stage directions
            (r"\[[^\]]+\]", 0.1),  # Action descriptions
            (r"\b(?:narrator|voice-over|v\.o\.)\b", 0.05),
            (r"(?:fade in|fade out|cut to|int\.|ext\.)", 0.05),
        ]

        for pattern, weight in transcript_patterns:
            matches = len(re.findall(pattern, text_content, re.IGNORECASE))
            if matches > 0:
                score += min(weight * (matches / 10), weight)  # Cap the contribution

        # Source-specific quality indicators
        for indicator in quality_indicators:
            if indicator.lower() in text_lower:
                score += 0.05

        # Content diversity assessment
        words = text_content.split()
        if words:
            unique_words = set(words)
            diversity_ratio = len(unique_words) / len(words)
            if diversity_ratio > 0.3:
                score += 0.1
            elif diversity_ratio > 0.5:
                score += 0.15

        return min(score, 1.0)

    def _extract_metadata_enhanced(
        self, soup: BeautifulSoup, metadata_selectors: list[str]
    ) -> dict[str, Any]:
        """Enhanced metadata extraction using Beautiful Soup best practices."""

        metadata = {}

        # Extract season/episode information using multiple patterns
        season_episode_patterns = [
            r"[Ss]eason\s*(\d+).*[Ee]pisode\s*(\d+)",
            r"S(\d+)E(\d+)",
            r"(\d+)x(\d+)",
            r"Season\s*(\d+)\s*Episode\s*(\d+)",
        ]

        # Collect text from multiple sources
        text_sources = []

        # Page title
        if soup.title:
            text_sources.append(soup.title.get_text(strip=True))

        # Main heading
        for h_tag in ["h1", "h2", "h3"]:
            heading = soup.find(h_tag)
            if heading:
                text_sources.append(heading.get_text(strip=True))

        # Extract season/episode from all text sources
        for text in text_sources:
            for pattern in season_episode_patterns:
                match = re.search(pattern, text)
                if match:
                    metadata["season"] = match.group(1)
                    metadata["episode"] = match.group(2)
                    break
            if "season" in metadata:
                break

        return metadata

    def _generate_test_urls(
        self, source_config: dict[str, Any], show_name: str, season: int, episode: int
    ) -> list[str]:
        """Generate test URLs for the given show and episode."""

        base_url = source_config["base_url"]
        show_slugs = self._get_show_slugs(show_name)

        urls = []

        # Common URL patterns
        patterns = [
            "/series/{show_slug}/season-{season}/episode-{episode}",
            "/series/{show_slug}/season-{season}/episode-{episode:02d}",
            "/series/{show_slug}/s{season}e{episode}",
            "/series/{show_slug}/s{season}e{episode:02d}",
            "/wiki/{show_slug}_Season_{season}_Episode_{episode}",
            "/wiki/{show_slug}/Season_{season}/Episode_{episode}",
            "/{show_slug}/season-{season}/episode-{episode}",
        ]

        for show_slug in show_slugs[:3]:  # Limit to top 3 slug variations
            for pattern in patterns:
                url = base_url + pattern.format(show_slug=show_slug, season=season, episode=episode)
                urls.append(url)

        return urls

    def _get_show_slugs(self, show_name: str) -> list[str]:
        """Generate possible URL slugs for show name."""

        slugs = []

        # Basic cleanup
        cleaned = show_name.lower()
        for char in ":'\"!?.,&+~()[]{}":
            cleaned = cleaned.replace(char, "")

        cleaned = " ".join(cleaned.split())

        # Generate variations
        slugs.extend(
            [
                cleaned.replace(" ", "-"),
                cleaned.replace(" ", "_"),
                cleaned.replace(" ", ""),
                "-".join(word.capitalize() for word in cleaned.split()),
            ]
        )

        # Predefined mappings for common shows
        mappings = {
            "my hero academia": [
                "my-hero-academia",
                "My_Hero_Academia-5626028",
                "boku-no-hero-academia",
            ],
            "attack on titan": ["attack-on-titan", "shingeki-no-kyojin"],
            "demon slayer": ["demon-slayer", "kimetsu-no-yaiba"],
        }

        if cleaned in mappings:
            slugs.extend(mappings[cleaned])

        return list(dict.fromkeys(slugs))  # Remove duplicates while preserving order

    def _select_best_result(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Select the best result based on comprehensive scoring."""

        def score_result(result):
            # Weighted scoring system
            quality_weight = 0.6
            length_weight = 0.3
            source_weight = 0.1

            quality_score = result.get("quality_score", 0.0)

            # Normalize content length (prefer longer content up to a point)
            length = result.get("content_length", 0)
            length_score = min(length / 10000, 1.0)  # Normalize to 10k chars max

            # Source preference (can be customized)
            source_scores = {
                "subslikescript": 0.9,
                "transcripts_wiki": 0.8,
                "anime_transcripts": 0.7,
            }
            source_score = source_scores.get(result.get("source", ""), 0.5)

            total_score = (
                quality_score * quality_weight
                + length_score * length_weight
                + source_score * source_weight
            )

            return total_score

        return max(results, key=score_result)

    def parse_discovered_url(self, url: str, source_name: str) -> dict[str, Any] | None:
        """
        Clean public method to parse a transcript from a discovered URL.

        This method takes a URL found by the discovery agent and extracts the transcript
        content using the appropriate source configuration and parsing strategy.

        Args:
            url (str): The URL to parse (typically found by discovery agent)
            source_name (str): The source name (subslikescript, movies_fandom, etc.)

        Returns:
            Optional[Dict[str, Any]]: Parsed transcript data with metadata, or None if parsing fails

        Example:
            discovery_result = discovery_agent.search_episode_enhanced("My Hero Academia", 1, 2)
            if discovery_result:
                transcript = transcript_agent.parse_discovered_url(
                    discovery_result['url'],
                    discovery_result['source']
                )
        """
        logger.info(f"Parsing discovered URL from {source_name}: {url}")

        # Get the source configuration
        source_config = self.sources.get(source_name)
        if not source_config:
            logger.error(f"Unknown source: {source_name}")
            return None

        # Use the enhanced parsing method
        result = self._fetch_and_parse_enhanced(url, source_config, source_name)

        if result:
            logger.info(
                f"Successfully parsed transcript from {source_name} "
                f"(length: {result['content_length']:,} chars, "
                f"quality: {result['quality_score']:.2f})"
            )
        else:
            logger.error(f"Failed to parse transcript from {source_name}: {url}")

        return result

    # Compatibility methods for existing codebase
    def search_source(
        self,
        source_name: str,
        show_name: str,
        season: int,
        episode: int,
        episode_title: str | None = None,
    ) -> dict[str, Any] | None:
        """Search a specific source for episode transcript (compatibility method)."""
        return self._search_source_enhanced(source_name, show_name, season, episode, episode_title)

    def search_using_site_search(
        self, source_name: str, show_name: str, season: int, episode: int
    ) -> dict[str, Any] | None:
        """Use site search functionality (compatibility method)."""
        logger.info(f"Site search on {source_name} for {show_name} S{season}E{episode}")
        return self._search_source_enhanced(source_name, show_name, season, episode)

    def search_with_fallback_discovery(
        self, show_name: str, season: int, episode: int, episode_title: str | None = None
    ) -> dict[str, Any] | None:
        """Enhanced search with fallback discovery (compatibility method)."""
        logger.info(f"Fallback discovery for {show_name} S{season}E{episode}")
        return self.find_episode_transcript(show_name, season, episode, episode_title)
