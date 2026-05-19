import argparse
import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

import pflegefachmann_bewerbung as b


def load_sent_emails(path: Path) -> set[str]:
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


def ensure_log(path: Path) -> None:
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


def mailbox_ok(email: str) -> bool:
    e = email.lower()
    hr = ("bewerbung", "karriere", "personal", "ausbildung", "pflege", "hr", "recruit", "jobs", "job")
    fallback = ("info", "kontakt")
    return any(k in e for k in hr) or any(k in e for k in fallback)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send refined applications from a CSV with dedupe.")
    parser.add_argument("--input", default="saxony_200_emails_final.csv")
    parser.add_argument("--sent-log", default="applications_sent.csv")
    parser.add_argument("--limit", type=int, help="Optional cap for this run")
    parser.add_argument("--delay-seconds", type=float, default=15.0, help="Fixed delay between emails")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")

    df = pd.read_csv(in_path)
    if "Email" not in df.columns:
        raise ValueError("Input file must contain an Email column")

    ensure_log(Path(args.sent_log))
    sent = load_sent_emails(Path(args.sent_log))

    # Keep first occurrence per email and only application-usable mailbox names
    df["Email"] = df["Email"].astype(str).str.strip().str.lower()
    df = df.drop_duplicates(subset=["Email"], keep="first")
    df = df[df["Email"].apply(lambda x: bool(b.EMAIL_REGEX.fullmatch(x)) and mailbox_ok(x))]

    if args.limit:
        df = df.head(args.limit)

    primary_attachment, extra_attachments = b.get_ordered_attachments()

    to_send = []
    for _, row in df.iterrows():
        email = row["Email"]
        if email in sent:
            continue
        to_send.append(row)

    total = len(to_send)
    if total == 0:
        print("Nothing new to send. All candidate emails already sent.")
        return

    sent_count = 0
    failed_count = 0

    for idx, row in enumerate(to_send, start=1):
        clinic = str(row.get("Clinic Name", "Unbekannt"))
        city = str(row.get("City", "Sachsen"))
        email = row["Email"]

        print(f"[{idx}/{total}] Sending to {clinic} <{email}> ({city})")
        body = b.create_email_body(clinic, "Sehr geehrte Damen und Herren", city=city)
        subject = b.EMAIL_SUBJECT_TEMPLATE.format(clinic=clinic)
        ok = b.send_email(
            email,
            subject,
            body,
            primary_attachment,
            extra_attachments,
            max_retries=b.SEND_MAX_RETRIES,
            retry_backoff=b.SEND_RETRY_BACKOFF,
        )

        status = "Sent" if ok else "Failed"
        append_log(Path(args.sent_log), clinic, email, city, status)

        if ok:
            sent.add(email)
            sent_count += 1
            print("  -> SENT")
        else:
            failed_count += 1
            print("  -> FAILED")

        if idx < total:
            delay = max(args.delay_seconds, 0.0)
            print(f"  -> waiting {delay:.1f}s")
            import time
            time.sleep(delay)

    print(f"Finished. SENT={sent_count}, FAILED={failed_count}, TOTAL_ATTEMPTED={total}")


if __name__ == "__main__":
    main()
