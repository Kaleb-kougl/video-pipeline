#!/usr/bin/env python3
"""
Test the new free tier messaging system.
"""

import sys
import os
sys.path.append('.')

# Remove API key to force fallbacks
if 'GOOGLE_API_KEY' in os.environ:
    del os.environ['GOOGLE_API_KEY']

print("Testing Free Tier Messaging System...")
print("=" * 50)

from media.media_utils import create_image, wave_file

# Test image generation fallback
print("\n1. Testing Image Generation Fallback:")
create_image('A beautiful anime scene with mountains', 'TestEp', '1', 'Message Test Show', 0)

# Test audio generation fallback
print("\n2. Testing Audio Generation Fallback:")
duration = wave_file('Message Test Show', '1', 'TestEp', 'This is a test of the audio generation fallback messaging system.')

print(f"\nTest completed! Duration: {duration}s")
