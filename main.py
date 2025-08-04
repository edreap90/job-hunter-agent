import os
import requests
import openai
import json

# ENV variables from GitHub Secrets
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZAPIER_HOOK_URL = os.getenv("ZAPIER_HOOK_URL")
ASSISTANT_ID = "asst_U32xY6OxubvMQjsWi5WWWnZx"  # Replace with your actual Assistant ID

openai.api_key = OPENAI_API_KEY

# Step 1: Load job data (placeholder example — replace with scraped data)
job_postings = [
    {
        "title": "Data Analyst – Clean Transportation",
        "company": "RMI",
        "location": "Remote",
        "description": "Use SQL and Tableau to uncover insights in the transportation decarbonization space.",
        "link": "https://jobs.rmi.org/example"
    },
    {
        "title": "Senior Data Scientist – City Planning",
        "company": "NYC Department of City Planning",
        "location": "New York, NY",
        "description": "Use analytics to help drive smarter infrastructure and transportation decisions. Experience in geospatial data required.",
        "link": "https://cityjobs.nyc.gov/example"
    }
]

# Step 2: Create a new assistant thread
thread = openai.beta.threads.create()

# Step 3: Format input message to the assistant
job_descriptions = "\n\n".join([
    f"{i+1}. Title: {job['title']}\nCompany: {job['company']}\nLocation: {job['location']}\nDescription: {job['description']}\nLink: {job['link']}"
    for i, job in enumerate(job_postings)
])

user_message = f"""Here are some job postings. For each one, please provide:
- A short summary
- A fit score from 0–100 based on Evan Reap's skills and mission interests
- Whether you'd recommend applying

{job_descriptions}
"""

openai.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content=user_message
)

# Step 4: Run assistant
run = openai.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=ASSISTANT_ID
)

# Step 5: Get the response
messages = openai.beta.threads.messages.list(thread_id=thread.id)
response_text = messages.data[0].content[0].text.value

print("✅ Assistant Response:\n")
print(response_text)

# Step 6: Parse output (very basic version — refine later)
# We'll just forward the full GPT response to Zapier for now

payload = {
    "summary": response_text,
    "job_count": len(job_postings)
}

zapier_response = requests.post(ZAPIER_HOOK_URL, json=payload)
if zapier_response.status_code == 200:
    print("✅ High-fit jobs sent to Zapier successfully.")
else:
    print(f"❌ Failed to send to Zapier: {zapier_response.status_code}")
