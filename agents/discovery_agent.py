"""
Enhanced Agent for discovering and validating episode URLs using search functionality.
"""

import logging
import random
import re
import time
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EpisodeDiscoveryAgent:
    """
    Enhanced agent responsible for discovering and validating episode URLs using search functionality.

    This agent leverages site search capabilities to find valid transcript URLs
    for anime episodes, handling complex naming conventions and URL patterns
    through intelligent search queries and result parsing.
    """

    #: How many consecutive episode probes must come back empty before a season
    #: with no configured length is treated as finished. Nothing here invents a
    #: season length: the run stops on observed evidence (a run of misses) and
    #: the trailing misses are discarded rather than reported as episodes.
    CONSECUTIVE_MISSES_TO_STOP = 3

    #: Hard ceiling on probes for a season with no configured length. Reaching it
    #: means the season is reported as partial coverage, never as complete.
    MAX_EPISODE_PROBES = 60

    #: Hard ceiling on seasons probed for a show with no configured season list.
    MAX_SEASON_PROBES = 20

    def __init__(self):
        """
        Initialize the enhanced episode discovery agent with search configurations.
        Sets up multi-source search capabilities and validation patterns.
        """
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

        # Multi-source search configuration
        self.search_sources = {
            "subslikescript": {
                "base_url": "https://subslikescript.com",
                "search_endpoint": "/search",
                "search_param": "q",  # Keep old format for subslikescript
                "result_selectors": [
                    'a[href*="/series/"]',  # Direct series links
                    ".search-result a",
                    ".result-link",
                    "h3 a",
                    ".entry-title a",
                    "a",  # Fallback to any link
                ],
                "episode_url_patterns": [
                    r"/series/[^/]+/season-\d+/episode-\d+",
                    r"/series/[^/]+/s\d+e\d+",
                    r"/episode/[^/]+",
                    r"/series/[^/]+$",  # Series pages that we can construct episodes from
                ],
                "quality_indicators": ["full-script", "transcript", "episode"],
            },
            "movies_fandom": {
                "base_url": "https://movies.fandom.com",
                "search_endpoint": "/wiki/Special:Search",
                "search_params": {
                    "query": "",  # Will be filled with search query
                    "scope": "internal",
                    "navigationSearch": "true",
                },
                "result_selectors": [
                    'a[href*="/wiki/"]',
                    ".unified-search__result a",
                    ".mw-search-result-heading a",
                    ".search-result-list a",
                    ".search-results a",
                ],
                "episode_url_patterns": [
                    r"/wiki/[^/]+_Season_\d+",
                    r"/wiki/[^/]+/Episode_\d+",
                    r"/wiki/[^/]+_\d+x\d+",
                    r"/wiki/[^/]+_Episode_\d+",
                    r"/wiki/[^/]+_Transcript",
                ],
                "quality_indicators": ["transcript", "episode", "movie", "wiki"],
            },
            "animetranscript_fandom": {
                "base_url": "https://animetranscript.fandom.com",
                "search_endpoint": "/wiki/Special:Search",
                "search_params": {
                    "query": "",  # Will be filled with search query
                    "scope": "internal",
                    "navigationSearch": "true",
                },
                "result_selectors": [
                    'a[href*="/wiki/"]',
                    ".unified-search__result a",
                    ".mw-search-result-heading a",
                    ".search-result-list a",
                    ".search-results a",
                ],
                "episode_url_patterns": [
                    r"/wiki/[^/]+_Season_\d+",
                    r"/wiki/[^/]+/Episode_\d+",
                    r"/wiki/[^/]+_\d+x\d+",
                    r"/wiki/[^/]+_Episode_\d+",
                    r"/wiki/[^/]+_Transcript",
                ],
                "quality_indicators": ["transcript", "episode", "anime", "wiki"],
            },
        }

        # Common show name mappings for better search results
        self.show_mappings = {
            "My Hero Academia": ["my hero academia", "boku no hero academia", "mha", "bnha"],
            "Attack on Titan": ["attack on titan", "shingeki no kyojin", "aot", "snk"],
            "Demon Slayer": ["demon slayer", "kimetsu no yaiba", "kny"],
            "One Piece": ["one piece"],
            "Naruto": ["naruto", "naruto shippuden"],
            "Dragon Ball": ["dragon ball", "dragon ball z", "dragon ball super", "dbz", "dbs"],
            "Death Note": ["death note"],
            "Fullmetal Alchemist": [
                "fullmetal alchemist",
                "fma",
                "fullmetal alchemist brotherhood",
            ],
            "Hunter x Hunter": ["hunter x hunter", "hxh"],
            "Tokyo Ghoul": ["tokyo ghoul"],
            "Jujutsu Kaisen": ["jujutsu kaisen", "jjk"],
            "Chainsaw Man": ["chainsaw man"],
            "Frieren: Beyond Journey's End": ["frieren beyond journeys end", "frieren"],
        }

        self.retry_count = 3
        self.delay_range = (1, 3)

        # Legacy support - keep base URL for compatibility.
        # NOTE: this URL points at one specific series, so any URL built from it
        # is only meaningful for that show (see `legacy_show_name`).
        self.legacy_show_name = "My Hero Academia"
        self.base_url = "https://subslikescript.com/series/My_Hero_Academia-5626028"

        # Dictionary of common episode naming patterns for URL construction
        self.episode_patterns = {
            "standard": "/season-{season}/episode-{episode}-{title}",
            "numbered": "/season-{season}/episode-{episode}",
        }

    def search_episode_enhanced(
        self, show_name: str, season: int, episode: int, episode_title: str | None = None
    ) -> dict[str, Any] | None:
        """
        Enhanced episode discovery using search functionality across multiple sources.

        Args:
            show_name (str): Show name to search for
            season (int): Season number
            episode (int): Episode number
            episode_title (str, optional): Episode title for better matching

        Returns:
            dict: Best episode result with URL and metadata or None if not found
        """
        logger.info(f"Enhanced search for {show_name} S{season}E{episode}")

        all_results = []

        # Search across all configured sources
        for source_name, _source_config in self.search_sources.items():
            logger.info(f"Searching {source_name}...")

            try:
                results = self._search_source_episodes(
                    source_name, show_name, season, episode, episode_title
                )
                if results:
                    all_results.extend(results)
                    logger.info(f"Found {len(results)} results on {source_name}")

            except Exception as e:
                logger.error(f"Error searching {source_name}: {e}")
                continue

        if not all_results:
            logger.warning(f"No episodes found for {show_name} S{season}E{episode}")
            return None

        # Select best result based on quality scoring
        best_result = self._select_best_episode_result(all_results, season, episode)

        if best_result:
            logger.info(f"Selected best result from {best_result['source']}: {best_result['url']}")
            return best_result

        return None

    def _search_source_episodes(
        self,
        source_name: str,
        show_name: str,
        season: int,
        episode: int,
        episode_title: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search a specific source for episode URLs using search functionality."""
        source_config = self.search_sources[source_name]

        # Generate search queries
        search_queries = self._generate_search_queries(show_name, season, episode, episode_title)

        all_results = []

        for query in search_queries:
            try:
                results = self._perform_search_query(
                    source_name, source_config, query, season, episode
                )
                if results:
                    all_results.extend(results)
                    # If we found good results, we might not need to try all queries
                    if len([r for r in results if r["quality_score"] > 0.7]) > 0:
                        break

                # Add delay between searches to be respectful
                time.sleep(random.uniform(*self.delay_range))

            except Exception as e:
                logger.debug(f"Search query failed for '{query}' on {source_name}: {e}")
                continue

        return all_results

    def _generate_search_queries(
        self, show_name: str, season: int, episode: int, episode_title: str | None = None
    ) -> list[str]:
        """Generate search queries for finding episodes, prioritizing broader queries."""
        queries = []

        # Get show name variations
        show_variations = self.show_mappings.get(show_name, [show_name.lower()])
        if show_name.lower() not in show_variations:
            show_variations.append(show_name.lower())

        for show_variant in show_variations[:3]:  # Limit to top 3 variations
            # Priority 1: Broad show name queries (most likely to find series pages)
            queries.append(show_variant)

            # Priority 2: Show name with basic season info
            queries.extend([f"{show_variant} season {season}", f"{show_variant} s{season}"])

            # Priority 3: Show name with episode info (less specific)
            queries.extend(
                [
                    f"{show_variant} episode {episode}",
                    f"{show_variant} s{season}e{episode}",
                    f"{show_variant} s{season}e{episode:02d}",
                ]
            )

            # Priority 4: More specific queries (fallback)
            queries.extend(
                [
                    f"{show_variant} season {season} episode {episode}",
                    f"{show_variant} {season}x{episode}",
                    f"{show_variant} {season}x{episode:02d}",
                ]
            )

            # Priority 5: If we have episode title, include it
            if episode_title:
                clean_title = re.sub(r"[^\w\s]", "", episode_title.lower())
                queries.extend(
                    [
                        f"{show_variant} {clean_title}",
                        f"{show_variant} season {season} {clean_title}",
                        f"{show_variant} episode {episode} {clean_title}",
                    ]
                )

        # Remove duplicates while preserving order
        unique_queries = list(dict.fromkeys(queries))

        logger.debug(f"Generated {len(unique_queries)} search queries (prioritized)")
        return unique_queries

    def _perform_search_query(
        self, source_name: str, source_config: dict[str, Any], query: str, season: int, episode: int
    ) -> list[dict[str, Any]]:
        """Perform a search query on a specific source and parse results."""

        # Construct search URL and parameters
        search_url = f"{source_config['base_url']}{source_config['search_endpoint']}"

        # Handle different parameter formats
        if "search_params" in source_config:
            # Multi-parameter format (for fandom sites)
            search_params = source_config["search_params"].copy()
            search_params["query"] = query
        else:
            # Single parameter format (for subslikescript)
            search_param_name = source_config.get("search_param", "q")
            search_params = {search_param_name: query}

        logger.debug(f"Searching {source_name} with query: '{query}'")
        logger.debug(f"Search URL: {search_url}")
        logger.debug(f"Search params: {search_params}")

        # Perform search with retry logic
        for attempt in range(self.retry_count):
            try:
                if attempt > 0:
                    delay = random.uniform(*self.delay_range) * (2**attempt)
                    time.sleep(delay)

                response = self.session.get(search_url, params=search_params, timeout=30)
                response.raise_for_status()

                if not response.text:
                    logger.debug(f"Empty response from {source_name}")
                    continue

                logger.debug(f"Got response from {source_name}, parsing...")

                # Parse search results
                soup = BeautifulSoup(response.text, "html.parser")
                results = self._parse_search_results(
                    soup, source_config, source_name, season, episode
                )

                if results:
                    logger.debug(f"Found {len(results)} results from {source_name}")
                    return results
                else:
                    logger.debug(f"No results parsed from {source_name}")

            except requests.exceptions.RequestException as e:
                logger.debug(f"Search request failed for '{query}' (attempt {attempt + 1}): {e}")
                if attempt == self.retry_count - 1:
                    break
            except Exception as e:
                logger.error(f"Unexpected error in search query: {e}")
                break

        return []

    def _parse_search_results(
        self,
        soup: BeautifulSoup,
        source_config: dict[str, Any],
        source_name: str,
        season: int,
        episode: int,
    ) -> list[dict[str, Any]]:
        """Parse search results and extract episode URLs."""

        results = []

        # Try different result selectors
        for selector in source_config["result_selectors"]:
            links = soup.select(selector)

            for link in links:
                href = link.get("href")
                if not href:
                    continue

                # Convert relative URLs to absolute
                if href.startswith("/"):
                    href = urljoin(source_config["base_url"], href)

                # Extract title and context
                title_text = link.get_text(strip=True)

                # For subslikescript, if we find a series page, we need to construct episode URLs
                if (
                    source_name == "subslikescript"
                    and "/series/" in href
                    and not any(pattern in href for pattern in ["/season-", "/episode-"])
                ):
                    # This is a series page, construct episode URLs from it
                    episode_urls = self._construct_episode_urls_from_series(
                        href, season, episode, title_text
                    )
                    results.extend(episode_urls)
                    continue

                # Check if this looks like a direct episode URL
                is_episode_url = any(
                    re.search(pattern, href, re.IGNORECASE)
                    for pattern in source_config["episode_url_patterns"]
                )

                if not is_episode_url:
                    continue

                # Calculate relevance score
                quality_score = self._calculate_episode_relevance(
                    href, title_text, source_config.get("quality_indicators", []), season, episode
                )

                if quality_score > 0.1:  # Minimum relevance threshold
                    result = {
                        "source": source_name,
                        "url": href,
                        "title": title_text,
                        "quality_score": quality_score,
                        "season": season,
                        "episode": episode,
                        "found_via": "search",
                    }
                    results.append(result)

        # Sort by quality score
        results.sort(key=lambda x: x["quality_score"], reverse=True)

        return results[:5]  # Return top 5 results

    def _construct_episode_urls_from_series(
        self, series_url: str, season: int, episode: int, series_title: str
    ) -> list[dict[str, Any]]:
        """Construct possible episode URLs from a series page."""
        results = []

        # Extract series base from URL (e.g., /series/My_Hero_Academia-5626028)
        series_base = series_url.replace("https://subslikescript.com", "")

        # Common episode URL patterns for subslikescript
        episode_patterns = [
            f"{series_base}/season-{season}/episode-{episode}",
            f"{series_base}/season-{season}/episode-{episode:02d}",
            f"{series_base}/s{season}e{episode}",
            f"{series_base}/s{season}e{episode:02d}",
        ]

        for pattern in episode_patterns:
            full_url = f"https://subslikescript.com{pattern}"

            # Calculate quality score based on series match
            quality_score = 0.8  # High score since we found the exact series

            result = {
                "source": "subslikescript",
                "url": full_url,
                "title": f"{series_title} S{season}E{episode}",
                "quality_score": quality_score,
                "season": season,
                "episode": episode,
                "found_via": "series_construction",
            }
            results.append(result)

        return results

    def _calculate_episode_relevance(
        self, url: str, title_text: str, quality_indicators: list[str], season: int, episode: int
    ) -> float:
        """Calculate how relevant a search result is to the target episode."""

        score = 0.0
        url_lower = url.lower()
        title_lower = title_text.lower()
        combined_text = f"{url_lower} {title_lower}"

        # Season/Episode number matching (high weight)
        season_episode_patterns = [
            rf"s{season}e{episode}\b",
            rf"s{season}e{episode:02d}\b",
            rf"season.{season}.*episode.{episode}\b",
            rf"{season}x{episode}\b",
            rf"{season}x{episode:02d}\b",
            rf"season-{season}.*episode-{episode}\b",
        ]

        for pattern in season_episode_patterns:
            if re.search(pattern, combined_text):
                score += 0.4
                break

        # Season matching (medium weight)
        if re.search(rf"\bseason.{season}\b|\bs{season}\b", combined_text):
            score += 0.2

        # Episode matching (medium weight)
        if re.search(rf"\bepisode.{episode}\b|\be{episode}\b", combined_text):
            score += 0.2

        # Quality indicators (low weight each)
        for indicator in quality_indicators:
            if indicator.lower() in combined_text:
                score += 0.05

        # URL structure bonus
        if "episode" in url_lower or "transcript" in url_lower:
            score += 0.1

        return min(score, 1.0)

    def _select_best_episode_result(
        self, results: list[dict[str, Any]], season: int, episode: int
    ) -> dict[str, Any] | None:
        """Select the best episode result from all search results."""

        if not results:
            return None

        # Sort by quality score first
        results.sort(key=lambda x: x["quality_score"], reverse=True)

        # Validate the top results to ensure they actually contain transcript content
        for result in results[:3]:  # Check top 3 results
            if self._validate_episode_url_enhanced(result["url"]):
                return result

        # If no validated results, return the highest scoring one
        return results[0]

    def _validate_episode_url_enhanced(self, url: str) -> bool:
        """Enhanced URL validation with transcript content checking."""
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Check for common transcript content indicators
                transcript_selectors = [
                    ".full-script",
                    ".transcript-content",
                    ".transcript",
                    ".episode-content",
                    ".mw-parser-output",
                    "main .content",
                    "article",
                ]

                for selector in transcript_selectors:
                    element = soup.select_one(selector)
                    if element:
                        text_content = element.get_text(strip=True)
                        # Check if it has substantial content
                        if len(text_content) > 500:
                            return True

        except Exception as e:
            logger.debug(f"URL validation failed for {url}: {e}")

        return False

    def generate_episode_url(
        self, season: int, episode: int, episode_title: str | None = None
    ) -> str:
        """
        Generate episode URL based on season, episode number, and optional title.
        This method constructs URLs using different patterns to accommodate
        various transcript site naming conventions.

        Args:
            season (int): Season number for the episode
            episode (int): Episode number within the season
            episode_title (str, optional): Episode title for URL formatting

        Returns:
            str: Generated episode URL formatted for transcript access
        """
        if episode_title:
            # Clean up the episode title for URL compatibility
            # Remove special characters that could break URLs
            formatted_title = re.sub(r"[^\w\s-]", "", episode_title)
            # Replace spaces with underscores for URL format
            formatted_title = re.sub(r"[\s]+", "_", formatted_title)
            # Construct URL with title included
            url = f"{self.base_url}/season-{season}/episode-{episode}-{formatted_title}"
        else:
            # Use simple numbered format when no title is provided
            url = f"{self.base_url}/season-{season}/episode-{episode}"

        return url

    def validate_episode_url(self, url: str) -> bool:
        """
        Validate if an episode URL exists and contains transcript content.
        This method performs HTTP requests and HTML parsing to verify
        that a URL actually contains usable transcript data.

        Args:
            url (str): Episode URL to validate for transcript availability

        Returns:
            bool: True if URL is valid and contains transcript content, False otherwise
        """
        try:
            # Attempt to fetch the webpage
            response = requests.get(url)
            # Check if the request was successful (HTTP 200)
            if response.status_code == 200:
                # Parse the HTML content to look for transcript data
                soup = BeautifulSoup(response.text, "html.parser")
                # Look for the specific element that contains transcript content
                # This is site-specific - different transcript sites use different structures
                transcript_element = soup.find(class_="full-script")
                return transcript_element is not None
        except Exception as e:
            # Log any errors that occur during validation
            logger.error(f"URL validation failed for {url}: {e}")

        # Return False if any error occurs or content is not found
        return False

    def is_legacy_show(self, show_name: str) -> bool:
        """
        Report whether `show_name` refers to the series that `self.base_url` points at.

        The legacy URL builders (`generate_episode_url`) interpolate season/episode
        numbers into `self.base_url`, which is hardcoded to a single series. Applying
        them to any other show produces a URL that validates successfully but serves
        the wrong show's transcript, so callers must gate on this check.

        Args:
            show_name (str): Show name to compare against the legacy series

        Returns:
            bool: True if the name (or a known alias) matches the legacy series
        """
        candidate = show_name.strip().lower()
        if candidate == self.legacy_show_name.lower():
            return True
        return candidate in self.show_mappings.get(self.legacy_show_name, [])

    def discover_episode_url(
        self,
        show_name: str,
        season: int,
        episode: int,
        possible_titles: list[str] | None = None,
    ) -> str | None:
        """
        Enhanced episode URL discovery using search functionality with fallback to legacy methods.

        Args:
            show_name (str): Name of the show to discover the episode for
            season (int): Season number to search for
            episode (int): Episode number within the season
            possible_titles (list, optional): List of possible episode titles to try

        Returns:
            str or None: Valid episode URL if found, None if no valid URL discovered
        """
        episode_title = possible_titles[0] if possible_titles else None

        # Method 1: Enhanced search across multiple sources
        search_result = self.search_episode_enhanced(show_name, season, episode, episode_title)
        if search_result and search_result.get("url"):
            logger.info(f"✅ Found via enhanced search: {search_result['url']}")
            return search_result["url"]

        # Method 2: Legacy direct URL generation (fallback).
        # Only safe for the single series self.base_url points at.
        if not self.is_legacy_show(show_name):
            logger.warning(
                f"❌ Could not find valid URL for {show_name} Season {season}, Episode {episode} "
                f"(legacy URL patterns only cover {self.legacy_show_name})"
            )
            return None

        logger.info("Enhanced search failed, trying legacy methods...")

        # First attempt: Try the simplest pattern without episode title
        url = self.generate_episode_url(season, episode)
        if self.validate_episode_url(url):
            logger.info(f"✅ Found via legacy numbered pattern: {url}")
            return url

        # Second attempt: Try with each provided title
        if possible_titles:
            for title in possible_titles:
                url = self.generate_episode_url(season, episode, title)
                if self.validate_episode_url(url):
                    logger.info(f"✅ Found via legacy titled pattern: {url}")
                    return url

        # Log failure for debugging and monitoring
        logger.warning(f"❌ Could not find valid URL for Season {season}, Episode {episode}")
        return None

    def discover_episode_url_for_show(
        self, show_name: str, season: int, episode: int, possible_titles: list[str] | None = None
    ) -> str | None:
        """
        Discover episode URL for any show using enhanced search functionality.

        Kept as a named entry point; `discover_episode_url` does the work and now
        takes the show name too, so the two are the same call.

        Args:
            show_name (str): Name of the show
            season (int): Season number to search for
            episode (int): Episode number within the season
            possible_titles (list, optional): List of possible episode titles to try

        Returns:
            str or None: Valid episode URL if found, None if no valid URL discovered
        """
        return self.discover_episode_url(show_name, season, episode, possible_titles)

    def _configured_season_lengths(self, show_name: str) -> dict[int, dict]:
        """
        Return the configured season structure for `show_name`, or ``{}``.

        An empty mapping means "the season structure of this show is unknown" -
        it must not be substituted with a guessed one.

        Args:
            show_name (str): Show to look up

        Returns:
            dict[int, dict]: Season number -> season config, empty if unknown
        """
        try:
            from agents.config_manager import EpisodeConfigManager
        except ImportError:
            logger.warning(
                "Config manager not available: no show has a known season structure, "
                "every season will be probed"
            )
            return {}

        config_manager = EpisodeConfigManager()
        if show_name.strip().lower() != str(config_manager.default_config["show"]).lower():
            return {}
        return dict(config_manager.default_config["seasons"])

    def discover_all_episodes(self, show_name: str) -> list[dict]:
        """
        Enhanced discovery of all available episodes for a show across all seasons.

        For a show whose season structure is configured, every configured season is
        walked. For an unknown show the seasons are *probed*: season 1 upwards until
        a season yields no episodes at all, which is the first real signal that the
        show has run out. No season count is assumed.

        Args:
            show_name (str): The name of the show to discover episodes for

        Returns:
            List[Dict]: List of episode dictionaries with metadata. Each entry
            carries ``episode_count_source`` ("config" or "probe") and
            ``season_coverage`` ("complete" or "partial") so callers can tell a
            known season length from a probed, possibly-truncated one.
        """
        logger.info(f"Enhanced discovery of all episodes for {show_name}")

        all_episodes: list[dict] = []
        configured_seasons = self._configured_season_lengths(show_name)

        if configured_seasons:
            for season_num in sorted(configured_seasons):
                all_episodes.extend(self.discover_season_episodes(show_name, season_num))
        else:
            logger.info(
                f"No configured season structure for {show_name}: probing seasons from 1 "
                f"until one comes back empty (ceiling {self.MAX_SEASON_PROBES} seasons)"
            )
            for season_num in range(1, self.MAX_SEASON_PROBES + 1):
                season_episodes = self.discover_season_episodes(show_name, season_num)
                available_in_season = sum(1 for ep in season_episodes if ep["available"])
                all_episodes.extend(season_episodes)

                logger.info(f"Season {season_num}: {available_in_season} episodes available")

                if available_in_season == 0:
                    logger.info(
                        f"Season {season_num} of {show_name} produced no episodes; treating "
                        f"season {season_num - 1} as the last one discovered"
                    )
                    break
            else:
                logger.warning(
                    f"Hit the {self.MAX_SEASON_PROBES}-season probe ceiling for {show_name}: "
                    "this result is partial, later seasons were not looked at"
                )

        total_available = sum(1 for ep in all_episodes if ep["available"])
        logger.info(
            f"Enhanced discovery complete for {show_name}: {total_available}/{len(all_episodes)} episodes available"
        )

        return all_episodes

    def discover_season_episodes(self, show_name: str, season: int) -> list[dict]:
        """
        Enhanced season episode discovery using search functionality.

        When the season length is configured, exactly that many episodes are
        searched for. When it is not, the season is probed from episode 1 and the
        run stops after `CONSECUTIVE_MISSES_TO_STOP` consecutive episodes come
        back empty; the trailing misses are dropped rather than reported, so an
        unknown 12-episode season yields 12 entries, not a guessed 25.

        Args:
            show_name (str): The name of the show
            season (int): The season number to discover episodes for

        Returns:
            List[Dict]: List of episode dictionaries with metadata
        """
        configured_seasons = self._configured_season_lengths(show_name)
        season_config = configured_seasons.get(season)

        if season_config:
            episode_count = season_config["episodes"]
            logger.info(
                f"Enhanced discovery for {show_name} Season {season}: "
                f"{episode_count} configured episodes"
            )
            return self._probe_season_episodes(
                show_name,
                season,
                season_config.get("titles", {}),
                max_probes=episode_count,
                stop_after_misses=None,
                count_source="config",
            )

        logger.info(
            f"Enhanced discovery for {show_name} Season {season}: season length is unknown, "
            f"probing from episode 1 and stopping after {self.CONSECUTIVE_MISSES_TO_STOP} "
            f"consecutive misses (ceiling {self.MAX_EPISODE_PROBES} episodes)"
        )
        return self._probe_season_episodes(
            show_name,
            season,
            {},
            max_probes=self.MAX_EPISODE_PROBES,
            stop_after_misses=self.CONSECUTIVE_MISSES_TO_STOP,
            count_source="probe",
        )

    def _probe_season_episodes(
        self,
        show_name: str,
        season: int,
        episode_titles: dict,
        *,
        max_probes: int,
        stop_after_misses: int | None,
        count_source: str,
    ) -> list[dict]:
        """
        Search episodes of one season, one episode number at a time.

        Args:
            show_name (str): The name of the show
            season (int): Season number being walked
            episode_titles (dict): Known episode titles keyed by episode number
            max_probes (int): Highest episode number to try
            stop_after_misses (int, optional): Stop once this many consecutive
                episodes come back empty. ``None`` walks all `max_probes`
                episodes, which is only correct when the count is configured.
            count_source (str): "config" when `max_probes` is a known season
                length, "probe" when the end of the season is being inferred.

        Returns:
            List[Dict]: Episode dictionaries, without the trailing run of misses
            that ended a probe.
        """
        episodes: list[dict] = []
        pending_misses: list[dict] = []
        consecutive_misses = 0
        coverage = "complete" if count_source == "config" else "partial"
        hit_ceiling = False

        for episode_num in range(1, max_probes + 1):
            episode_title = episode_titles.get(episode_num)

            # Try to discover the episode URL using enhanced search
            search_result = self.search_episode_enhanced(
                show_name, season, episode_num, episode_title
            )

            episode_url = search_result["url"] if search_result else None

            episode_info = {
                "show": show_name,
                "season": season,
                "episode": episode_num,
                "title": episode_title,
                "url": episode_url,
                "available": episode_url is not None,
                "status": "available" if episode_url else "not_found",
                "source": search_result.get("source") if search_result else None,
                "quality_score": search_result.get("quality_score", 0.0) if search_result else 0.0,
                "found_via": search_result.get("found_via") if search_result else None,
                "episode_count_source": count_source,
                "season_coverage": coverage,
            }

            if episode_url:
                # Misses before a confirmed hit are real gaps inside the season.
                episodes.extend(pending_misses)
                pending_misses.clear()
                episodes.append(episode_info)
                consecutive_misses = 0

                source_info = f" (from {search_result.get('source', 'unknown')})"
                logger.info(
                    f"✅ Found S{season}E{episode_num}: {episode_title or 'Unknown Title'}{source_info}"
                )
            else:
                consecutive_misses += 1
                logger.debug(
                    f"❌ Not found S{season}E{episode_num}: {episode_title or 'Unknown Title'}"
                )

                if stop_after_misses is None:
                    episodes.append(episode_info)
                else:
                    # Held back: if nothing follows, these probed past the end of
                    # the season and reporting them would invent episodes.
                    pending_misses.append(episode_info)
                    if consecutive_misses >= stop_after_misses:
                        logger.info(
                            f"Stopping probe of {show_name} Season {season} after "
                            f"{consecutive_misses} consecutive misses at episode {episode_num}; "
                            f"{len(episodes)} episode(s) discovered"
                        )
                        break

            # Add small delay between searches to be respectful
            time.sleep(random.uniform(0.5, 1.5))
        else:
            hit_ceiling = stop_after_misses is not None

        if hit_ceiling:
            episodes.extend(pending_misses)
            logger.warning(
                f"Hit the {max_probes}-episode probe ceiling for {show_name} Season {season}: "
                "the season may continue past this point, the result is partial"
            )

        available_count = sum(1 for ep in episodes if ep["available"])
        logger.info(
            f"Season {season} enhanced discovery complete: {available_count}/{len(episodes)} "
            f"episodes available (episode count from: {count_source}, coverage: {coverage})"
        )

        return episodes
