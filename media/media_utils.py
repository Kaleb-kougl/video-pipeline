"""
Media processing utilities for video, audio, and image generation.
"""

import json
import logging
import os
import wave
from pathlib import Path
from pprint import pprint

from google import genai
from google.genai import types
from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips
from PIL import Image

logger = logging.getLogger(__name__)


def create_images(sentences: list[str], episode: str, season: str, show: str) -> None:
    """
    Creates AI-generated images for each plot point in the episode.
    This function coordinates the generation of multiple images that will
    be used as visual slides in the final video compilation.

    Args:
        sentences (list): List of plot point descriptions or enhanced prompts for image generation
        episode (str): Episode identifier for file naming and organization
        season (str): Season identifier for file naming and organization
        show (str): Show name for file naming and organization
    """
    logger.info(f"Creating {len(sentences)} images for {show} S{season}E{episode}")
    # Generate an image for each plot point/sentence
    for index, sentence in enumerate(sentences):
        create_image(sentence, episode, season, show, index)


def create_image(image_sentence: str, episode: str, season: str, show: str, index: int) -> None:
    """
    Generate a single image using AI based on plot point description.
    This function uses Google's Gemini model to create anime-style images
    that visually represent specific scenes from the episode.

    Args:
        image_sentence (str): Description of the scene to generate (enhanced prompt with style)
        episode (str): Episode identifier for file naming
        season (str): Season identifier for file naming
        show (str): Show name for file naming
        index (int): Image index for unique filename generation
    """
    logger.debug(f"Creating image {index} for episode {episode}")

    # Ensure the directory structure exists
    os.makedirs(f"{show}/Season{season}/Episode{episode}", exist_ok=True)
    image_path = f"{show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png"

    try:
        # Try AI image generation if API key is available
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise Exception("No Google API key found")

        client = genai.Client(api_key=api_key)

        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=image_sentence,
            config=types.GenerateImagesConfig(number_of_images=1, output_mime_type="image/png"),
        )

        # Process successful response
        if response.generated_images and len(response.generated_images) > 0:
            image = response.generated_images[0].image
            image.save(image_path)
            logger.info(f"Generated AI image: {image_path}")
            return

    except Exception as e:
        error_msg = str(e)
        if "billed users" in error_msg or "INVALID_ARGUMENT" in error_msg:
            print(
                f"🖼️  Using FREE PLACEHOLDER IMAGE ({index + 1}) - Upgrade to Google Cloud billing for AI-generated anime artwork"
            )
            logger.info(
                f"AI image generation requires billing - creating placeholder for: {image_sentence[:50]}..."
            )
        elif "No Google API key found" in error_msg:
            print(
                f"🖼️  Using FREE PLACEHOLDER IMAGE ({index + 1}) - Add GOOGLE_API_KEY to .env for AI generation"
            )
            logger.warning("No Google API key found - creating placeholder")
        else:
            print(
                f"🖼️  Using FREE PLACEHOLDER IMAGE ({index + 1}) - AI generation failed, using fallback"
            )
            logger.warning(f"AI image generation failed ({error_msg[:100]}) - creating placeholder")

    # Create enhanced placeholder image
    create_placeholder_image(image_sentence, image_path, index)
    logger.info(f"Created placeholder image: {image_path}")


def create_placeholder_image(prompt: str, image_path: str, index: int):
    """Create a visually appealing placeholder image with prompt text."""
    from PIL import ImageDraw, ImageFont

    # Create image with gradient background
    width, height = 1024, 768
    image = Image.new("RGB", (width, height), color="#1a1a2e")
    draw = ImageDraw.Draw(image)

    # Add gradient effect
    for y in range(height):
        color_value = int(26 + (y / height) * 40)  # Gradient from dark blue to lighter
        color = (color_value, color_value, min(color_value + 20, 255))
        draw.line([(0, y), (width, y)], fill=color)

    # Add title
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 60)
        text_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
    except Exception:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # Main title
    title = f"Scene {index + 1}"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_width) // 2, 100), title, fill="white", font=title_font)

    # Wrap and display prompt text
    words = prompt.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        test_text = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_text, font=text_font)
        if bbox[2] - bbox[0] > width - 100:  # Leave 50px margin on each side
            if len(current_line) > 1:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))

    # Draw wrapped text
    y_offset = 250
    for line in lines[:8]:  # Limit to 8 lines
        bbox = draw.textbbox((0, 0), line, font=text_font)
        line_width = bbox[2] - bbox[0]
        draw.text(((width - line_width) // 2, y_offset), line, fill="#cccccc", font=text_font)
        y_offset += 35

    # Add decorative elements
    draw.rectangle([100, height - 120, width - 100, height - 80], outline="white", width=2)
    draw.text((120, height - 110), "Anime Video Generator", fill="white", font=text_font)

    image.save(image_path)


def wave_file(
    show: str,
    season: str,
    episode: str,
    contents: str,
    channels: int = 1,
    rate: int = 24000,
    sample_width: int = 2,
) -> float:
    """
    Generate audio file from text using AI text-to-speech.
    This function converts the YouTube transcript text into spoken narration
    using Google's Gemini TTS model with a specific voice configuration.

    Args:
        show (str): Show name for file organization
        season (str): Season identifier for file organization
        episode (str): Episode identifier for file organization
        contents (str): Text content to convert to speech (YouTube transcript)
        channels (int): Audio channels (default: 1 for mono audio)
        rate (int): Sample rate in Hz (default: 24000 for good quality)
        sample_width (int): Sample width in bytes (default: 2 for 16-bit audio)

    Returns:
        float: Duration of generated audio file in seconds for video timing
    """
    logger.info(f"Creating audio file for {show} S{season}E{episode}")

    # Ensure the directory structure exists for audio file storage
    os.makedirs(f"{show}/Season{season}/Episode{episode}", exist_ok=True)
    file_name = f"{show}/Season{season}/Episode{episode}/{show}_{episode}.wav"

    try:
        # Try AI text-to-speech
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise Exception("No Google API key found")

        client = genai.Client(api_key=api_key)

        # Generate speech audio using Gemini TTS model
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],  # Request audio output only
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Kore",  # Use specific voice for consistency
                        )
                    )
                ),
            ),
        )

        # Extract audio data from the response
        data = response.candidates[0].content.parts[0].inline_data.data

    except Exception as e:
        error_msg = str(e)
        if "billed users" in error_msg or "INVALID_ARGUMENT" in error_msg:
            print(
                "🎤 Using FREE SILENT AUDIO - Upgrade to Google Cloud billing for AI-generated professional narration"
            )
            logger.info("AI audio generation requires billing - creating silent audio")
        elif "No Google API key found" in error_msg:
            print("🎤 Using FREE SILENT AUDIO - Add GOOGLE_API_KEY to .env for AI narration")
            logger.warning("No Google API key found - creating silent audio")
        else:
            print("🎤 Using FREE SILENT AUDIO - AI narration failed, using fallback")
            logger.warning(
                f"AI audio generation failed ({error_msg[:100]}) - creating silent audio"
            )

        # Create silent audio file as fallback, at the rate the caller asked for
        return create_silent_audio_fallback(file_name, contents, sample_rate=rate)

    # Write the audio data to a WAV file with specified parameters
    with wave.open(file_name, "wb") as wf:
        wf.setnchannels(channels)  # Set audio channels
        wf.setsampwidth(sample_width)  # Set bit depth
        wf.setframerate(rate)  # Set sample rate
        wf.writeframes(data)  # Write audio data

    # Return the duration for video timing calculations
    return get_wav_duration(file_name)


def create_silent_audio_fallback(filename: str, contents: str, sample_rate: int = 24000) -> float:
    """Create a silent audio file as fallback when TTS fails."""
    # Estimate duration based on text length (rough approximation: 150 words per minute)
    word_count = len(contents.split())
    estimated_duration = max(60.0, word_count / 2.5)  # Minimum 1 minute, ~150 WPM reading speed

    # Calculate number of frames
    num_frames = int(estimated_duration * sample_rate)

    # Make sure the destination directory exists: this runs on the TTS-failure
    # path, which callers may reach before creating any output directory.
    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # Write WAV file. A full-length transcript can run to hours of narration, so
    # the silence is written a second at a time rather than materialising the
    # whole buffer (2 bytes * rate * duration) in memory first.
    frames_per_write = sample_rate
    with wave.open(filename, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        remaining = num_frames
        while remaining > 0:
            block = min(frames_per_write, remaining)
            wav_file.writeframes(b"\x00\x00" * block)
            remaining -= block

    print(
        f"🔇 Created {estimated_duration:.1f}s silent audio track - Perfect for adding your own voice-over!"
    )
    logger.info(f"Created silent audio fallback: {filename} ({estimated_duration:.1f}s)")
    return estimated_duration


def get_wav_duration(wav_file_path: str) -> float:
    """
    Determine the duration of a WAV audio file.
    This function calculates the exact duration needed for video timing
    by analyzing the audio file's frame count and sample rate.

    Args:
        wav_file_path (str): Path to WAV file to analyze

    Returns:
        float: Duration in seconds for video synchronization
    """
    logger.debug(f"Calculating duration for {wav_file_path}")
    # Open WAV file in read mode and extract timing information
    with wave.open(wav_file_path, "r") as wf:
        num_frames = wf.getnframes()  # Total number of audio frames
        frame_rate = wf.getframerate()  # Frames per second (sample rate)
        # Calculate duration: total frames divided by frames per second
        duration = num_frames / frame_rate
        return duration


def mp4_file_enhanced(
    show: str, season: str, episode: str, sentences: list[str], durations: list[float]
) -> None:
    """
    Creates an MP4 video file from images and an audio file with adaptive slide durations.
    This function is the final assembly step that combines all generated assets
    (images, audio, intro video) into a complete YouTube-ready video.

    Args:
        show (str): The name of the show for file path construction
        season (str): The season number for file path construction
        episode (str): The episode number for file path construction
        sentences (list): A list of plot points (used to find corresponding images)
        durations (list): A list of durations for each image in seconds
    """
    logger.info(f"Creating enhanced MP4 for {show} S{season}E{episode}")
    array_ic = []

    # Create an ImageClip for each sentence/image with its calculated duration
    # This step builds the visual timeline with proportional timing
    for index, (_sentence, duration) in enumerate(zip(sentences, durations, strict=False)):
        # Construct path to the generated image file
        image_path = f"{show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png"
        # Create MoviePy ImageClip with specific duration
        ic = ImageClip(image_path).with_duration(duration)
        array_ic.append(ic)

    # Load the intro video and the generated audio file
    intro_video = VideoFileClip(f"{show}/tldr_mha_intro.mp4")  # Channel branding intro
    ac_1 = AudioFileClip(
        f"{show}/Season{season}/Episode{episode}/{show}_{episode}.wav"
    )  # Narration audio

    # Concatenate the image clips to create the main content video
    video = concatenate_videoclips(clips=array_ic, method="compose")
    # Attach the audio narration to the visual content
    video_with_audio = video.with_audio(ac_1)

    # Add the intro video to the beginning for channel branding
    video_with_intro = concatenate_videoclips(
        clips=[intro_video, video_with_audio], method="compose"
    )

    # Write the final video file with optimized settings for YouTube
    # Use 24fps for smooth playback and AAC audio codec for compatibility
    video_with_intro.write_videofile(
        f"{show}/Season{season}/Episode{episode}/{show}_{season}_{episode}.mp4",
        fps=24,
        audio_codec="aac",
    )

    # Clean up audio resources to prevent memory leaks
    ac_1.close()


def read_json(file_path: str) -> dict:
    """
    Read and parse JSON data from file.
    This utility function loads and displays JSON configuration data
    for debugging and data inspection purposes.

    Args:
        file_path (str): Path to JSON file to read

    Returns:
        dict: Parsed JSON data structure
    """
    # Load JSON file and parse the content
    data = json.loads(Path(file_path).read_text())
    logger.debug("JSON file loaded successfully")
    # Pretty print the data for debugging/inspection
    pprint(data)
    return data
