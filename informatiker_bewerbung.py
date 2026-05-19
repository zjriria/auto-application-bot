import os
import time
import random
import csv
import smtplib
import email.utils
import re
import pandas as pd
import argparse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GMAIL_USER = os.getenv("INFO_EMAIL_USER", "your_email@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("INFO_EMAIL_PASS", "your_app_password")
EMAIL_DOMAIN = GMAIL_USER.split("@")[-1].lower() if "@" in GMAIL_USER else ""

# SMTP Configuration
if EMAIL_DOMAIN in {"hotmail.com", "outlook.com", "live.com", "msn.com"}:
    SMTP_HOST = "smtp.office365.com"
    SMTP_PORT = 587
else:
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587

MY_NAME = "Zakariae Jriria"
MY_PHONE = "(+212) 660 944 365"
SENT_FILE = "informatiker_applications_sent.csv"
LEADS_FILE = "informatiker_leads.csv"

# Attachments
ORDERED_ATTACHMENT_FILES = [
    "Lebenslauf-IT.pdf",
    "ANSCHREIBEN-IT.pdf",
    "B2 ZERTIFIKAT.pdf",
    "ZEUGNISSE-IT.pdf",
]

# --- EMAIL CONTENT ---
# User-provided subject and body
EMAIL_SUBJECT_TEMPLATE = "Bewerbung um einen Ausbildungsplatz zum Fachinformatiker – {company}"
EMAIL_BODY_TEMPLATE = """Sehr geehrte Damen und Herren,

mein Name ist Zakariae Jriria aus Marokko. Ich habe Ihr Angebot auf der Website der Agentur für Arbeit gesehen und fand es sehr interessant. Besonders gefällt mir, dass Sie Auszubildende fördern und ein innovatives Lernumfeld bieten.

Ich möchte eine Ausbildung zum Fachinformatiker in Ihrem Unternehmen beginnen. Ich begeistere mich sehr für die Softwareentwicklung und konnte bereits wertvolle praktische Erfahrungen sammeln. So habe ich beispielsweise eigenständig das Projektmanagement-Tool „Agility“ auf Basis einer Microservices-Architektur entwickelt. Zudem konnte ich meine Fähigkeiten erfolgreich bei Wettbewerben unter Beweis stellen: Ich habe den 1. Platz bei den „Hackdays“ mit einem KI-gestützten Bewässerungssystem gewonnen und den 5. Platz beim „Hackathon RamadanIA“ belegt.

Mein Bachelor-Abschluss in Wirtschaft und Management bildet dabei eine solide Grundlage für meine strukturierte und analytische Arbeitsweise. Ich bin sehr motiviert, lerne schnell und verfüge bereits über Deutschkenntnisse auf dem Niveau B2.

Meine vollständigen Unterlagen habe ich im Anhang beigefügt. Da ich mich aktuell noch in Marokko befinde, würde ich mich sehr freuen, wenn ein erstes Vorstellungsgespräch online stattfinden könnte.

Über eine Einladung zu einem Gespräch freue ich mich sehr.

Mit freundlichen Grüßen
Zakariae Jriria
"""

def send_email(to_email, subject, body, attachments):
    msg = MIMEMultipart("mixed")
    msg['From'] = email.utils.formataddr((MY_NAME, GMAIL_USER))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Reply-To'] = email.utils.formataddr((MY_NAME, GMAIL_USER))
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Message-ID'] = email.utils.make_msgid(domain=EMAIL_DOMAIN)
    msg['MIME-Version'] = '1.0'
    msg['X-Mailer'] = 'Mozilla Thunderbird 115.0'

    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    attached_any = False
    for path in attachments:
        if os.path.exists(path):
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                msg.attach(part)
                attached_any = True
    
    if not attached_any:
        print("Warning: No attachments found!")

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg, from_addr=GMAIL_USER, to_addrs=[to_email])
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send to {to_email}: {e}")
        return False

def main():
    print("=== Informatiker Application System ===")
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=LEADS_FILE, help='Input CSV file with leads')
    args = parser.parse_args()
    leads_file = args.input
    
    if not os.path.exists(leads_file):
        print(f"Error: {leads_file} not found. Run the scraper first.")
        return

    # Load sent history - always use the consolidated applications_sent.csv
    sent_file = "applications_sent.csv"
    sent_emails = set()
    if os.path.exists(sent_file):
        df_sent = pd.read_csv(sent_file)
        sent_emails = set(df_sent['Email'].str.lower())
        print(f"Already applied to {len(sent_emails)} companies.")
    else:
        with open(sent_file, "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Company", "Email", "Status", "Date"])
            writer.writeheader()

    # Read Leads from specified input file
    df_leads = pd.read_csv(leads_file)
    df_leads['Email'] = df_leads['Email'].str.lower()
    
    # Filter leads
    leads_to_apply = df_leads[~df_leads['Email'].isin(sent_emails)]
    
    if leads_to_apply.empty:
        print("No new leads to process.")
        return

    print(f"Starting application process for {len(leads_to_apply)} new leads...")
    
    for idx, row in leads_to_apply.iterrows():
        company = row['Company']
        email = row['Email']
        
        print(f"\n[+] Processing: {company} ({email})")
        subject = EMAIL_SUBJECT_TEMPLATE.format(company=company)
        body = EMAIL_BODY_TEMPLATE
        
        success = send_email(email, subject, body, ORDERED_ATTACHMENT_FILES)
        
        status = "Sent" if success else "Failed"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(sent_file, "a", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Company", "Email", "Status", "Date"])
            writer.writerow({"Company": company, "Email": email, "Status": status, "Date": timestamp})
        
        if success:
            print(f"[SUCCESS] Application sent successfully!")
            delay = random.uniform(30, 60)
            print(f"Waiting {delay:.1f}s before next send...")
            time.sleep(delay)
        else:
            print(f"[ERROR] Failed to send application.")
            time.sleep(5)

if __name__ == "__main__":
    main()
