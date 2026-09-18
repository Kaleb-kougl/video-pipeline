#!/usr/bin/env python3
"""
Tests for DatabaseManager class to validate sqlite3.Row object access patterns.

This test suite validates the database access patterns that were fixed, ensuring
that sqlite3.Row objects are accessed correctly using square bracket notation
instead of the .get() method.
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

from core.database import DatabaseManager


class TestDatabaseManager:
    """Test suite for DatabaseManager class focusing on Row object access."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, temp_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)  # Close the file descriptor, we just need the path
        db = DatabaseManager(temp_path)
        yield db, temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_database_initialization(self, temp_db):
        """Test that the database initializes correctly."""
        db, temp_path = temp_db
        
        # Verify the database file was created
        assert os.path.exists(temp_path)
        
        # Verify tables were created
        with sqlite3.connect(temp_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('episodes', 'processing_logs')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            assert 'episodes' in tables
            assert 'processing_logs' in tables

    def test_save_and_get_episode(self, temp_db):
        """Test saving and retrieving episode data."""
        db, _ = temp_db
        
        # Save test episode data
        test_data = {
            'show': 'My Hero Academia',
            'season': '1',
            'episode': '4', 
            'url': 'https://test.com/transcript',
            'transcript': 'Test transcript content',
            'summary': 'Test episode summary',
            'plot_points': ['Point 1', 'Point 2']
        }
        
        db.save_episode(
            test_data['show'],
            test_data['season'],
            test_data['episode'],
            test_data['url'],
            test_data['transcript'],
            test_data['summary'],
            test_data['plot_points']
        )
        
        # Retrieve the episode
        result = db.get_episode(
            test_data['show'],
            test_data['season'],
            test_data['episode']
        )
        
        # Verify the result is a sqlite3.Row object
        assert result is not None
        assert isinstance(result, sqlite3.Row)
        
        # Test square bracket access (correct method)
        assert result['show'] == test_data['show']
        assert result['season'] == test_data['season'] 
        assert result['episode'] == test_data['episode']
        assert result['url'] == test_data['url']
        assert result['transcript'] == test_data['transcript']
        assert result['summary'] == test_data['summary']

    def test_sqlite_row_access_patterns(self, temp_db):
        """Test the correct access patterns for sqlite3.Row objects."""
        db, _ = temp_db
        
        # Save test data
        db.save_episode('Test Show', '1', '1', 'https://test.com', 
                       'Test transcript', 'Test summary', ['plot1'])
        
        # Get the episode
        episode_data = db.get_episode('Test Show', '1', '1')
        
        # Test that square bracket access works
        assert episode_data['transcript'] == 'Test transcript'
        assert episode_data['summary'] == 'Test summary'
        
        # Test that .get() method does NOT exist (this should raise AttributeError)
        with pytest.raises(AttributeError):
            episode_data.get('transcript')
        
        # Test accessing non-existent column raises IndexError (not KeyError!)
        with pytest.raises(IndexError):
            episode_data['non_existent_column']
        
        # Test that we can safely check for existence
        assert 'transcript' in episode_data.keys()
        assert 'non_existent_column' not in episode_data.keys()

    def test_episode_data_none_handling(self, temp_db):
        """Test handling of None values in episode data."""
        db, _ = temp_db
        
        # Save episode with None values
        db.save_episode('Test Show', '1', '2', 'https://test.com',
                       None, None, None)
        
        episode_data = db.get_episode('Test Show', '1', '2')
        
        # Test accessing None values
        assert episode_data['transcript'] is None
        assert episode_data['summary'] is None
        assert episode_data['plot_points'] is None
        
        # Test boolean evaluation (important for our conditional checks)
        assert not episode_data['transcript']  # None should be falsy
        assert not episode_data['summary']
        assert not episode_data['plot_points']

    def test_get_episodes_by_show(self, temp_db):
        """Test retrieving multiple episodes for a show."""
        db, _ = temp_db
        
        # Save multiple episodes
        for ep in range(1, 4):
            db.save_episode(
                'Test Show', '1', str(ep), f'https://test.com/{ep}',
                f'Transcript {ep}', f'Summary {ep}', [f'Plot {ep}']
            )
        
        # Get all episodes for the show
        episodes = db.get_episodes_by_show('Test Show', '1')
        
        assert len(episodes) == 3
        
        # Test that each result is a sqlite3.Row object
        for episode in episodes:
            assert isinstance(episode, sqlite3.Row)
            # Test square bracket access
            assert episode['show'] == 'Test Show'
            assert episode['season'] == '1'
            assert episode['episode'] in ['1', '2', '3']

    def test_episode_not_found(self, temp_db):
        """Test behavior when episode is not found."""
        db, _ = temp_db
        
        # Try to get non-existent episode
        result = db.get_episode('Non-existent Show', '1', '1')
        
        assert result is None

    def test_database_error_handling(self, temp_db):
        """Test database error handling."""
        db, temp_path = temp_db
        
        # Close and remove the database file to simulate error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        
        # This should handle the error gracefully
        result = db.get_episode('Test Show', '1', '1')
        assert result is None

    def test_conditional_checks_with_row_data(self, temp_db):
        """Test the conditional patterns used in main code."""
        db, _ = temp_db
        
        # Test case 1: Episode with transcript
        db.save_episode('Show1', '1', '1', 'url1', 'Has transcript', None, None)
        
        # Test case 2: Episode without transcript  
        db.save_episode('Show2', '1', '1', 'url2', None, None, None)
        
        # Test case 3: Episode with empty string transcript
        db.save_episode('Show3', '1', '1', 'url3', '', None, None)
        
        # Test the conditional patterns used in our code
        episode1 = db.get_episode('Show1', '1', '1')
        episode2 = db.get_episode('Show2', '1', '1')  
        episode3 = db.get_episode('Show3', '1', '1')
        
        # Test the patterns: if not episode_data or not episode_data['transcript']:
        assert not (not episode1 or not episode1['transcript'])  # Should pass condition
        assert (not episode2 or not episode2['transcript'])       # Should fail condition
        assert (not episode3 or not episode3['transcript'])       # Should fail condition (empty string)

    def test_main_code_integration_patterns(self, temp_db):
        """Test the exact patterns used in main_refactored.py."""
        db, _ = temp_db
        
        # Save test episode
        db.save_episode(
            'My Hero Academia', '1', '4', 'https://test.com',
            'Full transcript content', 'Episode summary', ['Plot point']
        )
        
        # Test the exact pattern from main code
        show_name, season, episode = 'My Hero Academia', '1', '4'
        episode_data = db.get_episode(show_name, season, episode)
        
        # This should work (the pattern we fixed)
        if not episode_data or not episode_data['transcript']:
            pytest.fail("Episode should have transcript")
        
        # Test accessing transcript in content generation
        transcript = episode_data['transcript']
        assert transcript == 'Full transcript content'
        
        # Test the pattern would fail with missing data
        db.save_episode('Test Show', '1', '1', 'url', None, None, None)
        missing_data = db.get_episode('Test Show', '1', '1')
        
        # This should trigger the conditional
        if not missing_data or not missing_data['transcript']:
            # This is the expected path for missing transcript
            assert True
        else:
            pytest.fail("Should have detected missing transcript")


class TestSqliteRowBehavior:
    """Test sqlite3.Row behavior to document expected patterns."""
    
    def test_row_object_methods(self):
        """Document the methods available on sqlite3.Row objects."""
        # Create in-memory database
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        
        # Create test table and data
        conn.execute('CREATE TABLE test (id INTEGER, name TEXT, value TEXT)')
        conn.execute("INSERT INTO test VALUES (1, 'test', 'data')")
        
        # Get a Row object
        cursor = conn.execute('SELECT * FROM test')
        row = cursor.fetchone()
        
        # Document available methods and properties
        assert hasattr(row, 'keys')  # Has keys() method
        assert callable(row.keys)
        
        # Test keys() method
        keys = row.keys()
        assert list(keys) == ['id', 'name', 'value']
        
        # Test dictionary-like access
        assert row['id'] == 1
        assert row['name'] == 'test'
        assert row['value'] == 'data'
        
        # Test that .get() method does NOT exist
        assert not hasattr(row, 'get')
        
        # Test index access
        assert row[0] == 1
        assert row[1] == 'test' 
        assert row[2] == 'data'
        
        # Test iteration
        values = list(row)
        assert values == [1, 'test', 'data']
        
        # Test len()
        assert len(row) == 3
        
        # Test 'in' operator with keys
        assert 'id' in row.keys()
        assert 'non_existent' not in row.keys()
        
        conn.close()

    def test_row_error_handling(self):
        """Test error handling with Row objects."""
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        
        conn.execute('CREATE TABLE test (id INTEGER, name TEXT)')
        conn.execute("INSERT INTO test VALUES (1, 'test')")
        
        cursor = conn.execute('SELECT * FROM test')
        row = cursor.fetchone()
        
        # Test IndexError for non-existent column (sqlite3.Row raises IndexError, not KeyError)
        with pytest.raises(IndexError):
            row['non_existent']
        
        # Test IndexError for out-of-range index
        with pytest.raises(IndexError):
            row[10]
        
        # Test AttributeError for .get() method
        with pytest.raises(AttributeError):
            row.get('id')
        
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
