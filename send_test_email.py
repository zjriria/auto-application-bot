"""Quick one-off script to send a test email to zjriria@gmail.com."""
import os
import smtplib
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("WIRTSCHAFT_EMAIL_USER") or os.getenv("INFO_EMAIL_USER", "zakariaejriria@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("WIRTSCHAFT_EMAIL_PASS") or os.getenv("INFO_EMAIL_PASS")

EMAIL_DOMAIN = GMAIL_USER.split("@")[1].lower() if "@" in GMAIL_USER else ""
if EMAIL_DOMAIN in {"hotmail.com", "outlook.com", "live.com", "msn.com"}:
    SMTP_HOST = "smtp.office365.com"
    SMTP_PORT = 587
else:
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587

TO_EMAIL = "tmt3alilech@gmail.com"
SENDER_NAME = "Zakariae Jriria"

# Attachments (DS application documents)
ORDERED_ATTACHMENT_FILES = [
    "zakariae_tabular.pdf",
    "ANSCHREIBEN_DS.pdf",
    "ZEUGNISSE-DS.pdf",
    "B2 ZERTIFIKAT.pdf",
]

EMAIL_SUBJECT = "Bewerbung für das Duale Studium B.Sc. Wirtschaftsinformatik – Zakariae Jriria"
EMAIL_BODY = """\
Sehr geehrte Damen und Herren,

hiermit bewerbe ich mich um einen Platz für das Duale Studium Bachelor of Science in Wirtschaftsinformatik in Ihrem Unternehmen.

Im Gegensatz zu klassischen Schulabgängern bringe ich bereits ein starkes praktisches und akademisches Fundament für diese Position mit. Ich verfüge über einen Bachelor-Abschluss in Wirtschaft und Management, der mir ein tiefes Verständnis für Unternehmensstrategien und Geschäftsprozesse verliehen hat. Um dieses wirtschaftliche Know-how mit technischer Umsetzungskompetenz zu vereinen, habe ich kürzlich eine intensive Zertifizierung im Bereich Software- und Cloud-Architektur (mit Spezialisierung auf Java-Backend-Entwicklung und Microservices) erfolgreich abgeschlossen.

Meine Fähigkeit, diese IT-Kenntnisse auch unter Druck zur Lösung komplexer Probleme einzusetzen, konnte ich bereits erfolgreich unter Beweis stellen: Unter anderem durch den 1. Platz beim Wettbewerb „Hackdays" sowie den 5. Platz beim „Hackathon RamadanIA".

Dieser duale Hintergrund macht die Wirtschaftsinformatik zur perfekten Wahl für meine berufliche Laufbahn und stellt sicher, dass ich Ihrem Team vom ersten Tag des Studiums an einen direkten, praktischen Mehrwert bieten kann.

Meinen Lebenslauf sowie ein detailliertes Anschreiben finden Sie im Anhang dieser E-Mail. Ich freue mich sehr über die Gelegenheit, meine Qualifikationen in einem persönlichen Gespräch mit Ihnen zu besprechen.

Vielen Dank für Ihre Zeit und die Prüfung meiner Unterlagen.

Mit freundlichen Grüßen

Zakariae Jriria
+212 660 944 365
zakariaejriria@gmail.com
linkedin.com/in/zakariae-jriria
"""


def main():
    print(f"Sending test email from {SENDER_NAME} <{GMAIL_USER}> to {TO_EMAIL}...")
    print(f"SMTP: {SMTP_HOST}:{SMTP_PORT}")

    msg = MIMEMultipart("mixed")

    # --- Anti-spam headers ---
    msg["From"] = email.utils.formataddr((SENDER_NAME, GMAIL_USER))
    msg["To"] = TO_EMAIL
    msg["Subject"] = EMAIL_SUBJECT
    msg["Reply-To"] = email.utils.formataddr((SENDER_NAME, GMAIL_USER))
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=EMAIL_DOMAIN)
    msg["MIME-Version"] = "1.0"
    msg["X-Mailer"] = "Mozilla Thunderbird 115.0"

    # Body
    msg.attach(MIMEText(EMAIL_BODY, "plain", "utf-8"))

    # Attach documents
    for path in ORDERED_ATTACHMENT_FILES:
        if os.path.exists(path):
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
                msg.attach(part)
                size_kb = os.path.getsize(path) / 1024
                print(f"  [OK] Attached: {path} ({size_kb:.0f} KB)")
        else:
            print(f"  [MISSING] Not found: {path}")

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"\n[SUCCESS] Email sent successfully to {TO_EMAIL}!")
    except Exception as e:
        print(f"\n[FAILED] Failed to send: {e}")


if __name__ == "__main__":
    main()
