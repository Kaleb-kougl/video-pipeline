"""
Agent for extracting and analyzing content from episode transcript URLs.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContentAgent:
    """
    Agent responsible for extracting and analyzing content from a URL.

    This agent handles the web scraping and initial AI analysis of episode transcripts.
    It manages HTTP requests, HTML parsing, and coordinates with AI models for content analysis.
    """

    def __init__(self, model):
        """
        Initialize the ContentAgent with an AI model for content analysis.

        Args:
            model: The generative AI model instance to use for content analysis.
                  Expected to have methods for text processing and analysis.
        """
        self.model = model
        self.retry_count = 3  # Number of retry attempts for failed requests
        self.delay_range = (0.5, 1.5)  # Jitter (seconds) for the retry backoff

    def extract_and_analyze(self, url: str) -> dict[str, Any]:
        """
        Extract HTML content from a URL, parse it, and use an AI model to analyze it.

        This method implements retry logic to handle network issues and temporary failures.
        It combines web scraping with AI analysis to provide comprehensive content extraction.

        Note on a fixed bug: the previous hand-rolled loop had its ``break`` on
        the *failure* branch. ``get_html_content`` returns ``None`` (it does not
        raise) when a page cannot be fetched, so an unreachable URL fell straight
        through to ``break`` on the first pass and the method returned
        ``"Max retries exceeded"`` having made exactly one attempt. The retry
        that the docstring advertised never happened for the single most common
        failure. Retries now go through ``utils.retry.with_http_retries``, which
        treats a falsy result as a retryable attempt.

        Args:
            url (str): The URL to extract content from (typically an episode transcript page)

        Returns:
            Dict[str, Any]: A dictionary containing:
                - transcript (str): Full episode transcript text
                - title (str): Episode title
                - episode (str): Episode identifier
                - analysis (str): AI-generated content analysis
                - success (bool): Whether the operation succeeded
        """
        # Import utilities here to avoid circular imports
        from utils.retry import with_http_retries
        from utils.web_utils import get_html_content, parse_html_with_beautifulsoup

        def _attempt() -> dict[str, Any] | None:
            # Step 1: Attempt to get HTML content from the URL.
            # get_html_content swallows requests errors and returns None, so an
            # unreachable page arrives here as a falsy value, not an exception.
            # Returning None asks the retry policy to try again - which is what
            # the old loop only *looked* like it did (see the docstring note).
            html_content = get_html_content(url)
            if not html_content:
                return None

            # Step 2: Parse the HTML to extract transcript and metadata
            # BeautifulSoup parsing extracts structured data from raw HTML
            transcript, title, episode = parse_html_with_beautifulsoup(html_content)

            # Step 3: Create a focused analysis prompt for the AI model
            # Truncate transcript to avoid token limits while preserving key content
            analysis_prompt = f"""
                    Analyze this episode transcript and extract:
                    1. Main characters mentioned
                    2. Key themes
                    3. Content rating/age appropriateness
                    4. Emotional tone

                    Transcript: {transcript[:1000] if transcript else ""}...
                    Title: {title}
                    """

            # Step 4: Get AI analysis of the content
            # This provides metadata that can be used for content classification
            analysis = self.model.invoke(analysis_prompt)

            # Return successful result with all extracted data
            return {
                "transcript": transcript,
                "title": title,
                "episode": episode,
                "analysis": analysis,
                "success": True,
            }

        try:
            result = with_http_retries(
                _attempt,
                attempts=self.retry_count,
                delay_range=self.delay_range,
                logger=logger,
                description=f"Content extraction from {url}",
            )
        except Exception as e:
            # Deliberately broad: this is the agent's public boundary and the
            # orchestrator's contract is a result dict, not an exception (see
            # workflow_orchestrator, which branches on result["success"]).
            # `self.model` is an injected third-party client whose failure modes
            # are provider-specific, so there is no narrower type to name here.
            # `logger.exception` keeps the traceback that the old handler threw
            # away.
            logger.exception(f"Content extraction from {url} failed")
            return {"success": False, "error": str(e)}

        if result is None:
            return {
                "success": False,
                "error": f"No content could be retrieved from {url} "
                f"after {self.retry_count} attempts",
            }

        return result
