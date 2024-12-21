import cv2
import asyncio
from datetime import timedelta
from cap_from_youtube import cap_from_youtube
from typing import List, Tuple
import aiohttp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_CONCURRENT_CAPTURES = 3
MAX_RETRIES = 3
RETRY_DELAY = 1

def parse_timestamp(timestamp_str):
    """Convert timestamp string (HH:MM:SS) to seconds"""
    time_parts = [int(x) for x in timestamp_str.split(':')]
    return time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2]

async def capture_youtube_screenshot(youtube_url: str, timestamp_str: str, output_filename: str, semaphore: asyncio.Semaphore) -> bool:
    """
    Capture a screenshot from a YouTube video at a specific timestamp with retry logic
    
    Args:
        youtube_url (str): YouTube video URL
        timestamp_str (str): Timestamp in format "HH:MM:SS"
        output_filename (str): Output image filename
        semaphore (asyncio.Semaphore): Semaphore for controlling concurrent captures
    
    Returns:
        bool: True if successful, False otherwise
    """
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                time_parts = [int(x) for x in timestamp_str.split(':')]
                start_time = timedelta(hours=time_parts[0], minutes=time_parts[1], seconds=time_parts[2])
                
                logger.info(f"Attempt {attempt + 1}: Capturing screenshot at {timestamp_str}")
                cap = cap_from_youtube(youtube_url, resolution='720p', start=start_time)
                
                if cap is None:
                    logger.error(f"Failed to create capture object for {timestamp_str}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    return False
                
                ret, frame = cap.read()
                if not ret:
                    logger.error(f"Failed to read frame at {timestamp_str}")
                    cap.release()
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    return False
                
                cv2.imwrite(output_filename, frame)
                logger.info(f"Successfully captured screenshot at {timestamp_str}")
                cap.release()
                return True
                
            except Exception as e:
                logger.error(f"Error during capture at {timestamp_str}: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return False
            
        return False

async def process_screenshots_batch(youtube_url: str, timestamps: List[Tuple[str, str]]) -> List[bool]:
    """
    Process multiple screenshots concurrently with controlled concurrency
    
    Args:
        youtube_url (str): YouTube video URL
        timestamps (List[Tuple[str, str]]): List of (timestamp, output_filename) tuples
    
    Returns:
        List[bool]: List of success/failure results
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CAPTURES)
    tasks = []
    
    for timestamp_str, output_filename in timestamps:
        task = asyncio.create_task(
            capture_youtube_screenshot(youtube_url, timestamp_str, output_filename, semaphore)
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return results

# Example usage:
# timestamps = [("00:00:10", "screenshot1.jpg"), ("00:00:20", "screenshot2.jpg")]
# results = await process_screenshots_batch("https://youtube.com/watch?v=xxx", timestamps)
