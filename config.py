# File paths
INPUT_VTT = "transcript.vtt"  # Path to the VTT subtitle file
INPUT_SRT = "transcript.srt"  # Path to the SRT subtitle file
INPUT_MARKDOWN = "generated_blog.md"  # Output file for the generated markdown blog
OUTPUT_MARKDOWN = "blog_with_screenshots.md"  # Final markdown file with added screenshots
OUTPUT_JSON = "blog_outline.json"  # JSON file storing the blog section outline
SCREENSHOTS_DIR = "screenshots"  # Directory to store generated screenshots

# Default input can be changed as needed
INPUT = INPUT_SRT  # Choose which input subtitle file to use (INPUT_SRT or INPUT_VTT)

# Processing settings
TRANSCRIPT_BATCH_SIZE = 3  # Number of batches to split transcript into for processing
SCREENSHOT_BATCH_SIZE = 5  # Number of screenshots to process concurrently

# YouTube settings
YOUTUBE_URL = 'https://youtu.be/worpx0LOeII?si=OJLXo3kwq3qkkg1I'  # Source video URL

# Section settings
MAX_SECTIONS = 10  # Maximum number of sections allowed
MIN_SECTION_DURATION = 120  # Minimum duration of each section in seconds
TARGET_SECTION_DURATION = 300  # Target duration for each section in seconds
SECTION_OVERLAP_THRESHOLD = 30  # Allowed overlap between sections in seconds
