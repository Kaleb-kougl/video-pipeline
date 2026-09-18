"""
Database management for storing and retrieving episode information.
"""

import sqlite3
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages the SQLite database for storing and retrieving episode information."""
    
    def __init__(self, db_path: str = "data/databases/video_generator.db"):
        """
        Initialize the DatabaseManager.

        Args:
            db_path (str): The path to the SQLite database file.
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self) -> None:
        """Initialize the database tables if they don't already exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Create the 'episodes' table to store details about each show episode.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show TEXT NOT NULL,
                    season TEXT NOT NULL,
                    episode TEXT NOT NULL,
                    url TEXT NOT NULL,
                    transcript TEXT,
                    summary TEXT,
                    plot_points TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(show, season, episode)
                )
            """)
            
            # Create the 'processing_logs' table to log the status of various tasks.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    processing_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (episode_id) REFERENCES episodes (id)
                )
            """)
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_show_season_episode 
                ON episodes(show, season, episode)
            """)
            
            logger.info("Database initialized successfully")
    
    def save_episode(self, show: str, season: str, episode: str, url: str, 
                    transcript: Optional[str] = None, summary: Optional[str] = None, 
                    plot_points: Optional[list] = None) -> None:
        """
        Save or update an episode's data in the database.

        Args:
            show (str): The name of the show.
            season (str): The season number.
            episode (str): The episode number.
            url (str): The URL of the episode transcript.
            transcript (str, optional): The full transcript.
            summary (str, optional): The summary of the episode.
            plot_points (list, optional): A list of key plot points.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO episodes 
                    (show, season, episode, url, transcript, summary, plot_points, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (show, season, episode, url, transcript, summary, 
                     json.dumps(plot_points) if plot_points else None))
                
                logger.info(f"Saved episode: {show} S{season}E{episode}")
                
        except sqlite3.Error as e:
            logger.error(f"Database error saving episode {show} S{season}E{episode}: {e}")
            raise
    
    def get_episode(self, show: str, season: str, episode: str) -> Optional[sqlite3.Row]:
        """
        Retrieve a specific episode's data from the database.

        Args:
            show (str): The name of the show.
            season (str): The season number.
            episode (str): The episode number.

        Returns:
            sqlite3.Row: The episode data, or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM episodes WHERE show = ? AND season = ? AND episode = ?
                """, (show, season, episode))
                result = cursor.fetchone()
                
                if result:
                    logger.debug(f"Retrieved episode: {show} S{season}E{episode}")
                
                return result
                
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving episode {show} S{season}E{episode}: {e}")
            return None
    
    def get_episodes_by_show(self, show: str, season: Optional[str] = None) -> list:
        """
        Get all episodes for a show, optionally filtered by season.
        
        Args:
            show (str): The name of the show.
            season (str, optional): The season number to filter by.
            
        Returns:
            list: List of episode rows.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if season:
                    cursor = conn.execute("""
                        SELECT * FROM episodes 
                        WHERE show = ? AND season = ? 
                        ORDER BY CAST(season AS INTEGER), CAST(episode AS INTEGER)
                    """, (show, season))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM episodes 
                        WHERE show = ? 
                        ORDER BY CAST(season AS INTEGER), CAST(episode AS INTEGER)
                    """, (show,))
                
                return cursor.fetchall()
                
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving episodes for {show}: {e}")
            return []
    
    def log_processing_task(self, episode_id: int, task_type: str, status: str, 
                          error_message: Optional[str] = None, processing_time: Optional[float] = None) -> None:
        """
        Log a processing task to the database.
        
        Args:
            episode_id (int): The episode ID.
            task_type (str): Type of task (e.g., 'transcript_discovery', 'video_generation').
            status (str): Task status ('pending', 'completed', 'failed').
            error_message (str, optional): Error message if task failed.
            processing_time (float, optional): Time taken to complete task in seconds.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO processing_logs 
                    (episode_id, task_type, status, error_message, processing_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (episode_id, task_type, status, error_message, processing_time))
                
                logger.debug(f"Logged processing task: {task_type} - {status}")
                
        except sqlite3.Error as e:
            logger.error(f"Database error logging task: {e}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            dict: Statistics about processed episodes.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get episode counts by status
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM episodes 
                    GROUP BY status
                """)
                status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # Get total episodes
                cursor = conn.execute("SELECT COUNT(*) as total FROM episodes")
                total = cursor.fetchone()['total']
                
                # Get recent processing activity
                cursor = conn.execute("""
                    SELECT task_type, status, COUNT(*) as count 
                    FROM processing_logs 
                    WHERE created_at > datetime('now', '-24 hours')
                    GROUP BY task_type, status
                """)
                recent_activity = cursor.fetchall()
                
                return {
                    'total_episodes': total,
                    'status_counts': status_counts,
                    'recent_activity': [dict(row) for row in recent_activity]
                }
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting stats: {e}")
            return {'total_episodes': 0, 'status_counts': {}, 'recent_activity': []}
    
    def update_episode_status(self, show: str, season: str, episode: str, status: str) -> None:
        """
        Update the status of an episode.
        
        Args:
            show (str): The name of the show.
            season (str): The season number.
            episode (str): The episode number.
            status (str): New status ('pending', 'completed', 'failed').
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE episodes 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE show = ? AND season = ? AND episode = ?
                """, (status, show, season, episode))
                
                logger.debug(f"Updated episode status: {show} S{season}E{episode} -> {status}")
                
        except sqlite3.Error as e:
            logger.error(f"Database error updating episode status: {e}")
            raise

    def init_season_summaries_table(self) -> None:
        """Initialize the season summaries table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS season_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    analysis_data TEXT,
                    media_files TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(show, season)
                )
            """)
            logger.debug("Season summaries table initialized")

    def save_season_summary(self, show: str, season: int, summary: str, 
                          analysis_data: Dict = None, media_files: Dict = None) -> int:
        """
        Save or update a season summary.
        
        Args:
            show: Show name
            season: Season number
            summary: Season summary text
            analysis_data: Analysis data dictionary
            media_files: Media files dictionary
            
        Returns:
            The ID of the saved summary
        """
        # Ensure table exists
        self.init_season_summaries_table()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Convert dictionaries to JSON strings
                analysis_json = json.dumps(analysis_data) if analysis_data else None
                media_json = json.dumps(media_files) if media_files else None
                
                # Use INSERT OR REPLACE to handle duplicates
                cursor = conn.execute("""
                    INSERT OR REPLACE INTO season_summaries 
                    (show, season, summary, analysis_data, media_files, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (show, season, summary, analysis_json, media_json))
                
                summary_id = cursor.lastrowid
                logger.info(f"Saved season summary: {show} Season {season} (ID: {summary_id})")
                return summary_id
                
        except sqlite3.Error as e:
            logger.error(f"Database error saving season summary: {e}")
            raise

    def get_season_summary(self, show: str, season: int) -> Optional[Dict]:
        """
        Retrieve a season summary.
        
        Args:
            show: Show name
            season: Season number
            
        Returns:
            Dictionary with summary data or None if not found
        """
        # Ensure table exists
        self.init_season_summaries_table()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM season_summaries 
                    WHERE show = ? AND season = ?
                """, (show, season))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'show': row['show'],
                        'season': row['season'],
                        'summary': row['summary'],
                        'analysis_data': json.loads(row['analysis_data']) if row['analysis_data'] else None,
                        'media_files': json.loads(row['media_files']) if row['media_files'] else None,
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving season summary: {e}")
            return None

    def get_all_season_summaries(self, show: str = None) -> List[Dict]:
        """
        Retrieve all season summaries, optionally filtered by show.
        
        Args:
            show: Optional show name to filter by
            
        Returns:
            List of season summary dictionaries
        """
        # Ensure table exists
        self.init_season_summaries_table()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if show:
                    cursor = conn.execute("""
                        SELECT * FROM season_summaries 
                        WHERE show = ?
                        ORDER BY season
                    """, (show,))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM season_summaries 
                        ORDER BY show, season
                    """)
                
                summaries = []
                for row in cursor.fetchall():
                    summaries.append({
                        'id': row['id'],
                        'show': row['show'],
                        'season': row['season'],
                        'summary': row['summary'],
                        'analysis_data': json.loads(row['analysis_data']) if row['analysis_data'] else None,
                        'media_files': json.loads(row['media_files']) if row['media_files'] else None,
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    })
                
                return summaries
                
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving season summaries: {e}")
            return []
