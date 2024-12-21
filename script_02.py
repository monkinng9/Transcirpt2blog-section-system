import re
import os
import asyncio
from youtube_screenshot import capture_youtube_screenshot, process_screenshots_batch

def extract_start_times(file_path):
    """Extract timestamps from markdown headings"""
    start_times = []
    pattern = r"## \[(\d{2}:\d{2}:\d{2})"

    with open(file_path, 'r') as file:
        for line in file:
            match = re.search(pattern, line)
            if match:
                start_times.append(match.group(1))
    
    return start_times

async def process_screenshot_batch(youtube_url, timestamps, screenshots_dir):
    """Process a batch of screenshots concurrently"""
    timestamp_pairs = []
    for timestamp in timestamps:
        screenshot_name = f"screenshot_{timestamp.replace(':', '_')}.png"
        screenshot_path = os.path.join(screenshots_dir, screenshot_name)
        timestamp_pairs.append((timestamp, screenshot_path))
    
    return await process_screenshots_batch(youtube_url, timestamp_pairs)

async def capture_thumbnail(youtube_url, screenshots_dir):
    """Capture the thumbnail/first frame of the video"""
    thumbnail_path = os.path.join(screenshots_dir, "thumbnail.png")
    timestamp = "00:00:00"
    
    # Use existing capture function with timestamp 0
    success = await process_screenshots_batch(youtube_url, [(timestamp, thumbnail_path)])
    return thumbnail_path if success[0] else None

async def inject_screenshots_to_markdown(input_file, output_file, youtube_url):
    """Process markdown file and inject screenshots above each timestamped section"""
    screenshots_dir = SCREENSHOTS_DIR
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # First capture the thumbnail
    thumbnail_path = await capture_thumbnail(youtube_url, screenshots_dir)
    
    with open(input_file, 'r') as file:
        content = file.readlines()
    
    new_content = []
    pattern = r"## \[(\d{2}:\d{2}:\d{2})"
    first_section = True
    
    # Collect all timestamps first
    timestamps = []
    for line in content:
        match = re.search(pattern, line)
        if match:
            timestamps.append(match.group(1))
    
    # First process all screenshots in batches
    screenshot_results = {}
    batch_size = SCREENSHOT_BATCH_SIZE
    for i in range(0, len(timestamps), batch_size):
        batch = timestamps[i:i + batch_size]
        results = await process_screenshot_batch(youtube_url, batch, screenshots_dir)
        for timestamp, success in zip(batch, results):
            screenshot_name = f"screenshot_{timestamp.replace(':', '_')}.png"
            screenshot_path = os.path.join(screenshots_dir, screenshot_name)
            screenshot_results[timestamp] = screenshot_path if success else None
    
    # Now process the content and inject screenshots
    for line in content:
        new_content.append(line)
        
        # Add thumbnail after the Overview heading
        if "## Overview" in line and thumbnail_path:
            new_content.append(f"\n![Video Thumbnail]({thumbnail_path})\n\n")
            continue
            
        match = re.search(pattern, line)
        if match:
            timestamp = match.group(1)
            screenshot_path = screenshot_results.get(timestamp)
            if screenshot_path:
                new_content.append(f"\n![Screenshot at {timestamp}]({screenshot_path})\n\n")
    
    with open(output_file, 'w') as file:
        file.writelines(new_content)

from config import *

async def main():
    # Get configuration from config.py
    youtube_url = YOUTUBE_URL
    input_markdown = INPUT_MARKDOWN
    output_markdown = OUTPUT_MARKDOWN
    
    # Process the markdown and inject screenshots
    await inject_screenshots_to_markdown(input_markdown, output_markdown, youtube_url)
    print("Processing complete! Check", output_markdown)

if __name__ == "__main__":
    asyncio.run(main())
