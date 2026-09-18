#!/usr/bin/env python3
"""
Legacy HTML parser and anime video generator.

This is a copy of the original monolithic main.py file, preserved for reference
during the migration to the new modular architecture. Contains functions for
HTML parsing, image generation, audio synthesis, and video composition.

Note: This file is deprecated in favor of the new modular architecture.
"""

import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from io import BytesIO
from PIL import Image
import re
import getpass
import os
import json
import wave
from moviepy import VideoFileClip, ImageClip, concatenate_videoclips, AudioFileClip




def get_html_content(url):
    print("retrieve html")
    """
    Fetches the HTML content from a given URL.

    Args:
        url (str): The URL of the webpage to fetch.

    Returns:
        str: The HTML content of the page, or None if an error occurs.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None

def parse_html_with_beautifulsoup(html_content):
    """
    Parses HTML content using BeautifulSoup and extracts various information.

    Args:
        html_content (str): The HTML content as a string.

    Returns:
       transcript, title
    """
    print("parse html")
    if not html_content:
        print("No HTML content to parse.")
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    # print("\n--- HTML Parsing Results ---")

    # 1. Get the page title
    title = soup.find('h1')
    if title:
        # print(f"Page Title: {title.get_text()}")
        title = title.get_text()
        # print(title)
    
    match = re.search(r'Season \d+, Episode \d+', title)
    episode = match.group(0)
    # else:
    #     print("Page Title: Not found")


    # 5. Find elements by class name (example: assuming elements with class="item")
    items = soup.find(class_="full-script")
    if items:
        # print(f"  full-script: {items.get_text()}")
        return items.get_text(), title, episode
    else:
        print("  No elements with class 'full-script' found.")      

def create_images(sentences, episode, season, show):
    """Generate images for each sentence using AI image generation.
    
    Args:
        sentences (list): List of sentences to create images for
        episode (str): Episode number
        season (str): Season number  
        show (str): Show name
        
    Returns:
        None
    """
    print(f"iterate through and create {len(sentences)} images")
    for index, sentence in enumerate(sentences):
        create_image(sentence, episode, season, show, index)

def create_image(image_sentence, episode, season, show, index): 
    """Create a single image using Gemini's image generation model.
    
    Args:
        image_sentence (str): Text description for image generation
        episode (str): Episode number for file naming
        season (str): Season number for file naming
        show (str): Show name for file naming and directory structure
        index (int): Image index for unique file naming
        
    Returns:
        None
    """
    print(f"create image:{index}")
    client = genai.Client()
    response =  client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=image_sentence,
        config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE']
        )
    )
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(part.text)
        elif part.inline_data is not None:
            image = Image.open(BytesIO((part.inline_data.data)))
            image.save(f"{show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png")

def save_json(dict, season, episode, show, type):
    """Save data as JSON file in organized directory structure.
    
    Args:
        dict (dict): Data to save as JSON
        season (str): Season number for directory structure
        episode (str): Episode number for directory structure
        show (str): Show name for directory structure
        type (str): File type identifier for naming
        
    Returns:
        None
    """
    print("Save youtube_transcript")
    write_json(f"{show}/Season{season}/Episode{episode}", 
               f"{show}_{season}_{episode}_{type}.json", 
               dict)

def write_json(target_path, target_file, data):
    """Write data to JSON file, creating directories if needed.
    
    Args:
        target_path (str): Directory path where file will be saved
        target_file (str): Filename for the JSON file
        data (dict): Data to serialize and save
        
    Returns:
        None
        
    Raises:
        Exception: If directory creation or file writing fails
    """
    print("Save youtube_transcript")
    if not os.path.exists(target_path):
        try:
            os.makedirs(target_path)
        except Exception as e:
            print(e)
            raise
    with open(os.path.join(target_path, target_file), 'w') as f:
        json.dump(data, f)

def read_json(file_path):
    from pathlib import Path
    from pprint import pprint

    data = json.loads(Path(file_path).read_text())
    print('loaded json')
    pprint(data)
    return data

def wave_file(show, season, episode, contents, channels=1, rate=24000, sample_width=2):
    print("create wave file")
    client = genai.Client()
    file_name=f"{show}/Season{season}/Episode{episode}/{show}_{episode}.wav"
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name='Kore',
                    )
                )
            ),
        )
    )
    data = response.candidates[0].content.parts[0].inline_data.data

    with wave.open(file_name, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(data)

    return get_wav_duration(file_name)

def get_wav_duration(wav_file_path):
    print("determine wave duration")
    with wave.open(wav_file_path, 'r') as wf:
        num_frames = wf.getnframes()
        frame_rate = wf.getframerate()
        duration = num_frames / frame_rate
        return duration
    
def image_clips_array(show, season, episode, sentences, wave_length):
    # Determine how long to show each image
    print("Determine how long to show each image")
    sentence_count = len(sentences)
    duration = wave_length / sentence_count
    array_image_clips = []
    for index, sentence in enumerate(sentences):
        ic = ImageClip(f"{show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png").with_duration(duration)
        array_image_clips.append(ic)
    return array_image_clips

def mp4_file(show, season, episode, sentences, wave_length):
    print("create mp4")
    array_ic = image_clips_array(show, season, episode, sentences, wave_length)
    intro_video = VideoFileClip(f"{show}/tldr_mha_intro.mp4")     
    
    ac_1 = AudioFileClip(f"{show}/Season{season}/Episode{episode}/{show}_{episode}.wav")
    video = concatenate_videoclips(clips=array_ic, method="compose")
    
    video_with_audio = video.with_audio(ac_1)
    video_with_intro = concatenate_videoclips(clips=[intro_video, video_with_audio], method="compose")
    video_with_intro.write_videofile(f"{show}/Season{season}/Episode{episode}/{show}_{season}_{episode}.mp4", fps=24, audio_codec="aac")

    # close audio file
    ac_1.close()

from typing import Optional
from pydantic import BaseModel, Field
# Pydantic
class Episode_Summary_Schema(BaseModel):
    """Summary of a given show episode."""

    show: str = Field(description="The title of the show")
    season: str = Field(description="The numerical season of the show")
    episode: str = Field(description="The numerical episode of the show")
    youtube_transcript: str = Field(description="Summary of the entire episode.")
    plot_points: list[str] = Field(description="Single sentence summaries of major plot points in this episode of the show")

if __name__ == "__main__":
    # # CONSTANTS
    # SHOW = "My Hero Academia"
    # TRANSCRIPT_URL = "https://subslikescript.com/series/My_Hero_Academia-5626028/season-1/episode-4-Start_Line"
    # # load environment variables from .env file (requires `python-dotenv`)
    # try:
    #     from dotenv import load_dotenv
    #     load_dotenv()
    # except ImportError:
    #     pass
        
    # os.environ["LANGSMITH_TRACING"] = "true"
    # if not os.environ.get("GOOGLE_API_KEY"):
    #     os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")
    
    # # INFORM MODEL OF THEIR ROLE
    # from langchain_core.prompts import ChatPromptTemplate
    # system_template = "You are a famous YouTuber who makes videos about popular anime shows and your channel is called TLDR Media. Can you summarize this episode of {Show} based on the following transcription? Make sure to ask watchers to Like, Comment, and subscribe somewhere in the video."
    # # NO INTRO
    # system_template = system_template + "Do not do an introduction."    
    # prompt_template = ChatPromptTemplate.from_messages(
    #     [("system", system_template), ("user", "{text}")]
    # )


    from langchain.chat_models import init_chat_model
    # set up model
    model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
    # set up structured response
    model_with_structure = model.with_structured_output(Episode_Summary_Schema)
    

    # # GET RAW TRANSCRIPT
    # html_to_parse = get_html_content(TRANSCRIPT_URL)
    # # PARSE RAW TRANSCRIPT
    # target_script, title, episode = parse_html_with_beautifulsoup(html_to_parse)
    # # BUILD PROMPT WITH SHOW TRANSCRIPT
    # prompt = prompt_template.invoke({"Show": SHOW, "text": html_to_parse})
    # # RUN PROMPT USING MODEL
    # response_youtube_transcript = model_with_structure.invoke(prompt)
    # dict_response_youtube_transcript = response_youtube_transcript.model_dump()
    # # Save response
    # save_json(dict=dict_response_youtube_transcript, show=dict_response_youtube_transcript["show"], type="model", season=dict_response_youtube_transcript["season"], episode=dict_response_youtube_transcript["episode"])
    
    # # Create images for youtube video
    # create_images(sentences=dict_response_youtube_transcript["plot_points"], episode=dict_response_youtube_transcript["episode"], season=dict_response_youtube_transcript["season"], show=dict_response_youtube_transcript["show"])


    dict_response_youtube_transcript = read_json('My Hero Academia/Season1/Episode4/My Hero Academia_1_4_model.json')


    # Create audio for youtube video
    wave_length = wave_file(show=dict_response_youtube_transcript["show"], season=dict_response_youtube_transcript["season"], episode=dict_response_youtube_transcript["episode"], contents=dict_response_youtube_transcript["youtube_transcript"])

    # Create youtuve video
    mp4_file(show=dict_response_youtube_transcript["show"], season=dict_response_youtube_transcript["season"], episode=dict_response_youtube_transcript["episode"], sentences=dict_response_youtube_transcript["plot_points"], wave_length=wave_length)


    print("Done!")

