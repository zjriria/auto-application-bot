import argparse
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
DISALLOW = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "postmaster",
    "webmaster",
    "abuse",
    "example",
)
GOOD_HINTS = (
    "bewerbung",
    "karriere",
    "personal",
    "ausbildung",
    "pflege",
    "hr",
    "recruit",
    "jobs",
    "info",
    "kontakt",
)
PAGES = ("/impressum",)


def normalize_email(value: str) -> str | None:
    email = value.strip().lower().replace("mailto:", "")
    email = email.strip("'\"<>[](){}")
    email = re.sub(r"^[^a-z0-9]+", "", email)
    email = re.sub(r"[^a-z0-9._%+-]+$", "", email)
    if not EMAIL_REGEX.fullmatch(email):
        return None
    if any(bad in email for bad in DISALLOW):
        return None
    return email


def score(email: str) -> int:
    val = 0
    if any(k in email for k in GOOD_HINTS):
        val += 3
    if email.endswith(".de"):
        val += 1
    return val


def scrape_url(url: str) -> set[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    }
    found = set()
    for suffix in PAGES:
        page = url.rstrip("/") + suffix
        try:
            resp = requests.get(page, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            for raw in EMAIL_REGEX.findall(text):
                cleaned = normalize_email(raw)
                if cleaned:
                    found.add(cleaned)
        except requests.RequestException:
            pass
        time.sleep(0.2)
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest Sachsen application emails from web search results.")
    parser.add_argument("--towns-file", default="saxony_towns_mega.txt")
    parser.add_argument("--seed", default="saxony_200_emails.csv")
    parser.add_argument("--output", default="saxony_200_emails_final.csv")
    parser.add_argument("--target", type=int, default=200)
    parser.add_argument("--results-per-town", type=int, default=20)
    args = parser.parse_args()

    towns_path = Path(args.towns_file)
    if not towns_path.exists():
        raise FileNotFoundError(f"Towns file missing: {towns_path}")

    towns = [line.strip() for line in towns_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    rows = []
    seen = set()
    if Path(args.seed).exists():
        seed_df = pd.read_csv(args.seed)
        for _, r in seed_df.iterrows():
            email = str(r.get("Email", "")).strip().lower()
            if normalize_email(email):
                seen.add(email)
                rows.append(
                    {
                        "City": r.get("City", "Sachsen"),
                        "Clinic Name": r.get("Clinic Name", ""),
                        "Email": email,
                        "Source URL": r.get("Source URL", ""),
                        "Score": int(r.get("Score", score(email))),
                    }
                )

    with DDGS() as ddgs:
        for town in towns:
            if len(seen) >= args.target:
                break
            query = f"Krankenhaus Pflegeheim Klinik {town} Sachsen Bewerbung Kontakt"
            print(f"Searching {town} ...")
            try:
                results = list(ddgs.text(query, max_results=args.results_per_town, backend="html"))
            except Exception:
                continue

            for item in results:
                if len(seen) >= args.target:
                    break
                title = (item.get("title") or "").strip()
                url = (item.get("href") or "").strip()
                if not url:
                    continue
                emails = scrape_url(url)
                if not emails:
                    continue

                ranked = sorted(emails, key=score, reverse=True)
                for email in ranked:
                    if email in seen:
                        continue
                    seen.add(email)
                    rows.append(
                        {
                            "City": town,
                            "Clinic Name": title or "Unknown",
                            "Email": email,
                            "Source URL": url,
                            "Score": score(email),
                        }
                    )
                    if len(seen) >= args.target:
                        break

    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["Email"], keep="first")
    out = out.sort_values(["Score", "City", "Clinic Name"], ascending=[False, True, True]).head(args.target)
    out.to_csv(args.output, index=False)
    out.to_excel(Path(args.output).with_suffix(".xlsx"), index=False)
    print(f"Saved {len(out)} unique emails to {args.output}")


if __name__ == "__main__":
    main()
