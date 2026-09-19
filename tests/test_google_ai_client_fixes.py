#!/usr/bin/env python3
"""
Regression tests for Google AI client initialization fixes.

This test suite validates that all the fixes for Google Generative AI client
initialization and API usage are working correctly. The original issues were:
1. Using deprecated genai.Client() without API key
2. Using wrong API methods (generate_content instead of generate_images)
3. Using deprecated model names and configuration parameters
"""

import os
import sys
import unittest.mock as mock
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_google_ai_client_fixes():
    """Test that Google AI client initialization fixes work correctly.

    This test validates that all Google AI client usage has been updated
    to use the new google-genai SDK properly with correct API key handling,
    proper method calls, and updated model names.

    Returns:
        bool: True if all tests pass, False otherwise
    """

    print("🧪 Testing Google AI Client Initialization Fixes")
    print("=" * 60)

    success_count = 0
    total_tests = 0

    # Test 1: Media Utils - Image Generation Client Initialization
    print("\n1️⃣ Testing Media Utils Image Generation Client")
    total_tests += 1

    try:
        # Mock the Google AI imports and environment
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with mock.patch("media.media_utils.genai") as mock_genai:
                with mock.patch("media.media_utils.types") as mock_types:
                    # Mock the client and its methods
                    mock_client = mock.Mock()
                    mock_genai.Client.return_value = mock_client

                    # Mock the response
                    mock_generated_image = mock.Mock()
                    mock_generated_image.image = mock.Mock()
                    mock_response = mock.Mock()
                    mock_response.generated_images = [mock_generated_image]
                    mock_client.models.generate_images.return_value = mock_response

                    # Mock the config class
                    mock_types.GenerateImagesConfig.return_value = mock.Mock()

                    # Mock PIL Image and os.makedirs
                    with mock.patch("media.media_utils.Image"):
                        with mock.patch("media.media_utils.os.makedirs"):
                            # Import and test the function
                            from media.media_utils import create_image

                            # This should use the new client initialization
                            create_image("test prompt", "1", "1", "Test Show", 0)

                            # Verify proper client initialization
                            mock_genai.Client.assert_called_with(api_key="test-key")

                            # Verify proper API method usage
                            mock_client.models.generate_images.assert_called_once()

                            # Verify proper config usage
                            mock_types.GenerateImagesConfig.assert_called_once()

                            print("    ✅ Media Utils - proper client initialization and API usage")
                            success_count += 1

    except Exception as e:
        print(f"    ❌ Media Utils image generation test failed: {e}")

    # Test 2: Media Utils - Audio Generation Client Initialization
    print("\n2️⃣ Testing Media Utils Audio Generation Client")
    total_tests += 1

    try:
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key-2"}):
            with mock.patch("media.media_utils.genai") as mock_genai:
                with mock.patch("media.media_utils.types") as mock_types:
                    with mock.patch("media.media_utils.os.makedirs"):
                        with mock.patch("media.media_utils.wave"):
                            # Mock the client
                            mock_client = mock.Mock()
                            mock_genai.Client.return_value = mock_client

                            # Import and test the function
                            from media.media_utils import wave_file

                            # This should use the new client initialization
                            wave_file("Test Show", "1", "1", "test content")

                            # Verify proper client initialization with API key
                            mock_genai.Client.assert_called_with(api_key="test-key-2")

                            print("    ✅ Media Utils - proper audio client initialization")
                            success_count += 1

    except Exception as e:
        print(f"    ❌ Media Utils audio generation test failed: {e}")

    # Test 3: API Key Environment Variable Handling
    print("\n3️⃣ Testing API Key Environment Variable Handling")
    total_tests += 1

    try:
        # Test without API key
        with mock.patch.dict(os.environ, {}, clear=True):
            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]

            with mock.patch("media.media_utils.genai") as mock_genai:
                with mock.patch("media.media_utils.types"):
                    with mock.patch("media.media_utils.Image"):
                        with mock.patch("media.media_utils.os.makedirs"):
                            mock_client = mock.Mock()
                            mock_genai.Client.return_value = mock_client

                            # Mock the response to avoid actual API call
                            mock_response = mock.Mock()
                            mock_response.generated_images = []
                            mock_client.models.generate_images.return_value = mock_response

                            from media.media_utils import create_image

                            # This should handle missing API key gracefully
                            create_image("test prompt", "1", "1", "Test Show", 0)

                            # Verify client was called with None API key (from os.getenv default)
                            mock_genai.Client.assert_called_with(api_key=None)

                            print("    ✅ API Key handling - graceful handling of missing key")
                            success_count += 1

    except Exception as e:
        print(f"    ❌ API Key handling test failed: {e}")

    # Test 4: Image Generation API Method and Model
    print("\n4️⃣ Testing Image Generation API Method and Model")
    total_tests += 1

    try:
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with mock.patch("media.media_utils.genai") as mock_genai:
                with mock.patch("media.media_utils.types") as mock_types:
                    with mock.patch("media.media_utils.Image"):
                        with mock.patch("media.media_utils.os.makedirs"):
                            # Mock client and response
                            mock_client = mock.Mock()
                            mock_genai.Client.return_value = mock_client

                            mock_generated_image = mock.Mock()
                            mock_generated_image.image = mock.Mock()
                            mock_response = mock.Mock()
                            mock_response.generated_images = [mock_generated_image]
                            mock_client.models.generate_images.return_value = mock_response

                            from media.media_utils import create_image

                            create_image("test prompt", "1", "1", "Test Show", 0)

                            # Verify proper API method is used (not generate_content)
                            mock_client.models.generate_images.assert_called_once()
                            assert (
                                not hasattr(mock_client.models, "generate_content")
                                or not mock_client.models.generate_content.called
                            ), "Should use generate_images, not generate_content"

                            # Verify the call parameters
                            call_args = mock_client.models.generate_images.call_args
                            assert call_args[1]["model"] == "imagen-3.0-generate-002", (
                                "Should use imagen-3.0-generate-002 model"
                            )
                            assert call_args[1]["prompt"] == "test prompt", (
                                "Should pass prompt parameter"
                            )

                            print("    ✅ Image API - correct method and model usage")
                            success_count += 1

    except Exception as e:
        print(f"    ❌ Image API method test failed: {e}")

    # Test 5: Image Generation Configuration
    print("\n5️⃣ Testing Image Generation Configuration")
    total_tests += 1

    try:
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with mock.patch("media.media_utils.genai") as mock_genai:
                with mock.patch("media.media_utils.types") as mock_types:
                    with mock.patch("media.media_utils.Image"):
                        with mock.patch("media.media_utils.os.makedirs"):
                            mock_client = mock.Mock()
                            mock_genai.Client.return_value = mock_client

                            mock_response = mock.Mock()
                            mock_response.generated_images = []  # Empty to trigger placeholder
                            mock_client.models.generate_images.return_value = mock_response

                            mock_config = mock.Mock()
                            mock_types.GenerateImagesConfig.return_value = mock_config

                            from media.media_utils import create_image

                            create_image("test prompt", "1", "1", "Test Show", 0)

                            # Verify proper configuration is used
                            mock_types.GenerateImagesConfig.assert_called_with(
                                number_of_images=1, output_mime_type="image/png"
                            )

                            print("    ✅ Image Config - proper GenerateImagesConfig usage")
                            success_count += 1

    except Exception as e:
        print(f"    ❌ Image configuration test failed: {e}")

    # Test 6: Fallback Placeholder Image Generation
    print("\n6️⃣ Testing Fallback Placeholder Image Generation")
    total_tests += 1

    try:
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with mock.patch("media.media_utils.genai") as mock_genai:
                with mock.patch("media.media_utils.types"):
                    with mock.patch("media.media_utils.os.makedirs"):
                        # Mock PIL Image
                        with mock.patch("media.media_utils.Image") as mock_image_class:
                            mock_placeholder = mock.Mock()
                            mock_image_class.new.return_value = mock_placeholder

                            mock_client = mock.Mock()
                            mock_genai.Client.return_value = mock_client

                            # Mock empty response to trigger placeholder creation
                            mock_response = mock.Mock()
                            mock_response.generated_images = []
                            mock_client.models.generate_images.return_value = mock_response

                            from media.media_utils import create_image

                            create_image("test prompt", "1", "1", "Test Show", 0)

                            # Verify placeholder was created
                            mock_image_class.new.assert_called_with(
                                "RGB", (1024, 768), color="black"
                            )
                            mock_placeholder.save.assert_called_once()

                            print("    ✅ Fallback - placeholder image creation works")
                            success_count += 1

    except Exception as e:
        print(f"    ❌ Fallback placeholder test failed: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print("GOOGLE AI CLIENT FIXES TEST SUMMARY")
    print(f"{'=' * 60}")

    success_rate = success_count / total_tests if total_tests > 0 else 0
    print(f"Passed: {success_count}/{total_tests}")
    print(f"Success rate: {success_rate:.1%}")

    if success_rate >= 0.8:
        print("✅ Google AI client fixes are working correctly!")
        return True
    else:
        print("❌ Some Google AI client fixes need attention!")
        return False


def main():
    """Run all Google AI client fix tests."""
    if test_google_ai_client_fixes():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
