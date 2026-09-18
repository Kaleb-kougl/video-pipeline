#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression tests for file path consistency in media generation.

This test suite validates that file path construction is consistent between
image generation and video creation functions, preventing issues where
videos look for images that don't exist due to path mismatches.
"""

import sys
import os
import unittest.mock as mock
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_file_path_consistency():
    """Test that file paths are consistent between media generation functions.
    
    This test validates that:
    1. Image generation saves files to predictable paths
    2. Video creation looks for images at the same paths
    3. Season-level processing uses consistent path patterns
    4. Episode-level processing uses consistent path patterns
    
    Returns:
        bool: True if all tests pass, False otherwise
    """
    
    print("🧪 Testing File Path Consistency in Media Generation")
    print("=" * 60)
    
    success_count = 0
    total_tests = 0
    
    # Test 1: Episode-level path consistency
    print("\n1️⃣ Testing Episode-level Path Consistency")
    total_tests += 1
    
    try:
        # Mock all the external dependencies
        with mock.patch('media.media_utils.genai'):
            with mock.patch('media.media_utils.types'):
                with mock.patch('media.media_utils.Image'):
                    with mock.patch('media.media_utils.os.makedirs'):
                        with mock.patch('media.media_utils.ImageClip'):
                            with mock.patch('media.media_utils.VideoFileClip'):
                                with mock.patch('media.media_utils.AudioFileClip'):
                                    
                                    # Test parameters
                                    show = "Test Show"
                                    season = "1"
                                    episode = "1"
                                    
                                    # Capture the path used by create_image
                                    saved_paths = []
                                    
                                    def mock_save(path):
                                        saved_paths.append(path)
                                    
                                    mock_image = mock.Mock()
                                    mock_image.save = mock_save
                                    
                                    with mock.patch('media.media_utils.Image.new', return_value=mock_image):
                                        from media.media_utils import create_image, mp4_file_enhanced
                                        
                                        # Generate an image
                                        create_image("test prompt", episode, season, show, 0)
                                        
                                        # Check the saved path
                                        expected_image_path = f"{show}/Season{season}/Episode{episode}/{show}_{episode}_0.png"
                                        
                                        assert len(saved_paths) > 0, "No image was saved"
                                        actual_path = saved_paths[0]
                                        
                                        assert actual_path == expected_image_path, \
                                            f"Image saved to {actual_path}, expected {expected_image_path}"
                                        
                                        # Now test if mp4_file_enhanced looks for images at the same path
                                        captured_image_paths = []
                                        
                                        def mock_image_clip(path):
                                            captured_image_paths.append(path)
                                            return mock.Mock()
                                        
                                        with mock.patch('media.media_utils.ImageClip', side_effect=mock_image_clip):
                                            # This should look for images at the same paths
                                            sentences = ["test sentence"]
                                            durations = [1.0]
                                            mp4_file_enhanced(show, season, episode, sentences, durations)
                                            
                                            # Verify the video function looks for images at correct paths
                                            assert len(captured_image_paths) > 0, "No image paths were used"
                                            video_image_path = captured_image_paths[0]
                                            
                                            assert video_image_path == expected_image_path, \
                                                f"Video looks for {video_image_path}, but image saved to {actual_path}"
                                        
                                        print("    ✅ Episode-level paths are consistent between image generation and video creation")
                                        success_count += 1
                            
    except Exception as e:
        print(f"    ❌ Episode-level path consistency test failed: {e}")
    
    # Test 2: Season-level path consistency
    print("\n2️⃣ Testing Season-level Path Consistency")
    total_tests += 1
    
    try:
        with mock.patch('media.media_utils.genai'):
            with mock.patch('media.media_utils.types'):
                with mock.patch('media.media_utils.Image'):
                    with mock.patch('media.media_utils.os.makedirs'):
                        with mock.patch('media.media_utils.ImageClip'):
                            with mock.patch('media.media_utils.VideoFileClip'):
                                with mock.patch('media.media_utils.AudioFileClip'):
                                    
                                    # Test parameters for season summary
                                    show = "Test Show"
                                    season = "1"
                                    episode = "Season_1"  # This is how season summaries work
                                    
                                    saved_paths = []
                                    
                                    def mock_save(path):
                                        saved_paths.append(path)
                                    
                                    mock_image = mock.Mock()
                                    mock_image.save = mock_save
                                    
                                    with mock.patch('media.media_utils.Image.new', return_value=mock_image):
                                        from media.media_utils import create_image, mp4_file_enhanced
                                        
                                        # Generate an image for season summary
                                        create_image("test season prompt", episode, season, show, 0)
                                        
                                        # Check the saved path
                                        expected_image_path = f"{show}/Season{season}/Episode{episode}/{show}_{episode}_0.png"
                                        
                                        assert len(saved_paths) > 0, "No season image was saved"
                                        actual_path = saved_paths[0]
                                        
                                        assert actual_path == expected_image_path, \
                                            f"Season image saved to {actual_path}, expected {expected_image_path}"
                                        
                                        # Test video creation for season summary
                                        captured_image_paths = []
                                        
                                        def mock_image_clip(path):
                                            captured_image_paths.append(path)
                                            return mock.Mock()
                                        
                                        with mock.patch('media.media_utils.ImageClip', side_effect=mock_image_clip):
                                            sentences = ["season summary sentence"]
                                            durations = [5.0]
                                            mp4_file_enhanced(show, season, episode, sentences, durations)
                                            
                                            assert len(captured_image_paths) > 0, "No season image paths were used"
                                            video_image_path = captured_image_paths[0]
                                            
                                            assert video_image_path == expected_image_path, \
                                                f"Season video looks for {video_image_path}, but image saved to {actual_path}"
                                        
                                        print("    ✅ Season-level paths are consistent between image generation and video creation")
                                        success_count += 1
                            
    except Exception as e:
        print(f"    ❌ Season-level path consistency test failed: {e}")
    
    # Test 3: Path parameter order consistency
    print("\n3️⃣ Testing Path Parameter Order Consistency")
    total_tests += 1
    
    try:
        # Test that create_images function calls create_image with correct parameter order
        with mock.patch('media.media_utils.create_image') as mock_create_image:
            from media.media_utils import create_images
            
            # Test parameters
            sentences = ["sentence 1", "sentence 2"]
            episode = "1"
            season = "1" 
            show = "Test Show"
            
            # Call create_images
            create_images(sentences, episode, season, show)
            
            # Verify create_image was called with correct parameter order
            assert mock_create_image.call_count == 2, "Should call create_image for each sentence"
            
            # Check first call
            first_call = mock_create_image.call_args_list[0]
            expected_args = ("sentence 1", episode, season, show, 0)
            actual_args = first_call[0]
            
            assert actual_args == expected_args, \
                f"First call args: {actual_args}, expected: {expected_args}"
            
            # Check second call  
            second_call = mock_create_image.call_args_list[1]
            expected_args = ("sentence 2", episode, season, show, 1)
            actual_args = second_call[0]
            
            assert actual_args == expected_args, \
                f"Second call args: {actual_args}, expected: {expected_args}"
            
            print("    ✅ Parameter order is consistent in create_images function")
            success_count += 1
            
    except Exception as e:
        print(f"    ❌ Parameter order consistency test failed: {e}")
    
    # Test 4: Directory structure consistency  
    print("\n4️⃣ Testing Directory Structure Consistency")
    total_tests += 1
    
    try:
        # Test that both image and audio functions create the same directory structure
        with mock.patch('media.media_utils.genai'):
            with mock.patch('media.media_utils.types'):
                with mock.patch('media.media_utils.Image'):
                    with mock.patch('media.media_utils.wave'):
                        
                        created_dirs = []
                        
                        def mock_makedirs(path, exist_ok=False):
                            created_dirs.append(path)
                        
                        with mock.patch('media.media_utils.os.makedirs', side_effect=mock_makedirs):
                            from media.media_utils import create_image, wave_file
                            
                            show = "Test Show"
                            season = "1"
                            episode = "1"
                            
                            # Create image - should create directory
                            create_image("test", episode, season, show, 0)
                            
                            # Create audio - should create same directory
                            wave_file(show, season, episode, "test content")
                            
                            # Both should create the same directory structure
                            expected_dir = f"{show}/Season{season}/Episode{episode}"
                            
                            assert len(created_dirs) >= 2, "Should create directories for both image and audio"
                            
                            # All created directories should be the same
                            unique_dirs = set(created_dirs)
                            assert len(unique_dirs) == 1, \
                                f"Multiple different directories created: {unique_dirs}"
                            
                            assert expected_dir in created_dirs, \
                                f"Expected directory {expected_dir} not created. Created: {created_dirs}"
                            
                            print("    ✅ Directory structure is consistent between media functions")
                            success_count += 1
                            
    except Exception as e:
        print(f"    ❌ Directory structure consistency test failed: {e}")
    
    # Test 5: File naming pattern consistency
    print("\n5️⃣ Testing File Naming Pattern Consistency")
    total_tests += 1
    
    try:
        # Test that file naming follows expected patterns
        saved_files = []
        
        def capture_save(path):
            saved_files.append(path)
        
        with mock.patch('media.media_utils.genai'):
            with mock.patch('media.media_utils.types'):
                with mock.patch('media.media_utils.os.makedirs'):
                    with mock.patch('media.media_utils.wave'):
                        
                        # Mock image saving
                        mock_image = mock.Mock()
                        mock_image.save = capture_save
                        with mock.patch('media.media_utils.Image.new', return_value=mock_image):
                            
                            # Mock wave file operations for audio
                            def mock_wave_open(path, mode):
                                saved_files.append(path)
                                return mock.Mock()
                            
                            with mock.patch('media.media_utils.wave.open', side_effect=mock_wave_open):
                                from media.media_utils import create_image, wave_file
                                
                                show = "Test Show"
                                season = "1" 
                                episode = "1"
                                
                                # Create image
                                create_image("test", episode, season, show, 5)
                                
                                # Create audio
                                wave_file(show, season, episode, "test content")
                                
                                # Verify file naming patterns
                                image_files = [f for f in saved_files if f.endswith('.png')]
                                audio_files = [f for f in saved_files if f.endswith('.wav')]
                                
                                assert len(image_files) > 0, "No image files were saved"
                                assert len(audio_files) > 0, "No audio files were saved"
                                
                                # Check image naming pattern
                                expected_image = f"{show}/Season{season}/Episode{episode}/{show}_{episode}_5.png"
                                assert expected_image in image_files, \
                                    f"Expected image {expected_image} not found. Found: {image_files}"
                                
                                # Check audio naming pattern
                                expected_audio = f"{show}/Season{season}/Episode{episode}/{show}_{episode}.wav"
                                assert expected_audio in audio_files, \
                                    f"Expected audio {expected_audio} not found. Found: {audio_files}"
                                
                                print("    ✅ File naming patterns are consistent and predictable")
                                success_count += 1
                                
    except Exception as e:
        print(f"    ❌ File naming pattern test failed: {e}")
    
    # Summary
    print(f"\n{'=' * 60}")
    print("FILE PATH CONSISTENCY TEST SUMMARY")
    print(f"{'=' * 60}")
    
    success_rate = success_count / total_tests if total_tests > 0 else 0
    print(f"Passed: {success_count}/{total_tests}")
    print(f"Success rate: {success_rate:.1%}")
    
    if success_rate >= 0.8:
        print("✅ File path consistency is maintained across media functions!")
        return True
    else:
        print("❌ File path consistency issues detected!")
        return False

def main():
    """Run all file path consistency tests."""
    if test_file_path_consistency():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
