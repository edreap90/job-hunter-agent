import os
import requests
import openai
import json
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager
import time

# --- CONFIG ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZAPIER_HOOK_URL = os.getenv("ZAPIER_HOOK_URL")
ASSISTANT_ID = "asst_U32xY6OxubvMQjsWi5WWWnZx"
openai.api_key = OPENAI_API_KEY

# --- SCRAPE JOBS FROM INDEED (Stealth + BeautifulSoup) ---
def fetch_indeed_jobs(keywords=["analytics", "data", "insights"], locations=["new york", "remote"]):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)

    jobs = []

    for keyword in keywords:
        for location in locations:
            query = keyword.replace(" ", "+")
            loc = location.replace(" ", "+")
            url = f"https://www.indeed.com/jobs?q={query}&l={loc}&radius=25"
            print(f"🌐 Visiting: {url}")

            try:
                driver.get(url)
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'lxml')
                job_cards = soup.find_all('div', class_='job_seen_beacon')
                print(f"🔍 Found {len(job_cards)} jobs for '{keyword}' in '{location}'")

                for i in job_cards[:10]:
                    try:
                        link = i.find('a', {'data-jk': True})
                        job_url = f"https://www.indeed.com{link.get('href')}" if link else None

                        title_tag = i.find('h2') or i.find('a', class_=lambda x: x and 'jobTitle' in x)
                        title = title_tag.text.strip() if title_tag else None

                        company_tag = i.find('span', {'data-testid': 'company-name'})
                        company = company_tag.text.strip() if company_tag else None

                        location_tag = i.find('div', {'data-testid': 'text-location'})
                        location_text = location_tag.text.strip() if location_tag else ''

                        desc_tag = i.find('div', class_='job-snippet')
                        summary = desc_tag.text.strip() if desc_tag else ''

                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location_text,
                            "description": summary,
                            "link": job_url,
                            "source": "Indeed"
                        })
                    except Exception as inner_e:
                        print(f"⚠️ Error parsing job card: {inner_e}")
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
