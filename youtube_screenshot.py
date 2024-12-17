import cv2
import asyncio
from datetime import timedelta
from cap_from_youtube import cap_from_youtube

async def capture_youtube_screenshot(youtube_url, timestamp_str, output_filename):
    """
    Capture a screenshot from a YouTube video at a specific timestamp
    
    Args:
        youtube_url (str): YouTube video URL
        timestamp_str (str): Timestamp in format "HH:MM:SS"
        output_filename (str): Output image filename
    """
    # Convert timestamp string to timedelta
    time_parts = [int(x) for x in timestamp_str.split(':')]
    target_time = timedelta(hours=time_parts[0], 
                          minutes=time_parts[1], 
                          seconds=time_parts[2])
    
    try:
        # Create a video capture object
        cap = cap_from_youtube(youtube_url, 'best', start=target_time)
        
        
        # Read the frame
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(output_filename, frame)
            success = True
        else:
            success = False
        
        # Release the video capture object
        cap.release()
        
        return success
    except Exception as e:
        print(f"Error capturing screenshot at {timestamp_str}: {str(e)}")
        return False
