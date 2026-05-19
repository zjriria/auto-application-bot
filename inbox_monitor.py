import imaplib
import email
from email.header import decode_header
import csv
import os
import time
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER", "ziiko20-maroco@hotmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SENT_FILE = "applications_sent.csv"

def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)

def check_inbox():
    print(f"Connecting to IMAP Server for {GMAIL_USER}...")
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        print("Login successful! Checking Inbox for Bounces or Replies...")
    except Exception as e:
        print(f"IMAP Login failed: {e}")
        return

    # Select inbox
    status, messages = imap.select("INBOX")
    
    # fetch all Unread messages
    # You can change to "ALL" to scan everything
    res, messages = imap.search(None, 'UNREAD')
    
    messages = messages[0].split(b' ')
    
    if not messages or messages == [b'']:
        print("No new unread messages in inbox.")
        imap.logout()
        return

    print(f"Found {len(messages)} unread messages.")
    
    updates_made = 0
    
    # Load sent database
    if not os.path.exists(SENT_FILE):
        print("applications_sent.csv not found! Run the sender first.")
        return
        
    df = pd.read_csv(SENT_FILE)

    for mail in messages:
        if not mail: continue
        
        res, msg_data = imap.fetch(mail, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                # parse a bytes email into a message object
                msg = email.message_from_bytes(response_part[1])
                
                # decode the email subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    # if it's a bytes, decode to str
                    try:
                        subject = subject.decode(encoding if encoding else "utf-8")
                    except:
                        subject = str(subject)
                        
                from_ = msg.get("From")
                print(f"\nScanning Message From: {from_} | Subject: {subject}")
                
                # Simple Bounce Detection
                if "Undelivered Mail" in subject or "Delivery Status Notification" in subject or "mailer-daemon" in str(from_).lower():
                    print("--> ❌ BOUNCE DETECTED!")
                    # Just mark the most recent 'Sent' as Bounced for simplicity in this demo
                    # A robust parser would extract the exact failed email from the bounce body
                    status_val = "Bounced"
                    updates_made += 1
                # Reply detection (Not a bounce)
                else:
                    print("--> 📥 POTENTIAL HR REPLY!")
                    status_val = "Responded"
                    updates_made += 1
                    
                # Mark as read (optional, so it doesn't process again)
                # imap.store(mail, '+FLAGS', '\Seen')

    if updates_made > 0:
        # In a real app, you would match the exact email address.
        # For layout purposes, df.to_csv is available.
        print(f"\nDetected {updates_made} relevant inbox updates. (Implementation would tag row in {SENT_FILE})")
    
    imap.close()
    imap.logout()

if __name__ == "__main__":
    check_inbox()
