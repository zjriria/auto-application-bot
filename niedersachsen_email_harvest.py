import argparse
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from clinic_finder import find_care_facilities

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
DISALLOWED = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "postmaster",
    "example",
    "test@",
)
HINT_HR = ("bewerbung", "karriere", "personal", "ausbildung", "pflege", "hr", "recruit", "jobs", "job")
HINT_INFO = ("info", "kontakt")
PAGES = (
    "/impressum",
)
LINK_HINTS = (
    "kontakt",
    "impressum",
    "team",
    "ansprechpartner",
    "leitung",
    "karriere",
    "jobs",
    "job",
    "ausbildung",
    "bewerbung",
    "pflege",
    "dialyse",
    "hospiz",
    "wohnen",
    "senior",
    "reha",
)
SEARCH_QUERIES: Sequence[str] = (
    "Pflegedienst Niedersachsen",
    "Hospiz Niedersachsen",
    "Betreutes Wohnen Niedersachsen",
    "Dialyse Niedersachsen",
    "Seniorenresidenz Niedersachsen",
    "Pflegezentrum Niedersachsen",
    "Seniorenheim Niedersachsen",
    "Reha Niedersachsen",
    "Klinik Niedersachsen",
    "Krankenhaus Niedersachsen",
    "MVZ Niedersachsen",
)

TOWN_QUERIES: Sequence[str] = (
    "Pflegedienst {town} Niedersachsen",
    "Hospiz {town} Niedersachsen",
    "Betreutes Wohnen {town} Niedersachsen",
    "Dialyse {town} Niedersachsen",
    "Pflegeheim {town} Kontakt",
    "Pflegedienst {town} Impressum",
    "MVZ {town} Niedersachsen",
    "Reha {town} Niedersachsen",
    "Krankenhaus {town} Niedersachsen",
    "Pflegeheim {town} Niedersachsen",
    "Klinik {town} Niedersachsen",
)

PRIORITY_TOWNS: Sequence[str] = (
    "Hannover",
    "Braunschweig",
    "Osnabrueck",
    "Oldenburg",
    "Goettingen",
    "Hildesheim",
    "Wolfsburg",
    "Lueneburg",
    "Celle",
    "Salzgitter",
    "Wilhelmshaven",
    "Delmenhorst",
    "Cuxhaven",
    "Lingen",
    "Nordhorn",
    "Goslar",
    "Aurich",
    "Vechta",
    "Diepholz",
    "Nienburg Weser",
    "Buxtehude",
    "Walsrode",
    "Bad Fallingbostel",
)


def normalize_email(raw: str) -> Optional[str]:
    email = raw.strip().lower().replace("mailto:", "")
    email = email.strip("'\"<>[](){}")
    email = re.sub(r"^[^a-z0-9]+", "", email)
    email = re.sub(r"[^a-z0-9._%+-]+$", "", email)
    if not EMAIL_REGEX.fullmatch(email):
        return None
    if any(token in email for token in DISALLOWED):
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
        score += 3
    if email.startswith("info@") or email.startswith("kontakt@"):
        score += 1
    if email.endswith(".de"):
        score += 1
    return score


def read_towns(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Town list not found: {path}")
    towns: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            towns.append(stripped)
    if not towns:
        raise ValueError(f"Town list {path} does not contain usable entries.")
    return list(dict.fromkeys(towns))


def prioritize_towns(towns: Sequence[str]) -> List[str]:
    ranked: List[str] = []
    remaining = list(towns)
    for priority in PRIORITY_TOWNS:
        for town in list(remaining):
            if town.lower() == priority.lower():
                ranked.append(town)
                remaining.remove(town)
                break
    ranked.extend(remaining)
    return ranked


def collect_emails_from_url(
    url: str,
    timeout: int = 12,
    page_delay: float = 0.25,
    max_depth: int = 2,
    max_pages: int = 30,
) -> Set[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    }
    found: Set[str] = set()
    queue: List[tuple[str, int]] = [(url.rstrip("/") + suffix, 0) for suffix in PAGES]
    visited: Set[str] = set()
    parsed_base = urlparse(url)

    while queue and len(visited) < max_pages:
        page, depth = queue.pop(0)
        normalized_page = page.rstrip("/")
        if normalized_page in visited:
            continue
        visited.add(normalized_page)

        try:
            resp = requests.get(page, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            for raw in EMAIL_REGEX.findall(text):
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
                elif depth < max_depth:
                    linked = urljoin(page, href)
                    parsed_link = urlparse(linked)
                    if parsed_link.scheme in {"http", "https"} and parsed_link.netloc == parsed_base.netloc:
                        link_text = f"{parsed_link.path} {parsed_link.query}".lower()
                        if any(hint in link_text for hint in LINK_HINTS):
                            queue.append((linked, depth + 1))
        except requests.RequestException:
            continue
        time.sleep(max(page_delay, 0.0))
    return found


def discover_urls_from_facilities(region_or_town: str) -> List[dict]:
    candidates: List[dict] = []
    try:
        facilities = find_care_facilities(region_or_town)
    except Exception as exc:
        print(f"⚠️ OSM lookup failed for {region_or_town}: {exc}")
        return candidates

    for facility in facilities:
        url = str(facility.get("URL", "")).strip()
        if not url:
            continue
        candidates.append(
            {
                "Clinic Name": facility.get("Clinic Name", "Unbekannt"),
                "Town": region_or_town,
                "Website": url,
                "Source": "OSM",
            }
        )
    return candidates


def discover_urls_with_ddgs(query: str, label: str, max_results: int = 12, ddgs_delay: float = 0.35) -> List[dict]:
    candidates: List[dict] = []
    backends = ("lite", "html", "api")
    try:
        with DDGS() as ddgs:
            results = []
            for backend in backends:
                try:
                    results = list(ddgs.text(query, max_results=max_results, backend=backend))
                    if results:
                        break
                except Exception:
                    time.sleep(max(ddgs_delay, 0.0))
                    continue
            if not results:
                return candidates
            for item in results:
                url = str(item.get("href") or item.get("url") or "").strip()
                title = str(item.get("title") or "Unbekannt").strip()
                if not url:
                    continue
                candidates.append(
                    {
                        "Clinic Name": title,
                        "Town": label,
                        "Website": url,
                        "Source": "DDGS",
                    }
                )
            time.sleep(max(ddgs_delay, 0.0))
    except Exception as exc:
        print(f"⚠️ DDGS lookup failed for {label}: {exc}")
    return candidates


def dedupe_urls(records: Iterable[dict]) -> List[dict]:
    unique: List[dict] = []
    seen: Set[str] = set()
    for record in records:
        url = str(record.get("Website", "")).strip().lower()
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(record)
    return unique


def build_candidates(
    towns: Sequence[str],
    include_state_seed: bool,
    ddgs_results: int,
    skip_osm: bool,
    ddgs_delay: float,
) -> List[dict]:
    raw: List[dict] = []
    if include_state_seed:
        print("🌍 Seeding from statewide Niedersachsen search...")
        for query in SEARCH_QUERIES:
            raw.extend(discover_urls_with_ddgs(query, label="Niedersachsen", max_results=ddgs_results, ddgs_delay=ddgs_delay))

    for idx, town in enumerate(towns, start=1):
        print(f"[{idx}/{len(towns)}] Discovering sites for {town}...")
        if not skip_osm:
            raw.extend(discover_urls_from_facilities(town))
        for query in TOWN_QUERIES:
            raw.extend(
                discover_urls_with_ddgs(
                    query.format(town=town),
                    label=town,
                    max_results=ddgs_results,
                    ddgs_delay=ddgs_delay,
                )
            )
        time.sleep(0.2)

    return dedupe_urls(raw)


def best_emails_for_site(url: str, page_delay: float, max_depth: int, max_pages: int) -> List[str]:
    emails = collect_emails_from_url(url, page_delay=page_delay, max_depth=max_depth, max_pages=max_pages)
    return sorted(emails, key=lambda e: (-score_email(e), e))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a large Niedersachsen lead list and harvest application emails until a target is reached.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--towns-file", type=Path, default=Path("niedersachsen_towns_mega.txt"))
    parser.add_argument("--output", type=Path, default=Path("niedersachsen_2000_emails.csv"))
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--ddgs-results", type=int, default=12)
    parser.add_argument("--town-limit", type=int, default=0, help="Max towns to process from the seed list (0 means all)")
    parser.add_argument("--skip-osm", action="store_true", help="Skip OSM lookups and use DDGS discovery only")
    parser.add_argument("--skip-ddgs", action="store_true", help="Only use OSM discoveries, no DuckDuckGo search")
    parser.add_argument("--skip-state-seed", action="store_true", help="Skip the broad Niedersachsen OSM seed query")
    parser.add_argument("--sleep-seconds", type=float, default=0.25, help="Delay between page requests")
    parser.add_argument("--ddgs-delay", type=float, default=0.35, help="Delay between DDGS searches")
    parser.add_argument("--max-depth", type=int, default=2, help="Max internal link depth per site")
    parser.add_argument("--max-pages-per-site", type=int, default=30, help="Max pages to crawl per site")
    parser.add_argument("--checkpoint-every", type=int, default=100, help="Save interim CSV/XLSX after this many scanned sites")
    args = parser.parse_args()

    towns = prioritize_towns(read_towns(args.towns_file))
    if args.town_limit and args.town_limit > 0:
        towns = towns[: args.town_limit]
    candidates = build_candidates(
        towns,
        include_state_seed=not args.skip_state_seed,
        ddgs_results=args.ddgs_results,
        skip_osm=args.skip_osm,
        ddgs_delay=max(args.ddgs_delay, 0.0),
    )
    if args.skip_ddgs:
        candidates = [candidate for candidate in candidates if candidate.get("Source") == "OSM"]

    if not candidates:
        print("No candidate sites discovered.")
        return

    rows: List[dict] = []
    seen_emails: Set[str] = set()
    if args.output.exists():
        try:
            existing = pd.read_csv(args.output)
            for _, row in existing.iterrows():
                email = str(row.get("Email", "")).strip().lower()
                if email:
                    seen_emails.add(email)
                    rows.append(
                        {
                            "Region": str(row.get("Region", "Niedersachsen")),
                            "Town": str(row.get("Town", "Niedersachsen")),
                            "Clinic Name": str(row.get("Clinic Name", "Unbekannt")),
                            "Website": str(row.get("Website", "")),
                            "Email": email,
                            "Mailbox Type": str(row.get("Mailbox Type", mailbox_type(email))),
                            "Score": int(row.get("Score", score_email(email))),
                            "Source": str(row.get("Source", "")),
                            "Collected At": str(row.get("Collected At", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
                        }
                    )
            print(f"Loaded {len(seen_emails)} existing emails from {args.output}")
        except Exception as exc:
            print(f"Warning: could not load existing output ({exc}). Continuing fresh.")

    def _write_checkpoint(current_rows: List[dict], label: str) -> None:
        if not current_rows:
            return
        checkpoint_df = pd.DataFrame(current_rows)
        checkpoint_df = checkpoint_df.drop_duplicates(subset=["Email"], keep="first")
        checkpoint_df = checkpoint_df.sort_values(["Score", "Town", "Clinic Name", "Email"], ascending=[False, True, True, True])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_df.to_csv(args.output, index=False)
        checkpoint_df.to_excel(args.output.with_suffix(".xlsx"), index=False)
        print(f"Checkpoint ({label}): saved {len(checkpoint_df)} unique emails to {args.output}")

    for idx, candidate in enumerate(candidates, start=1):
        if len(seen_emails) >= args.target:
            break

        clinic = str(candidate.get("Clinic Name", "Unbekannt")).strip()
        town = str(candidate.get("Town", "Niedersachsen")).strip()
        url = str(candidate.get("Website", "")).strip()
        source = str(candidate.get("Source", "")).strip()

        print(f"\n[{idx}/{len(candidates)}] Scraping {clinic} | {town} | {url}")
        ranked_emails = best_emails_for_site(
            url,
            page_delay=args.sleep_seconds,
            max_depth=max(args.max_depth, 0),
            max_pages=max(args.max_pages_per_site, 1),
        )
        if not ranked_emails:
            continue

        for email in ranked_emails:
            if email in seen_emails:
                continue
            seen_emails.add(email)
            rows.append(
                {
                    "Region": "Niedersachsen",
                    "Town": town,
                    "Clinic Name": clinic,
                    "Website": url,
                    "Email": email,
                    "Mailbox Type": mailbox_type(email),
                    "Score": score_email(email),
                    "Source": source,
                    "Collected At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            if len(seen_emails) >= args.target:
                break

        if idx % 50 == 0:
            print(f"Progress: {idx}/{len(candidates)} sites scanned, unique emails so far: {len(seen_emails)}")
        if args.checkpoint_every > 0 and idx % args.checkpoint_every == 0:
            _write_checkpoint(rows, label=f"{idx}/{len(candidates)}")

    if not rows:
        print("No emails collected.")
        return

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["Email"], keep="first")
    df = df.sort_values(["Score", "Town", "Clinic Name", "Email"], ascending=[False, True, True, True])
    df = df.head(args.target)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    df.to_excel(args.output.with_suffix(".xlsx"), index=False)
    print(f"\n✅ Saved {len(df)} unique emails to {args.output} and {args.output.with_suffix('.xlsx')}")


if __name__ == "__main__":
    main()
