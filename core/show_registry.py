#!/usr/bin/env python3
"""
Show registry and metadata validation system.
Ensures consistent show naming and metadata tagging across the vector database.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ShowMetadata:
    """
    Standardized show metadata structure.

    Represents metadata for anime shows including canonical naming,
    aliases, and status information for consistent database storage.
    """

    show_name: str  # Original name "My Hero Academia"
    show_id: str  # Canonical slug "my_hero_academia"
    aliases: list[str]  # Alternative names ["MHA", "Boku no Hero"]
    total_seasons: int  # Known seasons count
    status: str  # "ongoing", "completed", "unknown"


class ShowRegistry:
    """
    Registry of known anime shows with canonical naming.

    Maintains a centralized registry of anime shows with canonical names,
    aliases, and metadata for consistent identification across the system.
    """

    def __init__(self) -> None:
        """
        Initialize with known shows.

        Sets up the registry with pre-configured anime show metadata
        and creates mappings for aliases to canonical identifiers.
        """
        self.shows: dict[str, ShowMetadata] = {}
        self._initialize_known_shows()

    def _initialize_known_shows(self) -> None:
        """
        Initialize registry with known anime shows.

        Sets up the registry with pre-configured show metadata including
        canonical names, aliases, season counts, and status information.
        """
        known_shows = [
            ShowMetadata(
                "My Hero Academia", "my_hero_academia", ["MHA", "Boku no Hero"], 7, "ongoing"
            ),
            ShowMetadata(
                "Attack on Titan", "attack_on_titan", ["AoT", "Shingeki no Kyojin"], 4, "completed"
            ),
            ShowMetadata("Demon Slayer", "demon_slayer", ["Kimetsu no Yaiba"], 4, "ongoing"),
            # Add more shows as needed
        ]

        for show in known_shows:
            self.shows[show.show_id] = show
            # Also map aliases to canonical ID
            for alias in show.aliases:
                self.shows[self._slugify(alias)] = show

    def _slugify(self, name: str) -> str:
        """
        Convert show name to canonical slug.

        Args:
            name: Show name to convert

        Returns:
            Canonical slug identifier with only lowercase letters, numbers, and underscores
        """
        return re.sub(r"[^a-z0-9]+", "_", name.lower().strip())

    def get_canonical_show(self, show_name: str) -> ShowMetadata | None:
        """
        Get canonical show metadata from any name/alias.

        Args:
            show_name: Show name or alias to look up

        Returns:
            ShowMetadata object if found, None otherwise
        """
        slug = self._slugify(show_name)
        return self.shows.get(slug)

    def validate_show_name(self, show_name: str) -> str:
        """
        Validate and return canonical show name.

        Args:
            show_name: Show name to validate

        Returns:
            Canonical show name from registry, or original name if not found
        """
        show_meta = self.get_canonical_show(show_name)
        if not show_meta:
            logger.warning(f"Unknown show: {show_name}. Adding to registry.")
            # Auto-add new shows (with validation prompt in production)
            new_show = ShowMetadata(show_name, self._slugify(show_name), [], 0, "unknown")
            self.shows[new_show.show_id] = new_show
            return show_name
        return show_meta.show_name

    def get_show_id(self, show_name: str) -> str:
        """
        Get canonical show ID for a show name.

        Args:
            show_name: Show name to get ID for

        Returns:
            Canonical show ID slug
        """
        show_meta = self.get_canonical_show(show_name)
        return show_meta.show_id if show_meta else self._slugify(show_name)


# Global registry instance
show_registry = ShowRegistry()
