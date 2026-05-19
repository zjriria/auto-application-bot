import argparse
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

from clinic_finder import find_care_facilities

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
DISALLOWED = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "postmaster",
    "webmaster",
    "abuse",
    "example",
)
HR_HINTS = ("bewerbung", "karriere", "personal", "ausbildung", "pflege", "hr", "recruit", "jobs", "job")
INFO_HINTS = ("info", "kontakt")
PAGES = ("/impressum",)


def normalize_email(raw: str) -> str | None:
    email = raw.strip().lower().replace("mailto:", "")
    email = email.strip("'\"<>[](){}")
    email = re.sub(r"^[^a-z0-9]+", "", email)
    email = re.sub(r"[^a-z0-9._%+-]+$", "", email)
    if not EMAIL_REGEX.fullmatch(email):
        return None
    if any(bad in email for bad in DISALLOWED):
        return None
    return email


def mailbox_type(email: str) -> str:
    if any(k in email for k in HR_HINTS):
        return "hr"
    if any(k in email for k in INFO_HINTS):
        return "info"
    return "other"


def read_towns(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def scrape_emails(url: str, timeout: int = 10) -> Set[str]:
    found: Set[str] = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    }
    for suffix in PAGES:
        page = url.rstrip("/") + suffix
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
        except requests.RequestException:
            continue
        time.sleep(0.3)
    return found


def choose_clinic_emails(candidates: Set[str]) -> List[Tuple[str, str]]:
    if not candidates:
        return []
    hr = sorted([e for e in candidates if mailbox_type(e) == "hr"])
    info = sorted([e for e in candidates if mailbox_type(e) == "info"])
    other = sorted([e for e in candidates if mailbox_type(e) == "other"])

    # Rule: prefer HR; only if no HR exists, include validated info/kontakt; else fallback to first other.
    if hr:
        return [(hr[0], "hr")]
    if info:
        return [(info[0], "info")]
    if other:
        return [(other[0], "other")]
    return []


def run_pass(towns_by_region: Dict[str, List[str]], global_seen: Set[str]) -> List[dict]:
    rows: List[dict] = []
    for region, towns in towns_by_region.items():
        for town in towns:
            print(f"\n[{region}] town: {town}")
            facilities = find_care_facilities(town)
            for facility in facilities:
                clinic = facility.get("Clinic Name", "")
                url = facility.get("URL", "")
                city = facility.get("City", town)
                if not url:
                    continue
                emails = scrape_emails(url)
                selected = choose_clinic_emails(emails)
                for email, kind in selected:
                    if email in global_seen:
                        continue
                    global_seen.add(email)
                    rows.append(
                        {
                            "Region": region,
                            "City": city,
                            "Clinic Name": clinic,
                            "Email": email,
                            "Mailbox Type": kind,
                            "Source URL": url,
                            "Collected At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
    return rows


def load_existing(output_csv: Path) -> Tuple[pd.DataFrame, Set[str]]:
    if not output_csv.exists():
        return pd.DataFrame(), set()
    df = pd.read_csv(output_csv)
    seen = {str(v).strip().lower() for v in df.get("Email", pd.Series(dtype=str)).dropna().tolist() if str(v).strip()}
    return df, seen


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeated regional email extraction with dedupe and HR-first selection.")
    parser.add_argument("--sachsen-towns", default="saxony_towns_mega.txt")
    parser.add_argument("--include-nearby", action="store_true", help="Include Thueringen, Sachsen-Anhalt, Brandenburg")
    parser.add_argument("--thueringen-towns", default="thueringen_towns.txt")
    parser.add_argument("--sachsen-anhalt-towns", default="sachsen_anhalt_towns.txt")
    parser.add_argument("--brandenburg-towns", default="brandenburg_towns.txt")
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--interval-minutes", type=float, default=90.0)
    parser.add_argument("--target", type=int, default=200)
    parser.add_argument("--output", default="regional_application_emails.csv")
    args = parser.parse_args()

    output_csv = Path(args.output)
    existing_df, seen = load_existing(output_csv)

    towns_by_region: Dict[str, List[str]] = {"Sachsen": read_towns(Path(args.sachsen_towns))}
    if args.include_nearby:
        towns_by_region["Thueringen"] = read_towns(Path(args.thueringen_towns))
        towns_by_region["Sachsen-Anhalt"] = read_towns(Path(args.sachsen_anhalt_towns))
        towns_by_region["Brandenburg"] = read_towns(Path(args.brandenburg_towns))

    end_time = datetime.now() + timedelta(hours=max(args.duration_hours, 0.0))
    pass_idx = 0
    collected_rows: List[dict] = []

    while datetime.now() <= end_time:
        pass_idx += 1
        print(f"\n=== PASS {pass_idx} started at {datetime.now():%Y-%m-%d %H:%M:%S} ===")
        new_rows = run_pass(towns_by_region, seen)
        if new_rows:
            collected_rows.extend(new_rows)
            print(f"PASS {pass_idx}: added {len(new_rows)} new emails")
        else:
            print(f"PASS {pass_idx}: no new emails")

        total_unique = len(seen)
        print(f"Current unique total: {total_unique}")
        if total_unique >= args.target:
            print(f"Target {args.target} reached.")
            break

        if datetime.now() + timedelta(minutes=args.interval_minutes) > end_time:
            break
        sleep_seconds = max(args.interval_minutes, 0.0) * 60.0
        print(f"Sleeping {sleep_seconds/60:.1f} minutes before next pass...")
        time.sleep(sleep_seconds)

    new_df = pd.DataFrame(collected_rows)
    final_df = pd.concat([existing_df, new_df], ignore_index=True) if not existing_df.empty else new_df
    if not final_df.empty:
        final_df = final_df.drop_duplicates(subset=["Email"], keep="first")
        final_df.to_csv(output_csv, index=False)
        final_df.to_excel(output_csv.with_suffix(".xlsx"), index=False)
        print(f"Saved {len(final_df)} unique emails to {output_csv}")
    else:
        print("No emails collected.")


if __name__ == "__main__":
    main()
