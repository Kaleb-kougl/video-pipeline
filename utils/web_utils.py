"""
Web scraping and HTML parsing utilities.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def get_html_content(url: str) -> str:
    """
    Fetches the HTML content from a given URL.
    This function handles HTTP requests with proper error handling
    to retrieve webpage content for transcript extraction.

    Args:
        url (str): The URL of the webpage to fetch

    Returns:
        str: The HTML content of the page, or None if an error occurs
    """
    logger.debug(f"Retrieving HTML from: {url}")
    try:
        # Make HTTP GET request to fetch webpage content
        response = requests.get(url)
        # Raise an HTTPError for bad responses (4xx or 5xx status codes)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        # Log and handle any network or HTTP errors
        logger.error(f"Error fetching URL {url}: {e}")
        return None


def parse_html_with_beautifulsoup(html_content: str) -> tuple:
    """
    Parses HTML content using BeautifulSoup and extracts various information.
    This function specifically targets transcript content from episode pages
    and extracts metadata like title and episode information.

    Args:
        html_content (str): The HTML content as a string to parse

    Returns:
        tuple: (transcript_text, title, episode) - extracted content and metadata
    """
    logger.debug("Parsing HTML content")
    if not html_content:
        logger.warning("No HTML content to parse.")
        return None, None, None

    # Parse HTML content using BeautifulSoup for element extraction
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract the page title from the h1 element
    title = soup.find("h1")
    if title:
        title = title.get_text()

    # Use regex to extract season and episode information from title
    match = re.search(r"Season \d+, Episode \d+", title) if title else None
    episode = match.group(0) if match else "Unknown Episode"

    # Find the transcript content using the specific class name
    # This is site-specific - different transcript sites use different structures
    items = soup.find(class_="full-script")
    if items:
        # Return the transcript text along with metadata
        return items.get_text(), title, episode
    else:
        logger.warning("No elements with class 'full-script' found.")
        return None, title, episode
