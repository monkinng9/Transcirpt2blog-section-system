import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import webvtt

# Prepare Transcript
## Read and parse the VTT file
captions = []
for caption in webvtt.read('transcript.vtt'):
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
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
import json

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

# Prompt to generate the blog outline
planning_prompt = PromptTemplate(
    template="""
    Analyze the following transcript and provide a detailed outline for a blog post. 
    Identify key themes, create section titles, and summarize each section. Include start and end times
    for each section to retain context.

    Transcript: {transcript}

    {format_instructions}

    Return a valid JSON object that matches this exact format:
    {{
        "outline": [
            {{
                "title": "Section Title",
                "summary": "Section summary text",
                "start_time": "00:00:00",
                "end_time": "00:30:33"
            }}
        ]
    }}
    """,
    input_variables=["transcript"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# Create the chain
chain = planning_prompt | pro_llm | parser

# Invoke the chain
planning_result = chain.invoke(
    {
        "transcript": formatted_text_and_ts  # Replace with your transcript input
    }
)

# Print the generated blog outline plan
print("==== Generated Blog Outline ====")
print(planning_result)

# Save the planning result to a JSON file
with open('blog_outline.json', 'w') as f:
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


