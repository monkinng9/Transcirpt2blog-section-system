import cv2
import asyncio
from datetime import timedelta
from cap_from_youtube import cap_from_youtube

def parse_timestamp(timestamp_str):
    """Convert timestamp string (HH:MM:SS) to seconds"""
    time_parts = [int(x) for x in timestamp_str.split(':')]
    td = timedelta(hours=time_parts[0], minutes=time_parts[1], seconds=time_parts[2])
    return td.total_seconds()

async def capture_youtube_screenshot(youtube_url, timestamp_str, output_filename):
    """
    Capture a screenshot from a YouTube video at a specific timestamp
    
    Args:
        youtube_url (str): YouTube video URL
        timestamp_str (str): Timestamp in format "HH:MM:SS"
        output_filename (str): Output image filename
    
    Returns:
        bool: True if successful, False otherwise
    """
    target_time = parse_timestamp(timestamp_str)
    
    try:
        # Create a video capture object targeting 720p
        cap = cap_from_youtube(youtube_url, 'bestvideo[height=720][ext=mp4]', start=target_time)
        
        if cap is None:
            print(f"Error capturing screenshot at {timestamp_str}: Failed to create video capture")
            return False
            
        # Read the frame
        ret, frame = cap.read()
        if not ret:
            print(f"Error capturing screenshot at {timestamp_str}: Failed to read frame")
            return False
            
        # Save the frame as an image
        cv2.imwrite(output_filename, frame)
        print(f"Successfully captured screenshot at {timestamp_str}")
        
        # Release the capture object
        cap.release()
        return True
        
    except Exception as e:
        print(f"Error capturing screenshot at {timestamp_str}: {str(e)}")
        return False
