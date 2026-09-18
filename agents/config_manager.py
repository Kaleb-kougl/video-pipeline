"""
Manager for episode configurations and batch processing settings.
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class EpisodeConfigManager:
    """
    Manages episode configurations and batch processing settings.
    
    This class handles the configuration of anime series data including
    season information, episode counts, and known episode titles.
    It provides structured data management for batch processing operations.
    """
    
    def __init__(self):
        """
        Initialize configuration manager with default series settings.
        Sets up the basic structure for My Hero Academia episode management.
        """
        # Default configuration with series structure
        # This defines the basic framework for the anime series
        self.default_config = {
            "show": "My Hero Academia",
            # Season structure with episode counts and title storage
            "seasons": {
                1: {"episodes": 13, "titles": {}},  # First season episode count
                2: {"episodes": 25, "titles": {}},  # Subsequent seasons
                3: {"episodes": 25, "titles": {}},
                4: {"episodes": 25, "titles": {}},
                5: {"episodes": 25, "titles": {}},
                6: {"episodes": 25, "titles": {}},
                7: {"episodes": 21, "titles": {}}   # Latest season (may vary)
            }
        }
        # Load any known episode titles for better URL generation
        self.load_episode_titles()
    
    def load_episode_titles(self):
        """
        Load known episode titles for better URL generation.
        
        This method populates the configuration with actual episode titles
        to improve URL discovery success rates. Currently loads Season 1
        titles for My Hero Academia as reference implementation.
        """
        # Sample episode titles for Season 1 of My Hero Academia
        # These titles help generate accurate URLs for transcript sources
        season_1_titles = {
            1: "Izuku_Midoriya_Origin",           # Series pilot episode
            2: "What_It_Takes_to_Be_a_Hero",     # Hero fundamentals
            3: "Roaring_Muscles",                # Physical training focus
            4: "Start_Line",                     # Competition beginning
            5: "What_I_Can_Do_for_Now",          # Character development
            6: "Rage_You_Damn_Nerd",             # Conflict episode
            7: "Deku_vs_Kacchan",                # Major character confrontation
            8: "Bakugo's_Start_Line",            # Character backstory
            9: "Yeah_Just_Do_Your_Best_Ida",     # Supporting character focus
            10: "Encounter_with_the_Unknown",    # Plot advancement
            11: "Game_Over",                     # Crisis episode
            12: "All_Might",                     # Mentor focus
            13: "In_Each_of_Our_Hearts"          # Season finale
        }
        
        # Store the titles in the configuration structure
        self.default_config["seasons"][1]["titles"] = season_1_titles
    
    def get_episode_config(self, season: int, episode: int) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific episode.
        This method retrieves all relevant metadata for an episode
        including title information and season context.
        
        Args:
            season (int): Season number to get configuration for
            episode (int): Episode number within the season
            
        Returns:
            dict: Episode configuration with show name, season, episode, title, and limits
        """
        # Check if the requested season exists in our configuration
        if season in self.default_config["seasons"]:
            season_config = self.default_config["seasons"][season]
            # Get the episode title if available, None if not found
            episode_title = season_config["titles"].get(episode)
            
            # Return comprehensive episode configuration
            return {
                "show": self.default_config["show"],        # Show name
                "season": season,                           # Season number
                "episode": episode,                         # Episode number
                "title": episode_title,                     # Episode title (may be None)
                "max_episodes": season_config["episodes"]   # Total episodes in season
            }
        
        # Return None if season is not configured
        return None
    
    def get_season_episodes(self, season: int) -> List[int]:
        """
        Get all episode numbers for a season.
        This method provides a complete list of episode numbers
        for batch processing operations.
        
        Args:
            season (int): Season number to get episode list for
            
        Returns:
            list: List of episode numbers (1 to max_episodes), empty list if season not found
        """
        # Check if the season exists in our configuration
        if season in self.default_config["seasons"]:
            # Get the maximum number of episodes for this season
            max_episodes = self.default_config["seasons"][season]["episodes"]
            # Generate a list from 1 to max_episodes (inclusive)
            return list(range(1, max_episodes + 1))
        
        # Return empty list if season is not configured
        return []
