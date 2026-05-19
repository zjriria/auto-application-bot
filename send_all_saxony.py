import csv
import re
import time
from datetime import datetime
from pathlib import Path

import pflegefachmann_bewerbung as b

LIST_PATH = Path("saxony_top_10_town_emails.md")
SENT_LOG_PATH = Path("applications_sent.csv")
LOCK_PATH = Path(".send_all_saxony.lock")

LINE_RE = re.compile(
    r"^\s*(\d+)\.\s*(.*?)\s*-\s*(.*?)\s*-\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*-\s*(\S+)\s*$"
)


def load_already_sent(path: Path) -> set[str]:
    if not path.exists():
        return set()
    sent = set()
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("Email") or "").strip().lower()
            status = (row.get("Status") or "").strip().lower()
            if email and status == "sent":
                sent.add(email)
    return sent


def ensure_sent_log(path: Path) -> None:
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Clinic Name", "Contact Person", "Email", "City", "Status", "Date Sent"],
        )
        writer.writeheader()


def append_log(path: Path, clinic: str, email: str, city: str, status: str) -> None:
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Clinic Name", "Contact Person", "Email", "City", "Status", "Date Sent"],
        )
        writer.writerow(
            {
                "Clinic Name": clinic,
                "Contact Person": "Sehr geehrte Damen und Herren",
                "Email": email,
                "City": city,
                "Status": status,
                "Date Sent": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )


def parse_entries(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"List file not found: {path}")

    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LINE_RE.match(line)
        if not match:
            continue
        _, town, clinic, email, url = match.groups()
        entries.append(
            {
                "town": town.strip(),
                "clinic": clinic.strip(),
                "email": email.strip().lower(),
                "url": url.strip(),
            }
        )

    if not entries:
        raise SystemExit("No valid entries found in the list file.")

    unique_entries = []
    seen = set()
    for entry in entries:
        email = entry["email"]
        if email in seen:
            continue
        seen.add(email)
        unique_entries.append(entry)
    return unique_entries


def acquire_lock(path: Path) -> None:
    try:
        path.open("x", encoding="utf-8").write(str(time.time()))
    except FileExistsError:
        raise SystemExit(
            "Another send_all_saxony.py process appears to be running. Remove .send_all_saxony.lock if this is stale."
        )


def release_lock(path: Path) -> None:
    if path.exists():
        path.unlink()


def main() -> None:
    acquire_lock(LOCK_PATH)
    try:
        ensure_sent_log(SENT_LOG_PATH)
        already_sent = load_already_sent(SENT_LOG_PATH)
        entries = parse_entries(LIST_PATH)

        primary_attachment, extra_attachments = b.get_ordered_attachments()

        subject_template = b.EMAIL_SUBJECT_TEMPLATE
        sent_now = 0
        failed_now = 0
        skipped_now = 0

        for idx, entry in enumerate(entries, start=1):
            clinic = entry["clinic"]
            city = entry["town"]
            to_email = entry["email"]

            if to_email in already_sent:
                skipped_now += 1
                print(f"[{idx}/{len(entries)}] SKIP duplicate {to_email} ({clinic})")
                continue

            print(f"[{idx}/{len(entries)}] Sending to {clinic} <{to_email}> ({city})")
            body = b.create_email_body(clinic, "Sehr geehrte Damen und Herren", city=city)
            subject = subject_template.format(clinic=clinic)

            ok = b.send_email(
                to_email,
                subject,
                body,
                primary_attachment,
                extra_attachments,
                max_retries=b.SEND_MAX_RETRIES,
                retry_backoff=b.SEND_RETRY_BACKOFF,
            )

            if ok:
                sent_now += 1
                status = "Sent"
                already_sent.add(to_email)
                print("  -> SENT")
            else:
                failed_now += 1
                status = "Failed"
                print("  -> FAILED")

            append_log(SENT_LOG_PATH, clinic, to_email, city, status)

            if idx < len(entries):
                delay = b._compute_next_delay()
                print(f"  -> waiting {delay:.1f}s")
                time.sleep(delay)

        print(
            f"Finished. SENT={sent_now}, FAILED={failed_now}, SKIPPED_DUPLICATE={skipped_now}, TOTAL={len(entries)}"
        )
    finally:
        release_lock(LOCK_PATH)


if __name__ == "__main__":
    main()
