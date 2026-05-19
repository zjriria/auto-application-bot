#!/usr/bin/env python3
"""
Send application emails for Duales Studium B.Sc. Wirtschaftsinformatik.
Reads leads from a CSV, deduplicates against all sent logs, and dispatches
emails with attachments and retry logic.
"""
import argparse
import csv
import email.utils
import os
import random
import re
import smtplib
import ssl
import time
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
from dotenv import load_dotenv


load_dotenv()

# --- CREDENTIALS ---
# Try WIRTSCHAFT-specific creds first, then INFO, then placeholder
GMAIL_USER = os.getenv("WIRTSCHAFT_EMAIL_USER") or os.getenv("INFO_EMAIL_USER") or "your_email@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("WIRTSCHAFT_EMAIL_PASS") or os.getenv("INFO_EMAIL_PASS") or "your_app_password"
EMAIL_DOMAIN = GMAIL_USER.split("@")[1].lower() if "@" in GMAIL_USER else ""

# --- SMTP CONFIG ---
if EMAIL_DOMAIN in {"hotmail.com", "outlook.com", "live.com", "msn.com"}:
    SMTP_HOST = "smtp.office365.com"
    SMTP_PORT = 587
else:
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587

# --- PERSONAL INFO ---
MY_NAME = "Zakariae Jriria"
MY_PHONE = "(+212) 660 944 365"

# --- FILE PATHS ---
SENT_FILE = "wirtschaftsinformatik_applications_sent.csv"
LEADS_FILE = "wirtschaftsinformatik_leads.csv"

# --- REGEX ---
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)

# --- RETRY CONFIG ---
SEND_MAX_RETRIES = 3
SEND_RETRY_BACKOFF = 10
SMTP_TIMEOUT_SECONDS = 30

# --- ATTACHMENTS (in display order) ---
ORDERED_ATTACHMENT_FILES = [
    "zakariae_tabular.pdf",
    "ANSCHREIBEN_DS.pdf",
    "ZEUGNISSE-DS.pdf",
    "B2 ZERTIFIKAT.pdf",
]

# --- EMAIL CONTENT ---
EMAIL_SUBJECT_TEMPLATE = "Bewerbung fuer das Duale Studium B.Sc. Wirtschaftsinformatik - Zakariae Jriria"
EMAIL_BODY_TEMPLATE = """\
Sehr geehrte Damen und Herren,

hiermit bewerbe ich mich um einen Platz fuer das Duale Studium Bachelor of Science in Wirtschaftsinformatik in Ihrem Unternehmen.

Im Gegensatz zu klassischen Schulabgaengern bringe ich bereits ein starkes praktisches und akademisches Fundament fuer diese Position mit. Ich verfuege ueber einen Bachelor-Abschluss in Wirtschaft und Management, der mir ein tiefes Verstaendnis fuer Unternehmensstrategien und Geschaeftsprozesse verliehen hat. Um dieses wirtschaftliche Know-how mit technischer Umsetzungskompetenz zu vereinen, habe ich kuerzlich eine intensive Zertifizierung im Bereich Software- und Cloud-Architektur mit Spezialisierung auf Java-Backend-Entwicklung und Microservices erfolgreich abgeschlossen.

Meine Faehigkeit, diese IT-Kenntnisse auch unter Druck zur Loesung komplexer Probleme einzusetzen, konnte ich bereits erfolgreich unter Beweis stellen: unter anderem durch den 1. Platz beim Wettbewerb Hackdays sowie den 5. Platz beim Hackathon RamadanIA.

Dieser duale Hintergrund macht die Wirtschaftsinformatik zur passenden Wahl fuer meine berufliche Laufbahn und stellt sicher, dass ich Ihrem Team vom ersten Tag des Studiums an einen direkten, praktischen Mehrwert bieten kann.

Meinen Lebenslauf sowie ein detailliertes Anschreiben finden Sie im Anhang dieser E-Mail. Ich freue mich sehr ueber die Gelegenheit, meine Qualifikationen in einem persoenlichen Gespraech mit Ihnen zu besprechen.

Vielen Dank fuer Ihre Zeit und die Pruefung meiner Unterlagen.

Mit freundlichen Gruessen

Zakariae Jriria
+212 660 944 365
jririazakariae@gmail.com
linkedin.com/in/zakariae-jriria
"""

def load_all_sent_emails(*extra_logs):
    """Load every email we've ever sent to across all sent-log files."""
    sent = set()
    default_logs = [
        "applications_sent.csv",
        SENT_FILE,
        "informatiker_applications_sent.csv",
    ]
    for log_path in list(default_logs) + list(extra_logs):
        if os.path.exists(log_path):
            try:
                df = pd.read_csv(log_path, on_bad_lines="skip")
                if "Email" in df.columns:
                    sent |= set(df["Email"].dropna().astype(str).str.strip().str.lower())
            except Exception:
                pass
    return sent


def get_ordered_attachments():
    """Return (primary, extras) where primary is the first existing file."""
    existing = [f for f in ORDERED_ATTACHMENT_FILES if os.path.exists(f)]
    if not existing:
        print("[WARN] No attachment files found in working directory!")
        return None, []
    return existing[0], existing[1:]


def send_email(to_email, subject, body, attachments, max_retries=SEND_MAX_RETRIES, retry_backoff=SEND_RETRY_BACKOFF):
    """Send a single email with retry logic."""
    msg = MIMEMultipart("mixed")
    msg["From"] = email.utils.formataddr((MY_NAME, GMAIL_USER))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = email.utils.formataddr((MY_NAME, GMAIL_USER))
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=EMAIL_DOMAIN)
    msg["MIME-Version"] = "1.0"
    msg["Auto-Submitted"] = "no"

    msg.attach(MIMEText(body, "plain", "utf-8"))

    attached_any = False
    for path in attachments:
        if os.path.exists(path):
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
                msg.attach(part)
                attached_any = True

    if not attached_any:
        print("  [WARN] No attachments were found/attached!")

    for attempt in range(1, max_retries + 1):
        try:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS)
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg, from_addr=GMAIL_USER, to_addrs=[to_email])
            server.quit()
            return True
        except Exception as e:
            print(f"  [RETRY {attempt}/{max_retries}] Failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_backoff * attempt)
    return False


def ensure_sent_log(path):
    """Create the sent-log file with headers if it doesn't exist."""
    if os.path.exists(path):
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Company", "Email", "City", "Status", "Date"])
        writer.writeheader()


def append_sent_log(path, company, email, city, status):
    """Append one row to the sent log."""
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Company", "Email", "City", "Status", "Date"])
        writer.writerow({
            "Company": company,
            "Email": email,
            "City": city,
            "Status": status,
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


def main():
    print("=" * 60)
    print("  Wirtschaftsinformatik Application System")
    print(f"  Sender: {GMAIL_USER}")
    print("=" * 60)

    parser = argparse.ArgumentParser(description="Send Wirtschaftsinformatik applications")
    parser.add_argument("--input", default=LEADS_FILE, help="Input CSV file with leads")
    parser.add_argument("--sent-log", default=SENT_FILE, help="Sent log CSV (default: wirtschaftsinformatik_applications_sent.csv)")
    parser.add_argument("--limit", type=int, help="Max number of emails to send in this run")
    parser.add_argument("--delay-min", type=float, default=120.0, help="Min delay between sends (seconds)")
    parser.add_argument("--delay-max", type=float, default=240.0, help="Max delay between sends (seconds)")
    args = parser.parse_args()

    leads_file = args.input
    sent_file = args.sent_log

    if not os.path.exists(leads_file):
        print(f"Error: {leads_file} not found. Run the scraper first.")
        return

    # Ensure sent log exists
    ensure_sent_log(sent_file)

    # Load ALL sent emails across every log for global dedup
    sent_emails = load_all_sent_emails(sent_file)
    print(f"Global dedup pool: {len(sent_emails)} emails already sent.")

    # Load and filter leads
    df_leads = pd.read_csv(leads_file)
    df_leads["Email"] = df_leads["Email"].astype(str).str.strip().str.lower()
    df_leads = df_leads[df_leads["Email"].str.contains("@", na=False)]
    df_leads = df_leads.drop_duplicates(subset=["Email"], keep="first")
    leads_to_apply = df_leads[~df_leads["Email"].isin(sent_emails)]

    if args.limit:
        leads_to_apply = leads_to_apply.head(args.limit)

    if leads_to_apply.empty:
        print("No new leads to process. All emails already sent.")
        return

    total = len(leads_to_apply)
    print(f"Starting application process for {total} new leads...\n")

    sent_count = 0
    failed_count = 0

    for idx, (_, row) in enumerate(leads_to_apply.iterrows(), start=1):
        company = str(row.get("Company", "Unbekannt"))
        email = row["Email"]
        city = str(row.get("City", ""))

        print(f"[{idx}/{total}] Processing: {company} <{email}>" + (f" ({city})" if city else ""))
        subject = EMAIL_SUBJECT_TEMPLATE
        body = EMAIL_BODY_TEMPLATE

        success = send_email(email, subject, body, ORDERED_ATTACHMENT_FILES)

        status = "Sent" if success else "Failed"
        append_sent_log(sent_file, company, email, city, status)

        if success:
            sent_count += 1
            sent_emails.add(email)
            print(f"  -> SENT ({sent_count} total)")
            if idx < total:
                delay = random.uniform(args.delay_min, args.delay_max)
                print(f"  -> Waiting {delay:.1f}s before next send...")
                time.sleep(delay)
        else:
            failed_count += 1
            print("  -> FAILED")
            time.sleep(5)

    print(f"\n{'=' * 60}")
    print(f"  Finished. SENT={sent_count} | FAILED={failed_count} | TOTAL={total}")
    print(f"  Sent log: {sent_file}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
