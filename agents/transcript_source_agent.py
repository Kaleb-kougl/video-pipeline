"""
Transcript Source Discovery Agent - Discovers and evaluates transcript sources.
"""

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSource:
    """Data class for transcript source information."""

    url: str
    source_type: str  # 'wiki', 'database', 'fan_site', 'official', 'community'
    reliability_score: float  # 0.0 to 1.0
    content_quality: str  # 'high', 'medium', 'low', 'unknown'
    last_updated: str | None
    accessibility: str  # 'public', 'registration', 'premium', 'blocked'
    format_type: str  # 'structured', 'plain_text', 'mixed', 'unknown'
    language: str
    episode_coverage: str  # 'complete', 'partial', 'single', 'unknown'
    metadata: dict


class TranscriptSourceDiscoveryAgent:
    """
    Agent responsible for discovering and evaluating transcript sources.

    This agent focuses on finding reliable sources for episode transcripts,
    evaluating their quality and accessibility, and building a comprehensive
    database of transcript sources for different shows.
    """

    #: Source families that are referenced by ``known_source_patterns`` /
    #: ``reliability_indicators`` but that this agent has no client for. They are
    #: never queried directly, so callers must not read their absence from a
    #: discovery result as "checked and nothing found".
    UNSEARCHED_SOURCES = (
        "MyAnimeList",
        "AniDB",
        "Anime News Network",
        "Crunchyroll",
    )

    def __init__(self):
        """
        Initialize the transcript source discovery agent.

        Sets up known source patterns, reliability indicators, search engines,
        and rate limiting configuration for transcript source discovery and evaluation.
        """
        # Only "fandom_wikis" and "transcript_databases" are crawled directly by
        # _search_known_patterns(). "community_sites" and "streaming_platforms" are
        # reference data: they document domains that web-search results are
        # classified against, they are not themselves searched.
        self.known_source_patterns = {
            "fandom_wikis": [
                "https://{}.fandom.com",
                "https://{}.wikia.com",
                "https://transcripts.fandom.com",
            ],
            "transcript_databases": [
                "https://transcripts.foreverdreaming.org",
                "https://www.springfieldspringfield.co.uk",
                "https://subslikescript.com",
                "https://www.tvfanatic.com",
                "https://www.imdb.com",
            ],
            "community_sites": [
                "https://www.reddit.com/r/{}",
                "https://myanimelist.net",
                "https://anidb.net",
                "https://www.animenewsnetwork.com",
            ],
            "streaming_platforms": [
                "https://www.crunchyroll.com",
                "https://www.funimation.com",
                "https://www.hulu.com",
                "https://www.netflix.com",
            ],
        }

        self.reliability_indicators = {
            "high_trust": [
                "fandom.com",
                "wikia.com",
                "imdb.com",
                "crunchyroll.com",
                "funimation.com",
                "animenewsnetwork.com",
                "myanimelist.net",
            ],
            "medium_trust": [
                "foreverdreaming.org",
                "springfieldspringfield.co.uk",
                "subslikescript.com",
                "tvfanatic.com",
                "anidb.net",
            ],
            "verify_needed": [
                "reddit.com",
                "blogspot.com",
                "wordpress.com",
                "tumblr.com",
                "fan-made",
                "user-generated",
            ],
        }

        self.search_engines = [
            "https://www.google.com/search",
            "https://duckduckgo.com",
            "https://www.bing.com/search",
        ]

        # Rate limiting
        self.request_delay = 2  # seconds between requests
        self.last_request_time = 0

    def discover_sources_for_show(
        self, show_name: str, season: int = None
    ) -> list[TranscriptSource]:
        """
        Discover transcript sources for a specific show.

        Searches the source families this agent actually implements - Fandom-style
        wikis and the known transcript databases - plus a general web search, then
        evaluates, deduplicates and sorts the results by reliability.

        The dedicated anime catalogue sites in ``UNSEARCHED_SOURCES`` (MyAnimeList,
        AniDB, Anime News Network, Crunchyroll) are **not** queried: no client for
        them exists. Their absence from the returned list therefore means "not
        checked", not "checked and found nothing". They can still turn up
        indirectly if the web search surfaces one of their pages.

        Args:
            show_name (str): Name of the show to search for
            season (int, optional): Optional season number for more specific search

        Returns:
            List[TranscriptSource]: List of discovered transcript sources sorted by reliability
        """
        logger.info(f"Discovering transcript sources for: {show_name}")

        sources = []

        # 1. Search known source patterns
        pattern_sources = self._search_known_patterns(show_name, season)
        sources.extend(pattern_sources)

        # 2. Perform web search for additional sources
        search_sources = self._perform_web_search(show_name, season)
        sources.extend(search_sources)

        # 3. Evaluate and deduplicate sources
        evaluated_sources = self._evaluate_and_deduplicate(sources)

        # 4. Sort by reliability score
        evaluated_sources.sort(key=lambda x: x.reliability_score, reverse=True)

        logger.info(
            f"Found {len(evaluated_sources)} transcript sources for {show_name} "
            f"(not searched: {', '.join(self.UNSEARCHED_SOURCES)})"
        )
        return evaluated_sources

    def _search_known_patterns(self, show_name: str, season: int = None) -> list[TranscriptSource]:
        """
        Search known source patterns for the show.

        Tests various URL patterns across Fandom wikis and transcript databases
        to find existing transcript sources for the specified show.

        Args:
            show_name (str): Name of the show to search for
            season (int, optional): Optional season number for context

        Returns:
            List[TranscriptSource]: Sources found through pattern matching
        """
        sources = []

        # Normalize show name for URL construction
        show_slug = self._normalize_show_name(show_name)

        # Search Fandom wikis
        for pattern in self.known_source_patterns["fandom_wikis"]:
            if "{}" in pattern:
                url = pattern.format(show_slug)
            else:
                url = f"{pattern}/{show_slug}"

            source = self._check_source_availability(url, "wiki", show_name, season)
            if source:
                sources.append(source)

        # Search transcript databases
        for base_url in self.known_source_patterns["transcript_databases"]:
            # Try different URL structures
            possible_urls = [
                f"{base_url}/{show_slug}",
                f"{base_url}/transcripts/{show_slug}",
                f"{base_url}/tv-show/{show_slug}",
                f"{base_url}/series/{show_slug}",
            ]

            for url in possible_urls:
                source = self._check_source_availability(url, "database", show_name, season)
                if source:
                    sources.append(source)
                    break  # Found one for this base URL, move to next

        return sources

    def _perform_web_search(self, show_name: str, season: int = None) -> list[TranscriptSource]:
        """Perform web search to find additional transcript sources."""
        sources = []

        # Construct search queries
        search_queries = [
            f'"{show_name}" transcript',
            f'"{show_name}" episode transcript',
            f'"{show_name}" script dialogue',
            f'"{show_name}" episode script',
        ]

        if season:
            search_queries.extend(
                [
                    f'"{show_name}" season {season} transcript',
                    f'"{show_name}" season {season} episode script',
                ]
            )

        # Search each query (limited to avoid rate limiting)
        for query in search_queries[:3]:  # Limit to first 3 queries
            try:
                search_results = self._search_with_google(query)
                for result_url in search_results[:5]:  # Top 5 results per query
                    source = self._analyze_potential_source(result_url, show_name, season)
                    if source:
                        sources.append(source)

                # Respect rate limiting
                time.sleep(self.request_delay)

            except Exception as e:
                logger.warning(f"Web search failed for query '{query}': {e}")
                continue

        return sources

    def _check_source_availability(
        self, url: str, source_type: str, show_name: str, season: int = None
    ) -> TranscriptSource | None:
        """Check if a potential source URL is available and contains transcripts."""
        try:
            self._rate_limit()

            response = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TranscriptBot/1.0)"},
            )

            if response.status_code == 200:
                # Analyze the content to determine if it contains transcripts
                content_analysis = self._analyze_page_content(response.text, show_name)

                if content_analysis["has_transcripts"]:
                    reliability_score = self._calculate_reliability_score(url, content_analysis)

                    return TranscriptSource(
                        url=url,
                        source_type=source_type,
                        reliability_score=reliability_score,
                        content_quality=content_analysis["quality"],
                        last_updated=content_analysis.get("last_updated"),
                        accessibility="public",
                        format_type=content_analysis["format"],
                        language=content_analysis.get("language", "english"),
                        episode_coverage=content_analysis["coverage"],
                        metadata=content_analysis,
                    )

        except Exception as e:
            logger.debug(f"Failed to check source {url}: {e}")

        return None

    def _analyze_page_content(self, html_content: str, show_name: str) -> dict:
        """Analyze page content to determine transcript availability and quality."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            text_content = soup.get_text().lower()

            # Check for transcript indicators
            transcript_indicators = [
                "transcript",
                "dialogue",
                "script",
                "episode script",
                "character:",
                "narrator:",
                "scene:",
                "[scene",
            ]

            has_transcripts = any(indicator in text_content for indicator in transcript_indicators)

            # Check for show name mentions
            show_mentions = text_content.count(show_name.lower())

            # Analyze content quality
            content_length = len(text_content)
            if content_length > 10000 and show_mentions > 5:
                quality = "high"
            elif content_length > 5000 and show_mentions > 2:
                quality = "medium"
            elif content_length > 1000:
                quality = "low"
            else:
                quality = "unknown"

            # Determine format type
            format_type = "unknown"
            if "character:" in text_content or re.search(r"\w+:", text_content):
                format_type = "structured"
            elif len(text_content) > 5000:
                format_type = "plain_text"
            else:
                format_type = "mixed"

            # Estimate episode coverage
            episode_patterns = [
                r"episode \d+",
                r"ep\d+",
                r"season \d+",
                r"s\d+e\d+",
                r"chapter \d+",
                r"part \d+",
            ]
            episode_matches = sum(
                len(re.findall(pattern, text_content)) for pattern in episode_patterns
            )

            if episode_matches > 10:
                coverage = "complete"
            elif episode_matches > 3:
                coverage = "partial"
            elif episode_matches > 0:
                coverage = "single"
            else:
                coverage = "unknown"

            # Check for last updated information
            last_updated = None
            date_patterns = [
                r"\d{4}-\d{2}-\d{2}",
                r"\d{1,2}/\d{1,2}/\d{4}",
                r"updated.*\d{4}",
                r"last.*\d{4}",
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text_content)
                if match:
                    last_updated = match.group()
                    break

            return {
                "has_transcripts": has_transcripts,
                "quality": quality,
                "format": format_type,
                "coverage": coverage,
                "last_updated": last_updated,
                "show_mentions": show_mentions,
                "content_length": content_length,
                "language": "english",  # Default, could be improved with detection
            }

        except Exception as e:
            logger.warning(f"Failed to analyze page content: {e}")
            return {
                "has_transcripts": False,
                "quality": "unknown",
                "format": "unknown",
                "coverage": "unknown",
            }

    def _calculate_reliability_score(self, url: str, content_analysis: dict) -> float:
        """Calculate reliability score for a transcript source."""
        score = 0.5  # Base score

        # Domain reputation
        domain = urlparse(url).netloc.lower()

        if any(trusted in domain for trusted in self.reliability_indicators["high_trust"]):
            score += 0.3
        elif any(medium in domain for medium in self.reliability_indicators["medium_trust"]):
            score += 0.2
        elif any(verify in domain for verify in self.reliability_indicators["verify_needed"]):
            score -= 0.1

        # Content quality
        quality_scores = {"high": 0.2, "medium": 0.1, "low": 0.0, "unknown": -0.1}
        score += quality_scores.get(content_analysis["quality"], 0)

        # Episode coverage
        coverage_scores = {"complete": 0.2, "partial": 0.1, "single": 0.0, "unknown": -0.1}
        score += coverage_scores.get(content_analysis["coverage"], 0)

        # Format structure
        format_scores = {"structured": 0.1, "plain_text": 0.05, "mixed": 0.02, "unknown": 0}
        score += format_scores.get(content_analysis["format"], 0)

        # Recency (if last_updated available)
        if content_analysis.get("last_updated"):
            score += 0.05  # Bonus for having update information

        return max(0.0, min(1.0, score))  # Clamp to 0-1 range

    def _search_with_google(self, query: str) -> list[str]:
        """Perform Google search and extract result URLs."""
        # Note: This is a simplified implementation
        # In production, you'd want to use Google's API or a proper search library
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

            self._rate_limit()
            response = requests.get(
                search_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TranscriptBot/1.0)"},
                timeout=10,
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                links = []

                # Extract search result URLs (simplified)
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if href.startswith("/url?q="):
                        # Extract actual URL from Google's redirect
                        actual_url = href.split("/url?q=")[1].split("&")[0]
                        if actual_url.startswith("http") and "google.com" not in actual_url:
                            links.append(actual_url)

                return links[:10]  # Return top 10 results

        except Exception as e:
            logger.warning(f"Google search failed: {e}")

        return []

    def _analyze_potential_source(
        self, url: str, show_name: str, season: int = None
    ) -> TranscriptSource | None:
        """Analyze a potential source URL found through web search."""
        try:
            # Determine source type based on URL
            domain = urlparse(url).netloc.lower()

            if "fandom.com" in domain or "wikia.com" in domain:
                source_type = "wiki"
            elif any(db in domain for db in ["transcripts", "script", "subtitle"]):
                source_type = "database"
            elif "reddit.com" in domain:
                source_type = "community"
            elif any(
                stream in domain for stream in ["crunchyroll", "funimation", "hulu", "netflix"]
            ):
                source_type = "official"
            else:
                source_type = "fan_site"

            return self._check_source_availability(url, source_type, show_name, season)

        except Exception as e:
            logger.debug(f"Failed to analyze potential source {url}: {e}")
            return None

    def _evaluate_and_deduplicate(self, sources: list[TranscriptSource]) -> list[TranscriptSource]:
        """Remove duplicates and improve source evaluation."""
        seen_urls = set()
        unique_sources = []

        for source in sources:
            # Normalize URL for comparison
            normalized_url = self._normalize_url(source.url)

            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_sources.append(source)

        return unique_sources

    def _normalize_show_name(self, show_name: str) -> str:
        """Normalize show name for URL construction."""
        # Remove special characters, convert to lowercase, replace spaces
        normalized = re.sub(r"[^\w\s-]", "", show_name.lower())
        normalized = re.sub(r"\s+", "-", normalized.strip())
        return normalized

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for duplicate detection."""
        # Remove trailing slashes, convert to lowercase
        return url.rstrip("/").lower()

    def _rate_limit(self):
        """Implement rate limiting for web requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)

        self.last_request_time = time.time()

    def evaluate_source_quality(self, source: TranscriptSource) -> dict:
        """
        Perform detailed quality evaluation of a transcript source.

        Args:
            source: TranscriptSource to evaluate

        Returns:
            Dictionary with detailed quality metrics
        """
        logger.info(f"Evaluating source quality: {source.url}")

        try:
            self._rate_limit()
            response = requests.get(
                source.url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TranscriptBot/1.0)"},
            )

            if response.status_code == 200:
                detailed_analysis = self._perform_detailed_content_analysis(response.text)

                return {
                    "overall_score": source.reliability_score,
                    "content_analysis": detailed_analysis,
                    "accessibility": self._check_accessibility(response),
                    "update_frequency": self._estimate_update_frequency(source.url),
                    "community_validation": self._check_community_validation(source.url),
                    "technical_quality": self._assess_technical_quality(response),
                }
            else:
                return {
                    "overall_score": 0.0,
                    "error": f"HTTP {response.status_code}",
                    "accessible": False,
                }

        except Exception as e:
            logger.error(f"Failed to evaluate source {source.url}: {e}")
            return {"overall_score": 0.0, "error": str(e), "accessible": False}

    def _perform_detailed_content_analysis(self, html_content: str) -> dict:
        """Perform detailed analysis of transcript content."""
        soup = BeautifulSoup(html_content, "html.parser")
        text_content = soup.get_text()

        # Count various content elements
        character_dialogue_count = len(re.findall(r"\w+:", text_content))
        scene_description_count = len(re.findall(r"\[.*?\]|\(.*?\)", text_content))
        word_count = len(text_content.split())

        # Assess formatting consistency
        formatting_score = self._assess_formatting_consistency(text_content)

        # Check for timestamps
        has_timestamps = bool(re.search(r"\d{2}:\d{2}:\d{2}|\d{1,2}:\d{2}", text_content))

        return {
            "word_count": word_count,
            "character_dialogue_count": character_dialogue_count,
            "scene_description_count": scene_description_count,
            "formatting_score": formatting_score,
            "has_timestamps": has_timestamps,
            "content_density": character_dialogue_count / max(1, word_count / 100),
            "structure_quality": "high"
            if formatting_score > 0.7
            else "medium"
            if formatting_score > 0.4
            else "low",
        }

    def _assess_formatting_consistency(self, text_content: str) -> float:
        """Assess the consistency of transcript formatting."""
        lines = text_content.split("\n")
        dialogue_lines = [line for line in lines if ":" in line and len(line.strip()) > 5]

        if not dialogue_lines:
            return 0.0

        # Check consistency patterns
        consistent_patterns = 0
        total_checks = 0

        # Check character name formatting consistency
        for line in dialogue_lines[:20]:  # Sample first 20 lines
            if ":" in line:
                char_name = line.split(":")[0].strip()
                total_checks += 1
                if char_name.isupper() or char_name.istitle():
                    consistent_patterns += 1

        return consistent_patterns / max(1, total_checks)

    def _check_accessibility(self, response) -> str:
        """Check source accessibility requirements."""
        # Check for login requirements, paywalls, etc.
        content = response.text.lower()

        if any(
            indicator in content for indicator in ["login", "sign in", "register", "subscription"]
        ):
            return "registration"
        elif any(indicator in content for indicator in ["premium", "paid", "subscribe", "payment"]):
            return "premium"
        else:
            return "public"

    def _estimate_update_frequency(self, url: str) -> str:
        """Estimate how frequently the source is updated."""
        # This could be enhanced with historical checking
        domain = urlparse(url).netloc.lower()

        if "fandom.com" in domain or "wikia.com" in domain:
            return "frequent"  # Community-edited wikis
        elif "official" in domain or any(
            official in domain for official in ["crunchyroll", "funimation"]
        ):
            return "regular"  # Official sources
        else:
            return "unknown"

    def _check_community_validation(self, url: str) -> dict:
        """Check if source has community validation/editing."""
        domain = urlparse(url).netloc.lower()

        if "fandom.com" in domain or "wikia.com" in domain:
            return {"has_community": True, "type": "wiki", "validation_level": "high"}
        elif "reddit.com" in domain:
            return {"has_community": True, "type": "forum", "validation_level": "medium"}
        else:
            return {"has_community": False, "type": "static", "validation_level": "low"}

    def _assess_technical_quality(self, response) -> dict:
        """Assess technical quality of the source."""
        return {
            "load_time": response.elapsed.total_seconds(),
            "content_length": len(response.content),
            "encoding": response.encoding,
            "status_code": response.status_code,
            "has_ssl": response.url.startswith("https"),
            "mobile_friendly": "viewport" in response.text.lower(),
        }

    def get_source_recommendations(self, sources: list[TranscriptSource]) -> dict:
        """
        Get recommendations for best transcript sources.

        Args:
            sources: List of discovered transcript sources

        Returns:
            Dictionary with source recommendations
        """
        if not sources:
            return {"recommended": [], "backup": [], "avoid": [], "summary": "No sources found"}

        # Categorize sources
        recommended = [s for s in sources if s.reliability_score >= 0.7]
        backup = [s for s in sources if 0.4 <= s.reliability_score < 0.7]
        avoid = [s for s in sources if s.reliability_score < 0.4]

        return {
            "recommended": recommended[:5],  # Top 5 recommended
            "backup": backup[:3],  # Top 3 backup options
            "avoid": avoid,
            "total_found": len(sources),
            "summary": f"Found {len(sources)} sources: {len(recommended)} recommended, {len(backup)} backup, {len(avoid)} to avoid",
            "best_source": sources[0] if sources else None,
        }
