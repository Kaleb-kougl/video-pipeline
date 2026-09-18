#!/usr/bin/env python3
"""
Create a silent audio file as placeholder for TTS generation.
"""

import wave
import os
import struct

def create_silent_audio(filename: str, duration_seconds: float = 300.0, sample_rate: int = 24000):
    """Create a silent WAV file of specified duration."""
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Calculate number of frames
    num_frames = int(duration_seconds * sample_rate)
    
    # Create silent audio data (16-bit mono)
    silence = b'\x00\x00' * num_frames
    
    # Write WAV file
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)
    
    print(f"Created silent audio: {filename} ({duration_seconds}s)")
    return duration_seconds

if __name__ == "__main__":
    # Create placeholder for My Hero Academia Season 1
    audio_path = "My Hero Academia/Season1/EpisodeSeason_1/My Hero Academia_Season_1.wav"
    create_silent_audio(audio_path, 600.0)  # 10 minutes
