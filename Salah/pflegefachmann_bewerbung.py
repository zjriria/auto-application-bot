import os
import time
import random
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from duckduckgo_search import DDGS
import requests
import re
from PyPDF2 import PdfMerger
import fitz  # PyMuPDF for compression
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
try:
    from google import genai as google_genai
except ImportError:  # Fallback when the new SDK is not installed yet
    google_genai = None

import outlook_oauth  # OAuth2 for Hotmail/Outlook accounts

# Load environment variables for the configured sending account.
# This no longer needs Google Maps or OpenAI API keys!
load_dotenv()

GMAIL_USER = os.getenv("PFLEGE_EMAIL_USER", "your_email@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("PFLEGE_EMAIL_PASS", "your_app_password")
EMAIL_DOMAIN = GMAIL_USER.split("@")[-1].lower() if "@" in GMAIL_USER else ""
USE_OAUTH = EMAIL_DOMAIN in {"hotmail.com", "outlook.com", "live.com", "msn.com"}

# Auto-select SMTP defaults for the configured mailbox provider.
if EMAIL_DOMAIN in {"hotmail.com", "outlook.com", "live.com", "msn.com"}:
    DEFAULT_SMTP_HOST_STARTTLS = "smtp.office365.com"
    DEFAULT_SMTP_PORT_STARTTLS = "587"
    DEFAULT_SMTP_HOST_SSL = "smtp.office365.com"
    DEFAULT_SMTP_PORT_SSL = "465"
else:
    DEFAULT_SMTP_HOST_STARTTLS = "smtp.gmail.com"
    DEFAULT_SMTP_PORT_STARTTLS = "587"
    DEFAULT_SMTP_HOST_SSL = "smtp.gmail.com"
    DEFAULT_SMTP_PORT_SSL = "465"

SMTP_HOST_STARTTLS = os.getenv("SMTP_HOST_STARTTLS", DEFAULT_SMTP_HOST_STARTTLS)
SMTP_PORT_STARTTLS = int(os.getenv("SMTP_PORT_STARTTLS", DEFAULT_SMTP_PORT_STARTTLS))
SMTP_HOST_SSL = os.getenv("SMTP_HOST_SSL", DEFAULT_SMTP_HOST_SSL)
SMTP_PORT_SSL = int(os.getenv("SMTP_PORT_SSL", DEFAULT_SMTP_PORT_SSL))

MY_NAME = "Zakaria Jriria"
MY_PHONE = "(+212) 660 944 365"
CITY_TO_SEARCH = "Dresden"  # Change this to your target city for clinic search     "
NUM_RESULTS = 10

EMAIL_SUBJECT_TEMPLATE = "Bewerbung als Pflegefachmann – {clinic}"
VALUE_PROP_BASE = [
    "Sorgfältige Dokumentation und sichere Vitalzeichenkontrolle aus meinem sechsmonatigen Praktikum",
    "Teamfähigkeit aus der Zusammenarbeit mit Rettungsteams und interdisziplinären Stationen",
    "Hohe Belastbarkeit und Empathie im direkten Patientenkontakt",
]
SEND_MAX_RETRIES = int(os.getenv("SEND_MAX_RETRIES", "3"))
SEND_RETRY_BACKOFF = float(os.getenv("SEND_RETRY_BACKOFF", "5"))
SEND_DELAY_JITTER = float(os.getenv("SEND_DELAY_JITTER", "8"))
SMTP_TIMEOUT_SECONDS = float(os.getenv("SMTP_TIMEOUT_SECONDS", "180"))

# --- 0. CONFIGURATION & TOGGLES ---
ENABLE_TIME_GATING = False  # Set to True to only send Tue-Thu 08:30-11:00 CET
HAS_B2_CERTIFICATE = True   # Set to True to inject B2 sentence in the email
ENABLE_AI_CONTENT = True    # Set to True to dynamically generate the opening paragraph via Gemini

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_CLIENT = None
if GEMINI_API_KEY and google_genai:
    try:
        GEMINI_CLIENT = google_genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[AI Error] Konnte Gemini Client nicht initialisieren: {e}")
elif GEMINI_API_KEY and not google_genai:
    print("[AI Hinweis] google-genai Paket nicht verfügbar. Bitte 'pip install google-genai' ausführen.")

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
# Attachments must be sent in this exact order.
ORDERED_ATTACHMENT_FILES = [
    "ANSCHREIBEN.pdf",
    "LEBENSLAUF.pdf",
    "B2 ZERTIFIKAT.pdf",
    "ZEUGNISSE.pdf",
]
# Backward-compatible alias used by older call sites.
ADDITIONAL_ATTACHMENT_FILES = ORDERED_ATTACHMENT_FILES[1:]

# --- 1. PDF MERGING ---
def get_ordered_attachments():
    """Return primary attachment and the remaining files in required order."""
    if not ORDERED_ATTACHMENT_FILES:
        return None, []
    return ORDERED_ATTACHMENT_FILES[0], ORDERED_ATTACHMENT_FILES[1:]


def merge_documents(output_filename="Bewerbung_Pflegefachmann.pdf"):
    """Merges configured application documents into a single PDF (optional workflow)."""
    print("Checking for PDF documents to merge...")

    docs_to_merge = ORDERED_ATTACHMENT_FILES
    existing_docs = [doc for doc in docs_to_merge if os.path.exists(doc)]
    
    if not existing_docs:
        print("No PDF documents found to merge! Please place 'Lebenslauf.pdf', etc. in the script folder.")
        return None
        
    print(f"Merging the following documents: {existing_docs}")
    merger = PdfMerger()
    
    for pdf in existing_docs:
        merger.append(pdf)
    
    merger.write(output_filename)
    merger.close()
    
    # Compress using PyMuPDF (Upgrade 3)
    compressed_name = output_filename
    try:
        doc = fitz.open(output_filename)
        doc.save("compressed_" + output_filename, garbage=4, deflate=True, clean=True)
        doc.close()
        # Replace original with compressed if successful
        os.replace("compressed_" + output_filename, output_filename)
        print(f"Successfully created and compressed {output_filename} to bypass IT Firewalls.")
    except Exception as e:
        print(f"Successfully created {output_filename} (Compression skipped: {e})")
        
    return output_filename

# --- 2. NO-API CLINIC SCRAPER ---
def extract_emails_from_url(url):
    """Visits a website and uses regex to find email addresses."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64 AppleWebKit/537.36)'}
        response = requests.get(url, headers=headers, timeout=10)
        
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, response.text)
        
        # Filter junk emails
        valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.gif', 'wixpress.com'))]
        return list(set(valid_emails))
    except Exception as e:
        print(f"  [!] Could not read {url}")
        return []

def find_clinics(city, num_results=5):
    """Searches for clinics via DuckDuckGo and scrapes their emails (API-Key Free)."""
    search_query = f"Krankenhaus Pflegeheim {city} Kontakt Impressum"
    results_list = []
    
    print(f"Searching DuckDuckGo for clinics in {city}...")
    with DDGS() as ddgs:
        try:
            results = list(ddgs.text(search_query, max_results=num_results, backend="html"))
        except Exception as e:
            print(f"DuckDuckGo Rate Limit Hit: {e}. Try again later or use an API.")
            results = []
        for result in results:
            title = result.get('title', 'Unknown Clinic')
            url = result.get('href', '')
            
            print(f"Checking: {title} ({url})")
            emails = extract_emails_from_url(url)
            
            contact_email = emails[0] if emails else None
            
            if contact_email:
                results_list.append({
                    "Clinic Name": title.split('-')[0].strip(), # Clean up the title a bit
                    "Contact Person": "Sehr geehrte Damen und Herren",
                    "Email": contact_email,
                    "City": city
                })
            time.sleep(3) # Polite scraping delay to avoid DDOSing DuckDuckGo
            
    return results_list


def extract_first_valid_email(raw_field):
    """Cleans messy CSV/Excel email fields and returns the first valid address."""
    if raw_field is None:
        return None
    value = str(raw_field).strip()
    if not value or value.lower() == "nan":
        return None
    normalized = value.replace("\n", ",").replace("|", ",")
    candidates = re.split(r"[;,\s]+", normalized)
    for candidate in candidates:
        cleaned = candidate.strip().strip('"').strip("'")
        cleaned = cleaned.replace("mailto:", "")
        cleaned = cleaned.rstrip('.')
        if cleaned and EMAIL_REGEX.fullmatch(cleaned):
            return cleaned.lower()
    return None

# --- 3. EMAIL TEMPLATE & SENDING ---

def _format_value_props(city) -> str:
    lines = list(VALUE_PROP_BASE)
    if HAS_B2_CERTIFICATE:
        lines.append("Zertifizierte Deutschkenntnisse auf B2-Niveau und sichere Kommunikation mit Angehörigen")
    if city:
        city_clean = str(city).strip()
        if city_clean and city_clean.lower() not in ("nan", "unbekannt"):
            lines.append(f"Einsatzbereitschaft für {city_clean} und umliegende Regionen")
    return "\n".join(f"• {line}" for line in lines)


def _compute_next_delay() -> float:
    base = float(os.getenv("SEND_DELAY_SECONDS", "30"))
    if SEND_DELAY_JITTER <= 0:
        return max(0.0, base)
    jitter = random.uniform(-SEND_DELAY_JITTER, SEND_DELAY_JITTER)
    return max(0.0, base + jitter)


def create_email_body(clinic_name, contact_person="Sehr geehrte Damen und Herren", city=None):
    """Generate the fixed email text requested by the user."""
    return """Sehr geehrte Damen und Herren,

mein Name ist Zakaria Jriria aus Marokko. Ich habe Ihr Angebot auf der Website der Agentur für Arbeit gesehen und fand es sehr interessant. Besonders gefällt mir, dass Sie Auszubildende unterstützen und gute Lernmöglichkeiten bieten.

Ich möchte eine Ausbildung als Pflegefachkraft in Ihrer Einrichtung beginnen. Ich habe großes Interesse an diesem Beruf und möchte gern praktische Erfahrungen sammeln und viel lernen.

Ich bin motiviert und arbeite gern mit Menschen. Außerdem lerne ich schnell und bin zuverlässig.

Meine Unterlagen habe ich im Anhang beigefügt. Da ich aktuell in Marokko bin, möchte ich das Vorstellungsgespräch gerne online machen.

Über eine Einladung zu einem Gespräch würde ich mich sehr freuen.

Mit freundlichen Grüßen
Zakaria Jriria
"""

def send_email(to_email, subject, body, attachment_path, extra_attachments=None, *, max_retries=None, retry_backoff=5.0):
    """Send an email via Gmail SMTP with retry/backoff logic."""
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg['Reply-To'] = GMAIL_USER
    msg['Bcc'] = GMAIL_USER  # BCC yourself
    msg['Subject'] = subject
    msg['X-Mailer'] = "Pflegefachmann-AutoMailer/2.0"

    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    attachments = []
    if attachment_path:
        attachments.append(attachment_path)
    if extra_attachments:
        attachments.extend(extra_attachments)

    attached_any = False
    for path in attachments:
        if not path:
            continue
        if not os.path.exists(path):
            print(f"Warning: Attachment not found and skipped: {path}")
            continue
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
            msg.attach(part)
            attached_any = True
    if not attached_any:
        print("Warning: Keine Anhänge gefunden! Sende nur den Text.")

    attempts = 0
    max_attempts = max_retries or 1
    while attempts < max_attempts:
        try:
            if USE_OAUTH:
                # Use OAuth2 for Hotmail/Outlook accounts
                server = outlook_oauth.smtp_connect_oauth(GMAIL_USER)
                server.send_message(msg)
                server.quit()
                return True
            else:
                # Try both common SMTP transports; slow networks often time out on one path.
                transport_errors = []
                for transport in ("starttls", "ssl"):
                    server = None
                    try:
                        if transport == "starttls":
                            server = smtplib.SMTP(SMTP_HOST_STARTTLS, SMTP_PORT_STARTTLS, timeout=SMTP_TIMEOUT_SECONDS)
                            server.ehlo()
                            server.starttls()
                            server.ehlo()
                        else:
                            server = smtplib.SMTP_SSL(SMTP_HOST_SSL, SMTP_PORT_SSL, timeout=SMTP_TIMEOUT_SECONDS)
                            server.ehlo()

                        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                        server.send_message(msg)
                        server.quit()
                        return True
                    except Exception as transport_exc:
                        transport_errors.append(f"{transport}:{transport_exc}")
                        try:
                            if server:
                                server.quit()
                        except Exception:
                            pass

                raise RuntimeError(" | ".join(transport_errors))
        except Exception as e:
            attempts += 1
            print(f"Failed to send email to {to_email} (Attempt {attempts}/{max_attempts}): {e}")
            if attempts >= max_attempts:
                break
            sleep_for = retry_backoff * (2 ** (attempts - 1)) + random.uniform(0, 1)
            print(f"   ↪️  Warte {sleep_for:.1f}s und versuche es erneut...")
            time.sleep(sleep_for)
    return False

# --- 4. DATA LOGGING & AUTOMATION ---
def main():
    print("=== Pflegefachmann Bewerbungs-Roboter ===")
    
    if os.path.exists("converted_output.csv"):
        clinics_file = "converted_output.csv"
    elif os.path.exists("input.xlsx"):
        clinics_file = "input.xlsx"
    else:
        clinics_file = "clinics.csv"
    
    # ---------------------------------------------------------
    # PHASE 1 & 2: Scrape & Build clinics.csv if it doesn't exist
    # (The Scraper Reality Check)
    # ---------------------------------------------------------
    if not os.path.exists(clinics_file):
        print(f"[!] '{clinics_file}' nicht gefunden. Starte Web-Scraper, um Kliniken in {CITY_TO_SEARCH} zu suchen...")
        clinics = find_clinics(CITY_TO_SEARCH, num_results=NUM_RESULTS)
        
        with open(clinics_file, mode="w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Clinic Name", "Contact Person", "Email", "City"])
            writer.writeheader()
            writer.writerows(clinics)
            
        print(f"\n[✓] {len(clinics)} Kliniken gefunden und in '{clinics_file}' gespeichert.")
        print("\n=== PHASE 1 ABGESCHLOSSEN ===")
        print("WICHTIG (Dein Launch-Plan Phase 1 & 2):")
        print("1. THE SELF-TEST: Ändere die erste Zeile in 'clinics.csv' zu deiner eigenen E-Mail und teste den Versand!")
        print("2. DATA CLEANUP: Überprüfe die echten E-Mail-Adressen manuell (lösche 'datenschutz@...', 'webmaster@...' etc.).")
        print("3. Starte dieses Skript danach erneut, um Phase 3 (Merge) und 4 (Soft Launch) zu starten!")
        return

    # ---------------------------------------------------------
    # PHASE 3 & 4: Merge files and Send applications from clinics.csv
    # ---------------------------------------------------------
    print(f"[+] '{clinics_file}' gefunden. Lese Daten und bereite den Versand vor...")
    
    # 1. Use the required attachment order directly.
    primary_attachment, extra_attachments = get_ordered_attachments()
        
    # 2. Track already sent (CSV)
    sent_file = "applications_sent.csv"
    sent_emails = set()
    
    if os.path.exists(sent_file):
        with open(sent_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                logged_email = row.get("Email", "").strip().lower()
                if logged_email:
                    sent_emails.add(logged_email)
    else:
        # Create new logging file
        with open(sent_file, mode="w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Clinic Name", "Contact Person", "Email", "City", "Status", "Date Sent"])
            writer.writeheader()
            
    # Read manually reviewed clinics
    clinics_to_email = []
    invalid_email_rows = 0
    
    print(f"Versand aus Datei: '{clinics_file}'...")
    
    if clinics_file.endswith(".xlsx"):
        df = pd.read_excel(clinics_file)
        for _, row in df.iterrows():
            email = extract_first_valid_email(row.get("Email", row.get("email", "")))
            if not email:
                invalid_email_rows += 1
                clinic_name = row.get("Clinic Name", row.get("Name", "Unbekannt"))
                print(f"[-] Überspringe '{clinic_name}' – keine gültige Email gefunden.")
                continue
            clinic_name = row.get("Clinic Name", row.get("Name", "Unbekannt"))
            clinics_to_email.append({
                "Clinic Name": str(clinic_name) if clinic_name is not None and not pd.isna(clinic_name) else "Unbekannt",
                "Contact Person": str(row.get("Contact Person", "Sehr geehrte Damen und Herren")) if "Contact Person" in df.columns else "Sehr geehrte Damen und Herren",
                "Email": email,
                "City": str(row.get("City", CITY_TO_SEARCH)) if "City" in df.columns else CITY_TO_SEARCH
            })
    else:
        with open(clinics_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = extract_first_valid_email(row.get("email", row.get("Email", "")))
                if not email:
                    invalid_email_rows += 1
                    clinic_name = row.get("firma", row.get("Clinic Name", "Unbekannt"))
                    print(f"[-] Überspringe '{clinic_name}' – keine gültige Email gefunden.")
                    continue
                clinics_to_email.append({
                    "Clinic Name": str(row.get("firma", row.get("Clinic Name", "Unbekannt"))),
                    "Contact Person": str(row.get("person", row.get("Contact Person", "Sehr geehrte Damen und Herren"))),
                    "Email": email,
                    "City": str(row.get("adresse", row.get("City", CITY_TO_SEARCH)))
                })
                
    if not clinics_to_email:
        print("Keine Emails in der Datei gefunden!")
        return
            
    print(f"Versand an {len(clinics_to_email)} Kontakte wird gestartet...\n")
    if invalid_email_rows:
        print(f"Hinweis: {invalid_email_rows} Kontakte wurden wegen fehlender/ungültiger Email-Adressen übersprungen.")
    
    # Send Loop
    for clinic in clinics_to_email:
        email = clinic["Email"]
        clinic_name = clinic["Clinic Name"]
        if not email or not EMAIL_REGEX.fullmatch(email):
            print(f"[!] Ungültige Email erkannt ({email}). Überspringe {clinic_name}.")
            continue
        email_key = email.lower()
        
        if email_key in sent_emails:
            print(f"Bereits an {email} ({clinic_name}) beworben. Überspringe...")
            continue
            
        print(f"\n[+] Bereite Bewerbung vor für {clinic_name} ({email})")
        body = create_email_body(
            clinic_name,
            clinic.get("Contact Person", "Sehr geehrte Damen und Herren"),
            city=clinic.get("City", CITY_TO_SEARCH),
        )
        subject = EMAIL_SUBJECT_TEMPLATE.format(clinic=clinic_name)
        
        # ---------
        # IMPORTANT (Phase 4: Soft Launch): Uncomment the next line to ACTUALLY send emails for real!
        success = send_email(
            email,
            subject,
            body,
            primary_attachment,
            extra_attachments,
            max_retries=SEND_MAX_RETRIES,
            retry_backoff=SEND_RETRY_BACKOFF,
        )
        # success = True
        print("REAL SEND ACTIVATED!" if success else "SENDEFEHLER – bitte prüfen.")
        # ---------
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        status_text = "Sent" if success else "Failed"
        
        # Upgrade 2: Smart Time-Gating
        if ENABLE_TIME_GATING:
            while True:
                now = datetime.now()
                # 1=Tue, 2=Wed, 3=Thu. Between 08:30 and 11:00
                if now.weekday() in [1, 2, 3] and 8 <= now.hour < 11:
                    if now.hour == 8 and now.minute < 30:
                        pass # too early
                    else:
                        break # In optimal sending window!
                print(f"[{now.strftime('%H:%M')}] Outside optimal HR hours (Tue-Thu 08:30-11:00). Snoozing for 10 minutes...")
                time.sleep(600)
        
        # Log the status immediately to CSV
        with open(sent_file, mode="a", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Clinic Name", "Contact Person", "Email", "City", "Status", "Date Sent"])
            writer.writerow({
                "Clinic Name": clinic_name,
                "Contact Person": clinic.get("Contact Person", "Unbekannt"),
                "Email": email,
                "City": clinic.get("City", CITY_TO_SEARCH),
                "Status": status_text,
                "Date Sent": timestamp
            })
        sent_emails.add(email_key)
        
        if success:
            delay = _compute_next_delay()
            print(f"Log 'Sent' in '{sent_file}' gespeichert. Warte {delay:.1f} Sekunden...")
            time.sleep(delay)
        else:
            print(f"Log 'Failed' in '{sent_file}' gespeichert. Fahre fort...")

    print("\nAlle Bewerbungen verarbeitet! Überprüfe 'applications_sent.csv' für die Historie.")

if __name__ == "__main__":
    main()
