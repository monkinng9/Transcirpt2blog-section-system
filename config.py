# File paths
INPUT_VTT = "transcript.vtt"  # Path to the VTT subtitle file
INPUT_SRT = "transcript.srt"  # Path to the SRT subtitle file
INPUT_MARKDOWN = "generated_blog.md"  # Output file for the generated markdown blog
OUTPUT_MARKDOWN = "blog_output.md"  # Final markdown file with added screenshots
OUTPUT_JSON = "blog_outline.json"  # JSON file storing the blog section outline
SCREENSHOTS_DIR = "screenshots"  # Directory to store generated screenshots

# Default input can be changed as needed
INPUT = INPUT_SRT  # Choose which input subtitle file to use (INPUT_SRT or INPUT_VTT)

# YouTube settings
YOUTUBE_URL = 'https://youtu.be/6Yd6NdJrn4s?si=gljMMfWhvjaxMVmw'  # Source video URL

# Section settings
MAX_SECTIONS = 10  # Maximum number of sections allowed
TARGET_SECTION_DURATION = 300  # Target duration for each section in seconds
