#!/usr/bin/env python3
"""
Manual smoke check for the free-tier fallback messaging system.

Not a pytest test: it unsets GOOGLE_API_KEY to force the image/audio
fallback paths and writes real files under "Message Test Show/".
Run directly:  python scripts/check_fallback_messaging.py
"""

import sys
import os

# Allow importing project packages when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
