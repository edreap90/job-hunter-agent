import os
import requests
import openai
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

# --- CONFIG ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZAPIER_HOOK_URL = os.getenv("ZAPIER_HOOK_URL")
ASSISTANT_ID = "asst_U32xY6OxubvMQjsWi5WWWnZx"
openai.api_key = OPENAI_API_KEY

# --- SCRAPE JOBS FROM INDEED (Multi-keyword/location, bot-resistant) ---
def fetch_indeed_jobs(keywords=["analytics", "data", "insights"], locations=["new york", "remote"]):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    jobs = []

    for keyword in keywords:
        for location in locations:
            query = keyword.replace(" ", "+")
            loc = location.replace(" ", "+")
            url = f"https://www.indeed.com/jobs?q={query}&l={loc}&radius=25"

            try:
                driver.get(url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "result"))
                )
                time.sleep(2)
                job_cards = driver.find_elements(By.CLASS_NAME, "result")
                print(f"🔍 Found {len(job_cards)} jobs for '{keyword}' in '{location}'")

                for card in job_cards[:10]:  # limit for speed
                    try:
                        title = card.find_element(By.CLASS_NAME, "jobTitle").text
                        link = card.find_element(By.CLASS_NAME, "jcs-JobTitle").get_attribute("href")
                        company = card.find_element(By.CLASS_NAME, "companyName").text
                        loc_text = card.find_element(By.CLASS_NAME, "companyLocation").text
                        summary = card.find_element(By.CLASS_NAME, "job-snippet").text

                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": loc_text,
                            "description": summary,
                            "link": link,
                            "source": "Indeed"
                        })
                    except Exception:
                        continue

            except Exception as e:
                print(f"❌ Error fetching jobs for '{keyword}' in '{location}': {e}")
                continue

    driver.quit()
    print(f"✅ Collected {len(jobs)} total jobs from Indeed")
    return jobs

# --- FORMAT FOR GPT ---
def format_jobs_for_gpt(jobs):
    return "\n\n".join([
        f"{i+1}. Title: {j['title']}\nCompany: {j['company']}\nLocation: {j['location']}\nDescription: {j['description']}\nLink: {j['link']}"
        for i, j in enumerate(jobs)
    ])

# --- MAIN LOGIC ---
def main():
    jobs = fetch_indeed_jobs()
    print(f"🔍 Fetched {len(jobs)} jobs from Indeed")

    if not jobs:
        print("❌ No jobs found.")
        return

    thread = openai.beta.threads.create()
    user_input = f"""Evaluate the following jobs for fit with Evan Reap's interests:
- Analytics/Data roles
- Nonprofit, public interest, or mission-driven orgs
- Remote or NYC-based
- Skills in SQL, Tableau, data storytelling

Return a summary for each job with a score from 0–100 and a recommendation.\n\n{format_jobs_for_gpt(jobs)}"""

    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_input
    )

    run = openai.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID
    )

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    response_text = messages.data[0].content[0].text.value
    print("✅ GPT Response:\n", response_text)

    high_fit_lines = []
    for line in response_text.split("\n\n"):
        if "Score:" in line:
            try:
                score_line = next(l for l in line.split("\n") if "Score:" in l)
                score = int(score_line.split("Score:")[-1].strip().split("/")[0])
                if score >= 80:
                    high_fit_lines.append(line)
            except Exception:
                continue

    if not high_fit_lines:
        print("📭 No high-fit jobs to send.")
        return

    filtered_summary = "\n\n".join(high_fit_lines)

    payload = {
        "summary": filtered_summary,
        "job_count": len(high_fit_lines)
    }
    zap = requests.post(ZAPIER_HOOK_URL, json=payload)
    if zap.status_code == 200:
        print("✅ Sent to Zapier successfully")
    else:
        print(f"❌ Zapier failed: {zap.status_code} — {zap.text}")

if __name__ == "__main__":
    main()
