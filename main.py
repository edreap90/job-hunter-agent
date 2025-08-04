# main.py

import os
import requests
import openai
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# --- CONFIG ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZAPIER_HOOK_URL = os.getenv("ZAPIER_HOOK_URL")
ASSISTANT_ID = "asst_U32xY6OxubvMQjsWi5WWWnZx" 
openai.api_key = OPENAI_API_KEY

# --- SCRAPE JOBS FROM Indeed using Selenium ---
def scrape_indeed_selenium():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    jobs = []
    url = "https://www.indeed.com/jobs?q=data+analyst+nonprofit+remote"
    driver.get(url)
    time.sleep(3)

    job_cards = driver.find_elements(By.CLASS_NAME, "job_seen_beacon")
    for card in job_cards[:10]:  # limit for speed
        try:
            title = card.find_element(By.CLASS_NAME, "jobTitle").text
            company = card.find_element(By.CLASS_NAME, "companyName").text
            location = card.find_element(By.CLASS_NAME, "companyLocation").text
            job_link = card.find_element(By.TAG_NAME, "a").get_attribute("href")

            driver.execute_script("window.open(arguments[0]);", job_link)
            driver.switch_to.window(driver.window_handles[1])
            time.sleep(2)
            try:
                desc = driver.find_element(By.ID, "jobDescriptionText").text
            except:
                desc = "N/A"
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": desc,
                "link": job_link
            })
        except Exception as e:
            print(f"❌ Error scraping Indeed job: {e}")

    driver.quit()
    return jobs

# --- FORMAT FOR GPT ---
def format_jobs_for_gpt(jobs):
    return "\n\n".join([
        f"{i+1}. Title: {j['title']}\nCompany: {j['company']}\nLocation: {j['location']}\nDescription: {j['description']}\nLink: {j['link']}"
        for i, j in enumerate(jobs)
    ])

# --- MAIN LOGIC ---
def main():
    jobs = scrape_indeed_selenium()
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
