#!/usr/bin/env python3
"""
Helper script to run the main application with environment variables loaded from .env file.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Verify API key is loaded
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("❌ GOOGLE_API_KEY not found in .env file")
    sys.exit(1)

print(f"✅ Loaded API key: {api_key[:20]}...")

# Import and run the main application
if __name__ == "__main__":
    # Add the arguments and run main
    sys.argv = [
        'main.py',
        'create-season-summary',
        'My Hero Academia',
        '1',
        '--duration', '10',
        '--format', 'standard',
        '--force'
    ]
    
    # Import and run main
    import main
    main.main()
