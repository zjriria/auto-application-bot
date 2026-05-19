#!/usr/bin/env python3
"""
Scrape leads for Duales Studium Bachelor of Science - Wirtschaftsinformatik.
This follows the same discovery flow as the existing lead scrapers, but uses
Wirtschaftsinformatik-specific search queries.
"""
import argparse
import csv
import codecs
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
DISALLOWED = ("noreply", "no-reply", "donotreply", "postmaster", "example", "test@", "wixpress")
HINT_HR = ("bewerbung", "karriere", "personal", "ausbildung", "it", "hr", "recruit", "jobs", "job", "duales studium", "wirtschaftsinformatik")
HINT_INFO = ("info", "kontakt")
PAGES = ("/impressum",)
LINK_HINTS = ("impressum",)

SEARCH_QUERIES = (
    "Duales Studium Wirtschaftsinformatik {city}",
    "Bachelor of Science Wirtschaftsinformatik Ausbildung {city}",
    "Wirtschaftsinformatik duales Studium {city} Kontakt",
    "IT Studium Wirtschaftsinformatik {city} Impressum",
    "Duales Studium Bachelor of Science Wirtschaftsinformatik {city}",
)


def safe_str(text: str) -> str:
    """Remove non-printable / non-CP1252 chars so print() never crashes on Windows."""
    return text.encode("ascii", errors="ignore").decode("ascii")


def normalize_email(raw: str) -> Optional[str]:
    email = raw.strip().lower().replace("mailto:", "").strip("'\"<>[](){}")
    email = re.sub(r"^[^a-z0-9]+", "", email)
    email = re.sub(r"[^a-z0-9._%+-]+$", "", email)
    if not EMAIL_REGEX.fullmatch(email) or any(token in email for token in DISALLOWED):
        return None
    return email


def mailbox_type(email: str) -> str:
    if any(token in email for token in HINT_HR):
        return "hr"
    if any(token in email for token in HINT_INFO):
        return "info"
    return "other"


def score_email(email: str) -> int:
    score = 0
    if any(token in email for token in HINT_HR):
        score += 5
    if email.startswith("bewerbung@") or email.startswith("jobs@") or email.startswith("karriere@"):
        score += 3
    if email.startswith("info@") or email.startswith("kontakt@"):
        score += 1
    if email.endswith(".de"):
        score += 1
    return score


def collect_emails_from_url(url: str, timeout: int = 15, max_pages: int = 20) -> Set[str]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    found: Set[str] = set()
    queue = [(url.rstrip("/") + suffix, 0) for suffix in PAGES]
    visited: Set[str] = set()
    parsed_base = urlparse(url)

    while queue and len(visited) < max_pages:
        page, depth = queue.pop(0)
        if page in visited:
            continue
        visited.add(page)
        try:
            resp = requests.get(page, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for raw in EMAIL_REGEX.findall(soup.get_text(" ", strip=True)):
                email = normalize_email(raw)
                if email:
                    found.add(email)
            for anchor in soup.find_all("a", href=True):
                href = anchor.get("href", "")
                if "mailto:" in href.lower():
                    maybe = href.split(":", 1)[-1].split("?", 1)[0]
                    email = normalize_email(maybe)
                    if email:
                        found.add(email)
                elif depth < 1:
                    linked = urljoin(page, href)
                    parsed_link = urlparse(linked)
                    if parsed_link.netloc == parsed_base.netloc and any(hint in linked.lower() for hint in LINK_HINTS):
                        queue.append((linked, depth + 1))
        except Exception:
            continue
    return found


def discover_leads(city: str, ddgs_results: int = 15) -> List[dict]:
    print(f"[SEARCH] Searching for Wirtschaftsinformatik leads in {city}...")
    leads = []
    seen_urls = set()
    seen_domains = set()
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
                            url = res.get("href", "").split("?")[0].rstrip("/")
                            domain = urlparse(url).netloc.lower() if url else ""
                            if (
                                url
                                and url not in seen_urls
                                and domain not in seen_domains
                                and not any(x in url for x in ["google", "linkedin", "indeed", "stepstone", "xing", "youtube", "facebook", "twitter"])
                            ):
                                seen_urls.add(url)
                                seen_domains.add(domain)
                                leads.append({"Company": res.get("title", "Unknown"), "Website": url, "City": city})
                        success = True
                        break
                except Exception as e:
                    print(f"[WARN] Search error with backend {backend} for {query}: {e}")
                    time.sleep(2)
            if not success:
                print(f"[FAIL] Failed to get results for {query} with any backend.")
            time.sleep(1)
    return leads


def main():
    parser = argparse.ArgumentParser(description="Scrape Wirtschaftsinformatik dual-study leads")
    parser.add_argument("--cities-file", default="germany_major_cities.txt")
    parser.add_argument("--output", default="wirtschaftsinformatik_leads.csv")
    parser.add_argument("--limit", type=int, default=10, help="Max cities to scan")
    args = parser.parse_args()

    print("=" * 60)
    print("  Wirtschaftsinformatik Lead Scraper")
    print("=" * 60)

    if not os.path.exists(args.cities_file):
        print(f"Error: {args.cities_file} not found.")
        return

    with open(args.cities_file, "r", encoding="utf-8") as f:
        cities = [line.strip() for line in f if line.strip()]

    output_path = Path(args.output)
    existing_emails = set()
    header_written = output_path.exists()

    if output_path.exists():
        try:
            df_old = pd.read_csv(output_path)
            if "Email" in df_old.columns:
                existing_emails = set(df_old["Email"].dropna().astype(str).str.lower())
                print(f"Loaded {len(existing_emails)} existing leads from {args.output}")
        except Exception:
            pass

    # Also cross-check against global sent logs to avoid re-scraping already-applied emails
    for sent_file in ["applications_sent.csv", "wirtschaftsinformatik_applications_sent.csv",
                       "informatiker_applications_sent.csv"]:
        if os.path.exists(sent_file):
            try:
                df_sent = pd.read_csv(sent_file, on_bad_lines="skip")
                if "Email" in df_sent.columns:
                    already = set(df_sent["Email"].dropna().astype(str).str.lower())
                    existing_emails |= already
                    print(f"  Cross-checked {len(already)} emails from {sent_file}")
            except Exception:
                pass

    fieldnames = ["Company", "Website", "City", "Email", "Type", "Score", "Date"]
    new_count = 0
    skipped = 0

    for i, city in enumerate(cities[: args.limit]):
        print(f"\n--- Progress: {i + 1}/{args.limit} cities ---")
        leads = discover_leads(city)
        for lead in leads:
            print(f"[SCRAPE] Scraping: {safe_str(lead['Company'])} ({lead['Website']})")
            try:
                emails = collect_emails_from_url(lead["Website"])
            except Exception as e:
                print(f"   [SKIP] Error scraping {lead['Website']}: {safe_str(str(e))}")
                continue
            ranked = sorted(emails, key=lambda e: (-score_email(e), e))
            for email in ranked:
                if email not in existing_emails:
                    existing_emails.add(email)
                    new_lead = {
                        "Company": lead["Company"],
                        "Website": lead["Website"],
                        "City": lead["City"],
                        "Email": email,
                        "Type": mailbox_type(email),
                        "Score": score_email(email),
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                    }
                    with open(output_path, "a", newline="", encoding="utf-8") as csvf:
                        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
                        if not header_written:
                            writer.writeheader()
                            header_written = True
                        writer.writerow(new_lead)
                    new_count += 1
                    print(f"   [OK] Found: {email}")
                    break  # Take best email per company
                else:
                    skipped += 1
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"  Done! New leads: {new_count} | Skipped (dupes): {skipped}")
    print(f"  Output: {args.output}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()