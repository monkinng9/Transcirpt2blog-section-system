import re
import os
import asyncio
from youtube_screenshot import capture_youtube_screenshot

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
    tasks = []
    for timestamp in timestamps:
        screenshot_name = f"screenshot_{timestamp.replace(':', '_')}.png"
        screenshot_path = os.path.join(screenshots_dir, screenshot_name)
        task = capture_youtube_screenshot(youtube_url, timestamp, screenshot_path)
        tasks.append(task)
    return await asyncio.gather(*tasks)

async def inject_screenshots_to_markdown(input_file, output_file, youtube_url):
    """Process markdown file and inject screenshots above each timestamped section"""
    screenshots_dir = SCREENSHOTS_DIR
    os.makedirs(screenshots_dir, exist_ok=True)
    
    with open(input_file, 'r') as file:
        content = file.readlines()
    
    new_content = []
    pattern = r"## \[(\d{2}:\d{2}:\d{2})"
    
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
            screenshot_results[timestamp] = success

    # Then process the content line by line
    for line in content:
        match = re.search(pattern, line)
        if match and match.group(1) in screenshot_results:
            timestamp = match.group(1)
            if screenshot_results[timestamp]:
                screenshot_name = f"screenshot_{timestamp.replace(':', '_')}.png"
                screenshot_path = os.path.join(screenshots_dir, screenshot_name)
                new_content.append(f"![Screenshot at {timestamp}]({screenshot_path})\n\n")
        new_content.append(line)
    
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
