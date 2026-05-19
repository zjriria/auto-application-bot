import argparse
import re
import time
import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
DISALLOWED = ("noreply", "no-reply", "donotreply", "postmaster", "example", "test@", "wixpress")
HINT_HR = ("bewerbung", "karriere", "personal", "ausbildung", "pflege", "hr", "recruit", "jobs", "job")
HINT_INFO = ("info", "kontakt")
PAGES = ("/impressum",)
LINK_HINTS = ("impressum",)

SEARCH_QUERIES = (
    "Ausbildung Pflegefachkraft {city}",
    "Ausbildung Pflegefachmann {city}",
    "Ausbildung Gesundheitswesen {city} Kontakt",
    "Pflegefachkraft Ausbildung {city} Bewerbung",
    "Ausbildungsplatz Pflege {city}"
)

def normalize_email(raw: str) -> Optional[str]:
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

def collect_emails_from_url(url: str, timeout: int = 15, max_pages: int = 20) -> Set[str]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    found: Set[str] = set()
    queue = [(url.rstrip("/") + suffix, 0) for suffix in PAGES]
    visited: Set[str] = set()
    parsed_base = urlparse(url)

    while queue and len(visited) < max_pages:
        page, depth = queue.pop(0)
        if page in visited: continue
        visited.add(page)
        try:
            resp = requests.get(page, headers=headers, timeout=timeout)
            if resp.status_code != 200: continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for raw in EMAIL_REGEX.findall(soup.get_text(" ", strip=True)):
                email = normalize_email(raw)
                if email: found.add(email)
            for anchor in soup.find_all("a", href=True):
                href = anchor.get("href", "")
                if "mailto:" in href.lower():
                    maybe = href.split(":", 1)[-1].split("?", 1)[0]
                    email = normalize_email(maybe)
                    if email: found.add(email)
                elif depth < 1:
                    linked = urljoin(page, href)
                    parsed_link = urlparse(linked)
                    if parsed_link.netloc == parsed_base.netloc and any(hint in linked.lower() for hint in LINK_HINTS):
                        queue.append((linked, depth + 1))
        except: continue
    return found

def discover_leads(city: str, ddgs_results: int = 15) -> List[dict]:
    print(f"[SEARCH] Searching for Pflege leads in {city}...")
    leads = []
    seen_urls = set()
    backends = ["html", "lite", "api"]
    with DDGS() as ddgs:
        for query_tmpl in SEARCH_QUERIES:
            query = query_tmpl.format(city=city)
            success = False
            for backend in backends:
                try:
                    results = list(ddgs.text(query, max_results=ddgs_results, backend=backend))
                    if results:
                        for res in results:
                            url = res.get('href', '').split('?')[0].rstrip('/')
                            if url and url not in seen_urls and not any(x in url for x in ['google', 'linkedin', 'indeed', 'stepstone', 'xing', 'youtube', 'facebook', 'twitter']):
                                seen_urls.add(url)
                                leads.append({"Company": res.get('title', 'Unknown'), "Website": url, "City": city})
                        success = True
                        break # Success with this backend
                except Exception as e:
                    print(f"[WARN] Search error with backend {backend} for {query}: {e}")
                    time.sleep(2)
            if not success:
                print(f"[ERROR] Failed to get results for {query} with any backend.")
            time.sleep(1)
    return leads

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cities-file", default="germany_major_cities.txt")
    parser.add_argument("--output", default="pflegefachkraft_leads.csv")
    parser.add_argument("--limit", type=int, default=10, help="Max cities to scan")
    args = parser.parse_args()

    if not os.path.exists(args.cities_file):
        print(f"Error: {args.cities_file} not found.")
        return

    with open(args.cities_file, 'r', encoding='utf-8') as f:
        cities = [line.strip() for line in f if line.strip()]

    all_leads = []
    output_path = Path(args.output)
    
    # Load existing if available
    existing_emails = set()
    if output_path.exists():
        try:
            df_old = pd.read_csv(output_path)
            existing_emails = set(df_old['Email'].str.lower())
            print(f"Loaded {len(existing_emails)} existing leads.")
        except: pass

    for i, city in enumerate(cities[:args.limit]):
        print(f"\n--- Progress: {i+1}/{args.limit} cities ---")
        leads = discover_leads(city)
        for lead in leads:
            print(f"[SCRAPE] Scraping: {lead['Company']} ({lead['Website']})")
            emails = collect_emails_from_url(lead['Website'])
            ranked = sorted(emails, key=lambda e: (-score_email(e), e))
            for email in ranked:
                if email not in existing_emails:
                    existing_emails.add(email)
                    new_lead = {**lead, "Email": email, "Type": mailbox_type(email), "Score": score_email(email), "Date": datetime.now().strftime("%Y-%m-%d")}
                    all_leads.append(new_lead)
                    # Append immediately to file
                    pd.DataFrame([new_lead]).to_csv(output_path, mode='a', index=False, header=not output_path.exists())
                    print(f"   [OK] Found: {email}")
                    break # Take best email per company
        time.sleep(1)

    print(f"\nDone! Scraped {len(all_leads)} new leads to {args.output}")

if __name__ == "__main__":
    main()
