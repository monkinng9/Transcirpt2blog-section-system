import os
import subprocess
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
import webvtt
import concurrent.futures
from typing import List, Dict
import math

from config import *

# Setup Config
config = {
    "input": INPUT_VTT
}

# Prepare Transcript
## Read and parse the VTT file
captions = []
for caption in webvtt.read(config['input']):
    captions.append({
        "start": caption.start,
        "end": caption.end,
        "text": caption.text
    })

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
    model="gemini-2.0-flash-exp",
    temperature=0.7,
    max_tokens=None,
    timeout=None,
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

# Process transcript in batches
batch_size = calculate_optimal_batch_size(captions)
caption_batches = [captions[i:i + batch_size] for i in range(0, len(captions), batch_size)]
previous_context = ""
all_sections = []

# Set up parallel processing
max_workers = min(4, len(caption_batches))  # Limit max workers to avoid API rate limits
with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Prepare batch information for parallel processing
    batch_infos = [
        (batch, previous_context, i+1) 
        for i, batch in enumerate(caption_batches)
    ]
    
    # Process batches in parallel
    future_to_batch = {
        executor.submit(process_batch_with_context, batch_info): batch_info[2]
        for batch_info in batch_infos
    }
    
    # Collect results in order
    for future in concurrent.futures.as_completed(future_to_batch):
        batch_num = future_to_batch[future]
        try:
            batch_result = future.result()
            print(f"\nCompleted batch {batch_num}/{len(caption_batches)}")
            all_sections.extend(batch_result["outline"])
            # Update context with summaries from this batch
            previous_context = "\n".join(
                section["summary"] for section in batch_result["outline"]
            )
        except Exception as e:
            print(f"Batch {batch_num} generated an exception: {str(e)}")
            continue

planning_result = {"outline": all_sections}

# Print the generated blog outline plan
print("==== Generated Blog Outline ====")
print(planning_result)

# Save the planning result to a JSON file
with open(OUTPUT_JSON, 'w') as f:
    json.dump(planning_result, f, indent=2)

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

sections = planning_result['outline']
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

    # Extract the relevant transcript excerpt based on start and end times
    current_transcript = ""
    for caption in captions:
        if start_time <= caption["start"] <= end_time:
            current_transcript += caption["text"].strip() + " "

    # Create the chain for section generation
    chain = section_prompt | flash_llm | StrOutputParser()
    
    section_result = chain.invoke({
        "overall_summ": overall_summary,
        "section_plan": json.dumps(section_plan),
        "previous_summary": previous_summary,
        "current_transcript": current_transcript
    })

    # Store title and content in a dictionary
    blog_sections.append({
        "title": section_plan['title'],
        "content": section_result,
        "start_time": start_time,
        "end_time": end_time
    })

    previous_summary += section_result + " \n\n"

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
