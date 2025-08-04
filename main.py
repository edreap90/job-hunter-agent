# main.py

import os
import requests
import openai
import json
from bs4 import BeautifulSoup

# --- CONFIG ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZAPIER_HOOK_URL = os.getenv("ZAPIER_HOOK_URL")
ASSISTANT_ID = "asst_U32xY6OxubvMQjsWi5WWWnZx" 
openai.api_key = OPENAI_API_KEY

# --- SCRAPE JOBS FROM Rem oteOK ---
def scrape_remoteok():
    url = "https://remoteok.com/remote-analytics-jobs"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    for tr in soup.find_all("tr", class_="job"):
        try:
            title = tr.find("h2").get_text(strip=True)
            company = tr.find("h3").get_text(strip=True)
            location = tr.find("div", class_="location").get_text(strip=True)
            link = "https://remoteok.com" + tr["data-href"]
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": "N/A",
                "link": link
            })
        except Exception as e:
            print(f"❌ Error parsing job row: {e}")
    return jobs

# --- SCRAPE JOBS FROM TechJobsForGood ---
def scrape_techjobsforgood():
    url = "https://www.techjobsforgood.com/jobs/?search=analytics"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    for job_card in soup.select(".job-card"):
        try:
            title = job_card.select_one(".job-title").text.strip()
            company = job_card.select_one(".organization-name").text.strip()
            location = job_card.select_one(".job-location").text.strip()
            link = "https://www.techjobsforgood.com" + job_card.find("a")["href"]
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": "N/A",
                "link": link
            })
        except Exception as e:
            print(f"❌ Error parsing TechJobs job: {e}")
    return jobs

# --- SCRAPE JOBS FROM Idealist ---
def scrape_idealist():
    url = "https://www.idealist.org/en/jobs?search_mode=true&q=analytics"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    for job_card in soup.select(".styles_component__JobCardWrapper-sc-1lf4q2o-0"):
        try:
            title = job_card.select_one("h2").text.strip()
            company = job_card.select_one("a[data-testid='job-company-name']").text.strip()
            location = job_card.select_one("span[data-testid='job-location']").text.strip()
            link = "https://www.idealist.org" + job_card.find("a")["href"]
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": "N/A",
                "link": link
            })
        except Exception as e:
            print(f"❌ Error parsing Idealist job: {e}")
    return jobs

# --- FORMAT FOR GPT ---
def format_jobs_for_gpt(jobs):
    return "\n\n".join([
        f"{i+1}. Title: {j['title']}\nCompany: {j['company']}\nLocation: {j['location']}\nDescription: {j['description']}\nLink: {j['link']}"
        for i, j in enumerate(jobs)
    ])

# --- MAIN LOGIC ---
def main():
    jobs = scrape_remoteok() + scrape_techjobsforgood() + scrape_idealist()
    print(f"🔍 Fetched {len(jobs)} jobs")

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

    # --- Filter output based on score ---
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
