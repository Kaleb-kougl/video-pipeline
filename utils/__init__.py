"""
Utility functions and helpers for the Anime Video Generator.

This package provides utility functions for web scraping, vector search,
and other common operations used throughout the system.
"""

from .vector_search import VectorSearchManager
from .web_utils import get_html_content, parse_html_with_beautifulsoup

__all__ = ["get_html_content", "parse_html_with_beautifulsoup", "VectorSearchManager"]
