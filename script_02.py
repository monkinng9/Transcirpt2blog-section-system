import re
import os
import cv2
import tempfile
from urllib.parse import urlparse, parse_qs
import yt_dlp
from config import YOUTUBE_URL, SCREENSHOTS_DIR, INPUT_MARKDOWN, OUTPUT_MARKDOWN

def get_video_id(youtube_url):
    """Extract video ID from YouTube URL"""
    parsed_url = urlparse(youtube_url)
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    raise ValueError(f"Could not extract video ID from URL: {youtube_url}")

def download_youtube_video(youtube_url):
    """Download YouTube video in 720p quality"""
    video_id = get_video_id(youtube_url)
    output_path = os.path.join(tempfile.gettempdir(), f"{video_id}.mp4")
    
    if os.path.exists(output_path):
        print(f"Video already downloaded: {output_path}")
        return output_path
    
    ydl_opts = {
        'format': 'best[height<=720]',
        'outtmpl': output_path,
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        print(f"Video downloaded: {output_path}")
        return output_path
    except Exception as e:
        raise Exception(f"Error downloading video: {str(e)}")

def extract_timestamps(markdown_file):
    """Extract timestamps from markdown headings"""
    with open(markdown_file, 'r') as f:
        content = f.read()
    
    # Find all section headings with timestamps
    pattern = r'## \[(\d{2}:\d{2}:\d{2}) - \d{2}:\d{2}:\d{2}\]'
    matches = re.finditer(pattern, content)
    return [match.group(1) for match in matches]

def capture_screenshot(video_path, timestamp, output_path):
    """Capture screenshot from video at specific timestamp"""
    try:
        # Convert timestamp to seconds
        h, m, s = map(int, timestamp.split(':'))
        seconds = h * 3600 + m * 60 + s
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file {video_path}")
            return False
        
        # Set position and capture frame
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ret, frame = cap.read()
        
        if not ret:
            print(f"Error: Could not read frame at {timestamp}")
            cap.release()
            return False
        
        # Save frame
        cv2.imwrite(output_path, frame)
        print(f"Screenshot saved: {output_path}")
        cap.release()
        return True
        
    except Exception as e:
        print(f"Error capturing screenshot at {timestamp}: {str(e)}")
        return False

def process_screenshots(video_path, timestamps, screenshots_dir):
    """Process screenshots for all timestamps"""
    results = {}
    for timestamp in timestamps:
        screenshot_name = f"screenshot_{timestamp.replace(':', '_')}.png"
        screenshot_path = os.path.join(screenshots_dir, screenshot_name)
        success = capture_screenshot(video_path, timestamp, screenshot_path)
        results[timestamp] = screenshot_path if success else None
    return results

def inject_screenshots_to_markdown(input_file, output_file, screenshot_paths):
    """Inject screenshots into markdown file"""
    with open(input_file, 'r') as f:
        content = f.readlines()
    
    new_content = []
    pattern = r'## \[(\d{2}:\d{2}:\d{2}) - \d{2}:\d{2}:\d{2}\]'
    
    # Add thumbnail at the start
    if '00:00:00' in screenshot_paths:
        new_content.append(f"![Video Thumbnail]({screenshot_paths['00:00:00']})\n\n")
    
    # Process content and inject screenshots
    for line in content:
        new_content.append(line)
        match = re.search(pattern, line)
        if match:
            timestamp = match.group(1)
            if timestamp in screenshot_paths and screenshot_paths[timestamp]:
                new_content.append(f"\n![Screenshot at {timestamp}]({screenshot_paths[timestamp]})\n\n")
    
    # Write new content
    with open(output_file, 'w') as f:
        f.writelines(new_content)

def cleanup_video(video_path):
    """Remove the downloaded video file"""
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            print(f"Removed video file: {video_path}")
    except Exception as e:
        print(f"Error removing video file: {e}")

def main():
    """Main function to process markdown and inject screenshots"""
    # Ensure screenshots directory exists
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    
    # Download video
    video_path = download_youtube_video(YOUTUBE_URL)
    
    try:
        # Extract timestamps from markdown
        timestamps = extract_timestamps(INPUT_MARKDOWN)
        
        # Add timestamp for thumbnail
        if '00:00:00' not in timestamps:
            timestamps.insert(0, '00:00:00')
        
        # Process screenshots
        screenshot_paths = process_screenshots(video_path, timestamps, SCREENSHOTS_DIR)
        
        # Inject screenshots into markdown
        inject_screenshots_to_markdown(INPUT_MARKDOWN, OUTPUT_MARKDOWN, screenshot_paths)
        print("Processing complete! Check", OUTPUT_MARKDOWN)
    
    finally:
        # Always cleanup the video, even if an error occurs
        cleanup_video(video_path)

if __name__ == "__main__":
    main()