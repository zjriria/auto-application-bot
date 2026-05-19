import argparse
import re
import sys
import time
import os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from typing import List

import pandas as pd
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
DISALLOWED = ("noreply", "no-reply", "donotreply", "postmaster", "example", "test@", "wixpress")
HINT_HR = ("bewerbung", "karriere", "personal", "ausbildung", "it", "hr", "recruit", "jobs", "job")
HINT_INFO = ("info", "kontakt")

SEARCH_QUERIES = [
    # LinkedIn
    'site:de.linkedin.com/jobs "Ausbildung Fachinformatiker" "@"',
    'site:de.linkedin.com/jobs "Ausbildung zum Fachinformatiker" "@"',
    # Xing
    'site:xing.com/jobs "Ausbildung Fachinformatiker" "@"',
    'site:xing.com/jobs "Ausbildung zum Fachinformatiker" "@"',
    # StepStone
    'site:stepstone.de "Ausbildung Fachinformatiker" "bewerbung@"',
    'site:stepstone.de "Ausbildung Fachinformatiker" "E-Mail"',
    # General Portals
    'site:azubi.de "Fachinformatiker" "@"',
    'site:ausbildung.de "Fachinformatiker" "@"'
]

def normalize_email(raw: str):
    email = raw.strip().lower().replace("mailto:", "").strip("'\"<>[](){}")
    email = re.sub(r"^[^a-z0-9]+", "", email)
    email = re.sub(r"[^a-z0-9._%+-]+$", "", email)
    if not EMAIL_REGEX.fullmatch(email) or any(token in email for token in DISALLOWED):
        return None
    return email

def mailbox_type(email: str) -> str:
    if any(token in email for token in HINT_HR): return "hr"
    if any(token in email for token in HINT_INFO): return "info"
    return "other"

def score_email(email: str) -> int:
    score = 0
    if any(token in email for token in HINT_HR): score += 5
    if email.startswith("bewerbung@") or email.startswith("jobs@") or email.startswith("karriere@"): score += 3
    if email.startswith("info@") or email.startswith("kontakt@"): score += 1
    if email.endswith(".de"): score += 1
    return score

def extract_company_from_snippet(snippet: str, title: str) -> str:
    if " bei " in title:
        return title.split(" bei ")[-1].split(" |")[0].strip()
    return "Social Platform Lead"

def discover_social_leads(ddgs_results: int = 40) -> List[dict]:
    print(f"🔍 Searching Social Platforms via Search Snippets...")
    leads = []
    seen_emails = set()
    
    with DDGS() as ddgs:
        for query in SEARCH_QUERIES:
            print(f"Executing Query: {query}")
            success = False
            for backend in ["api", "html", "lite"]:
                try:
                    results = list(ddgs.text(query, max_results=ddgs_results, backend=backend))
                    if results:
                        for res in results:
                            snippet = res.get('body', '')
                            title = res.get('title', '')
                            url = res.get('href', '')
                            
                            # Extract emails from the snippet text!
                            raw_emails = EMAIL_REGEX.findall(snippet + " " + title)
                            
                            for raw in raw_emails:
                                email = normalize_email(raw)
                                if email and email not in seen_emails:
                                    seen_emails.add(email)
                                    company = extract_company_from_snippet(snippet, title)
                                    leads.append({
                                        "Company": company,
                                        "Website": url,
                                        "Email": email,
                                        "Type": mailbox_type(email),
                                        "Score": score_email(email),
                                        "Date": datetime.now().strftime("%Y-%m-%d")
                                    })
                        success = True
                        break # Done with this query
                except Exception as e:
                    print(f"⚠️ Search error with backend {backend} for {query}: {e}")
                    time.sleep(2)
            if not success:
                print(f"❌ Failed to get results for {query}.")
            time.sleep(2) # rate limit prevention
            
    return leads

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="informatiker_leads.csv")
    args = parser.parse_args()

    output_path = Path(args.output)
    
    existing_emails = set()
    if output_path.exists():
        try:
            df_old = pd.read_csv(output_path)
            if 'Email' in df_old.columns:
                existing_emails = set(df_old['Email'].astype(str).str.lower())
                print(f"Loaded {len(existing_emails)} existing leads.")
        except Exception as e:
            print(f"Could not load existing CSV: {e}")

    new_leads = discover_social_leads()
    
    added_count = 0
    for lead in new_leads:
        if lead['Email'] not in existing_emails:
            existing_emails.add(lead['Email'])
            # Create a dataframe with just this row
            df_new = pd.DataFrame([lead])
            
            # Make sure it aligns with columns of the current CSV
            # To ensure compatibility, we'll append. 
            df_new.to_csv(output_path, mode='a', index=False, header=not output_path.exists())
            
            print(f"   ✅ Found new social lead: {lead['Email']} ({lead['Company']})")
            added_count += 1

    print(f"\nDone! Scraped {added_count} new leads to {args.output}")

if __name__ == "__main__":
    main()
