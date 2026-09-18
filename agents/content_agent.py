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

    def extract_and_analyze(self, url: str) -> dict[str, Any]:
        """
        Extract HTML content from a URL, parse it, and use an AI model to analyze it.

        This method implements retry logic to handle network issues and temporary failures.
        It combines web scraping with AI analysis to provide comprehensive content extraction.

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
        from utils.web_utils import get_html_content, parse_html_with_beautifulsoup

        # Implement retry logic to handle temporary network failures
        for attempt in range(self.retry_count):
            try:
                # Step 1: Attempt to get HTML content from the URL
                # This function handles HTTP requests and basic error handling
                html_content = get_html_content(url)
                if html_content:
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
                break  # Exit retry loop on successful content extraction
            except Exception as e:
                # Log the error with attempt number for debugging
                logger.error(f"Content extraction attempt {attempt + 1} failed: {e}")
                if attempt == self.retry_count - 1:
                    # All retry attempts have been exhausted, return failure
                    return {"success": False, "error": str(e)}

        # Fallback return if loop completes without success (shouldn't happen with current logic)
        return {"success": False, "error": "Max retries exceeded"}
