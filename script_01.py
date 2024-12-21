import os
import subprocess
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
import webvtt
import pysrt  # Add this import for SRT support
import concurrent.futures
from typing import List, Dict
import math

from config import *

# Setup Config
config = {
    "input": INPUT
}

# Prepare Transcript
## Read and parse the VTT or SRT file
captions = []
file_extension = os.path.splitext(config['input'])[1].lower()

if file_extension == '.vtt':
    for caption in webvtt.read(config['input']):
        captions.append({
            "start": caption.start,
            "end": caption.end,
            "text": caption.text
        })
elif file_extension == '.srt':
    subs = pysrt.open(config['input'])
    for sub in subs:
        captions.append({
            "start": str(sub.start),
            "end": str(sub.end),
            "text": sub.text.replace('\n', ' ')
        })
else:
    raise ValueError(f"Unsupported file type: {file_extension}. Only .vtt and .srt files are supported.")

def captions_to_long_text(captions):
    # Join all the text parts from the captions
    return " ".join(caption["text"].strip() for caption in captions)

def captions_to_long_text_with_ts(captions):
    """
    Convert a list of captions to a long text with timestamps.
    Each caption will have its timestamp and text concatenated.
    
    Args:
        captions (list of dict): List of captions with "start", "end", and "text".
        
    Returns:
        str: Concatenated text with timestamps.
    """
    long_text = ""
    for caption in captions:
        start = caption["start"]
        end = caption["end"]
        text = caption["text"].strip()
        long_text += f"[{start} - {end}] {text}\n"
    return long_text

## Convert captions to long text
formatted_text = captions_to_long_text(captions)
formatted_text_and_ts = captions_to_long_text_with_ts(captions)


# Setup LLM
# Load Gemini API key from environment variable
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
flash_llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.7,
    max_tokens=None,
    timeout=60,
    max_retries=2,
)

# Generate Summarise Overview
overview_sum_prompt = ChatPromptTemplate.from_messages(
    [
        ("human", """
        <transcript>
        {transcript}
        </transcript>
        Summarize the following text in more than 200 words but less than 500 words. 
        Focus on capturing the main ideas, key arguments, and significant details. 
        Maintain clarity and coherence while preserving the original meaning and tone. 
        Include essential facts, insights, and conclusions, but avoid unnecessary repetition or minor details."""),
    ]
)

chain = overview_sum_prompt | flash_llm
overview_sum = chain.invoke(
    {
        "transcript": formatted_text[:10000]
    }
)
overview_sum_content = overview_sum.content
print(overview_sum_content)


# Planning Section
from pydantic import BaseModel, Field

# Define the schema for the output using Pydantic's BaseModel
class Section(BaseModel):
    title: str = Field(description="Title of the blog section")
    summary: str = Field(description="Summary of the blog section")
    start_time: str = Field(description="Start time of the section")
    end_time: str = Field(description="End time of the section")

class BlogOutline(BaseModel):
    outline: list[Section] = Field(description="List of sections for the blog post")

# Initialize the JSON parser with the defined schema
parser = JsonOutputParser(pydantic_object=BlogOutline)

# Initialize the model
pro_llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    temperature=0.7,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

def calculate_optimal_batch_size(captions: List[Dict], min_batch_size: int = 50) -> int:
    """
    Calculate optimal batch size based on caption length and minimum batch size.
    
    Args:
        captions: List of caption dictionaries
        min_batch_size: Minimum number of captions per batch
        
    Returns:
        Optimal batch size
    """
    total_length = sum(len(caption["text"]) for caption in captions)
    avg_caption_length = total_length / len(captions)
    
    # Target ~10000 characters per batch (adjustable based on model context window)
    target_chars_per_batch = 10000
    optimal_size = max(
        min_batch_size,
        math.ceil(target_chars_per_batch / avg_caption_length)
    )
    return min(optimal_size, len(captions))

def process_batch_with_context(batch_info):
    """
    Process a single batch with its context information.
    
    Args:
        batch_info: Tuple containing (batch, previous_context, batch_number)
        
    Returns:
        Processed batch results
    """
    batch, previous_context, batch_number = batch_info
    batch_text = captions_to_long_text_with_ts(batch)
    return process_transcript_batch(batch_text, previous_context, batch_number)

def process_transcript_batch(transcript_text, previous_context="", batch_number=1):
    planning_prompt = PromptTemplate(
        template="""
        Analyze the following transcript segment and provide an outline for blog sections. Aim for a comprehensive summary of at least 200 words across all sections. You may create more than 4 sections if the content warrants it for better organization and coverage.

        Consider the previous context if provided.

        Previous Context: {previous_context}
        Current Transcript: {transcript}

        Return a valid JSON object with sections that matches this format:
        {{
            "outline": [
                {{
                    "title": "Section Title",
                    "summary": "Section summary text (aim for substantial summaries contributing to the 200+ word total)",
                    "start_time": "00:00:00",
                    "end_time": "00:30:33"
                }},
                        {{
                    "title": "Another Section Title",
                    "summary": "More summary text to reach the 200+ word goal.",
                    "start_time": "00:30:34",
                    "end_time": "01:00:00"
                }},
                // ... more sections as needed
            ]
        }}

        Ensure the combined summaries of all sections are at least 200 words long, providing a detailed overview of the transcript segment. Prioritize clarity, accuracy, and comprehensive coverage of the key topics discussed.  If the transcript is short, still aim for detailed summaries within each section to meet the word count, by elaborating on the key points.
        """,
        input_variables=["transcript", "previous_context"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = planning_prompt | pro_llm | parser
    return chain.invoke({
        "transcript": transcript_text,
        "previous_context": previous_context
    })

def optimize_sections(sections):
    """
    Optimize sections based on configuration parameters.
    
    Args:
        sections: List of section dictionaries
    
    Returns:
        List of optimized sections
    """
    print("\n==== Starting Section Optimization ====")
    print(f"Total sections before optimization: {len(sections)}")
    print(f"Maximum sections allowed: {MAX_SECTIONS}")
    
    if len(sections) <= MAX_SECTIONS:
        print("No optimization needed. Sections are within the limit.")
        return sections
        
    # Convert time strings to seconds for easier calculation
    def time_to_seconds(time_str):
        try:
            # Handle comma-separated milliseconds format
            time_str = time_str.replace(',', '.')
            
            # Split into components
            if '.' in time_str:
                main_time, ms = time_str.split('.')
            else:
                main_time = time_str
                ms = '0'
            
            # Convert HH:MM:SS to seconds
            h, m, s = map(float, main_time.split(':'))
            total_seconds = h * 3600 + m * 60 + s + float('0.' + ms)
            return total_seconds
        except Exception as e:
            print(f"Error parsing time {time_str}: {str(e)}")
            return 0
        
    def seconds_to_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    # Calculate duration and importance for each section
    sections_with_metrics = []
    print("\nCalculating section metrics:")
    for i, section in enumerate(sections, 1):
        start_seconds = time_to_seconds(section['start_time'])
        end_seconds = time_to_seconds(section['end_time'])
        duration = end_seconds - start_seconds
        
        # Calculate importance based on summary length and duration
        importance = len(section['summary']) * (duration / TARGET_SECTION_DURATION) if duration > 0 else 0
        
        sections_with_metrics.append({
            **section,
            'duration': duration,
            'importance': importance
        })
        
        print(f"Section {i}: Start={section['start_time']}, End={section['end_time']}, "
              f"Duration={duration:.2f}s, Importance={importance:.2f}")
    
    # Sort sections by importance
    print("\nSorting sections by importance...")
    sorted_sections = sorted(sections_with_metrics, key=lambda x: x['importance'], reverse=True)
    
    # Take top MAX_SECTIONS sections and sort them by start time
    print(f"\nSelecting top {MAX_SECTIONS} most important sections:")
    optimized_sections = sorted(sorted_sections[:MAX_SECTIONS], 
                              key=lambda x: time_to_seconds(x['start_time']))
    
    # Log the selected sections
    print("\nSelected Optimized Sections:")
    for i, section in enumerate(optimized_sections, 1):
        print(f"Section {i}: Start={section['start_time']}, End={section['end_time']}, "
              f"Title='{section['title']}'")
    
    # Clean up the sections before returning
    for section in optimized_sections:
        del section['duration']
        del section['importance']
    
    print(f"\n==== Optimization Complete ====")
    print(f"Total sections after optimization: {len(optimized_sections)}")
    return optimized_sections

# Process transcript in batches
batch_size = calculate_optimal_batch_size(captions)
print(f"\n==== Batch Processing Configuration ====")
print(f"Total captions: {len(captions)}")
print(f"Optimal batch size: {batch_size}")

caption_batches = [captions[i:i + batch_size] for i in range(0, len(captions), batch_size)]
print(f"Number of batches: {len(caption_batches)}")

previous_context = ""

# Process each batch and collect all sections
all_sections = []
print("\n==== Starting Batch Processing ====")
for i, batch in enumerate(caption_batches, 1):
    print(f"\nProcessing Batch {i}/{len(caption_batches)}")
    print(f"Batch size: {len(batch)} captions")
    
    batch_info = (batch, previous_context, i)
    result = process_batch_with_context(batch_info)
    
    print(f"Sections generated in batch {i}: {len(result['outline'])}")
    all_sections.extend(result['outline'])
    
    # Update context with summaries from this batch
    previous_context = captions_to_long_text(batch)

print("\n==== Batch Processing Complete ====")
print(f"Total sections generated: {len(all_sections)}")

# Optimize sections based on configuration
print("\n==== Preparing for Section Optimization ====")
optimized_sections = optimize_sections(all_sections)

# Generate Each Section
section_prompt = PromptTemplate(
    input_variables=["overall_summ", "section_plan", "previous_summary", "current_transcript"],
    template="""
    Overall summary: {overall_summ}
    Write a detailed blog section based on the plan: {section_plan}.
    Previous sections summary: {previous_summary}
    Current transcript excerpt: {current_transcript}

    Generate an engaging, coherent blog section. 
    Example Title: ## [{{start_time}} - {{end_time}}] [Title]
    at the beginning of the section to help readers follow along with the original content.
    """
)

sections = optimized_sections
overall_summary = overview_sum_content # Example overall summary. Replace with a dynamic one if needed.
previous_summary = ""
blog_sections = []

def log_progress(current, total):
    """Log the progress of section generation"""
    percent = (current + 1) * 100 // total
    print(f"Generating section {current + 1}/{total} ({percent}% complete)")

for i, section_plan in enumerate(sections):
    log_progress(i, len(sections))
    start_time = section_plan['start_time']
    end_time = section_plan['end_time']

    current_transcript = " ".join(
        caption["text"].strip()
        for caption in captions
        if start_time <= caption["start"] <= end_time
    )

    chain = section_prompt | flash_llm | StrOutputParser()
    
    section_result = chain.invoke({
        "overall_summ": overall_summary,
        "section_plan": json.dumps(section_plan),
        "previous_summary": " ".join(blog_section["content"] for blog_section in blog_sections[-2:]),
        "current_transcript": current_transcript
    })

    blog_sections.append({
        "title": section_plan['title'],
        "content": section_result,
        "start_time": start_time,
        "end_time": end_time
    })

# Generate final summary
final_summary_prompt = ChatPromptTemplate.from_messages([
    ("human", """
    Based on all the sections covered:
    {previous_summary}
    
    Write a concluding paragraph that:
    1. Summarizes the key points discussed
    2. Provides final thoughts or takeaways
    3. Closes the blog post naturally
    Keep it concise (150-200 words).
    """)
])

chain = final_summary_prompt | flash_llm | StrOutputParser()
final_summary = chain.invoke({"previous_summary": previous_summary})

# Write the blog content
with open('generated_blog.md', 'w', encoding='utf-8') as f:
    f.write("# Blog Post\n\n")
    f.write("## Overview\n")
    f.write(overview_sum_content)
    f.write("\n\n")
    
    # Write each section with timestamps
    for section_data in blog_sections:
        f.write(section_data['content'])
        f.write("\n\n")
    
    # Add the final summary section
    f.write("## Final Thoughts\n")
    f.write(final_summary)
    f.write("\n")

print("Blog post has been written to generated_blog.md")
