## Bewerbung als Pflegefachmann Automation

This directory contains two ways to automate your applications for the "Ausbildung als Pflegefachmann":

### Option 1: Python Script (`pflegefachmann_bewerbung.py`)
This script uses the Google Maps API to search for institutions (Krankenhaus, Pflegeheim) in a specific city, extracts their emails (if available in their Places details or via a web search), generates a customized cover letter using OpenAI, and sends the email via your Gmail account.

**Prerequisites**:
1. Install Python packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Your script is completely **API-Key Free**! It uses DuckDuckGo to scrape Google for Hospitals and Emails automatically. You only need your Gmail App Password to send.
   Create a `.env` file in this directory with:
   ```
   GMAIL_USER=your_email@gmail.com
   GMAIL_APP_PASSWORD=your_gmail_app_password
   ```
3. Prepare your application. Put your `Lebenslauf.pdf` and `Zeugnis.pdf` in this folder. The script will automatically merge them using PyPDF2.
4. Run the script:
   ```bash
   python pflegefachmann_bewerbung.py
   ```
   By default, the outbound email only contains the merged `Bewerbung_Pflegefachmann_<name>.pdf`. If you want to attach extra originals, populate the `ADDITIONAL_ATTACHMENT_FILES` list in `pflegefachmann_bewerbung.py`.

### Option 1b: NRW Clinic Batch Runner (`clinic_batch_runner.py`)
Use this helper to call `clinic_finder.py` across many NRW towns and automatically merge the results into a single CSV.

```bash
python clinic_batch_runner.py \
   --cities Siegen Detmold Euskirchen \
   --aggregate-output found_clinics_nrw.csv
```

Key flags:
- `--cities` list of towns (omit to use built-in NRW defaults)
- `--cities-file path.txt` read towns from file (one per line)
- `--skip-individual` only produce the aggregate CSV
- `--sleep-seconds 5` slow down between API calls

Every city still honors `clinic_finder.py` filtering (only facilities with websites).

### Option 2: One-Click NRW Outreach (`nrw_email_automation.py`)
This orchestrator discovers clinics in smaller NRW towns, scrapes recruiter emails, and (optionally) sends your Bewerbungen in one pass.

```bash
python nrw_email_automation.py --cities Siegen Soest Euskirchen --limit-per-city 8 --email-delay 20
```

Key behaviors:
- Defaults to a curated NRW town list unless you provide `--cities` or `--cities-file`.
- Uses the same PDF attachments and email copy defined in `pflegefachmann_bewerbung.py`.
- Writes all harvested leads to `nrw_leads_ready.csv` and appends send results to `applications_sent.csv`.
- Add `--skip-send` to only build the lead list or `--dry-run` to preview without SMTP activity.
- Email delivery now includes retry/backoff and jittered delays. Tune via env vars:
   - `SEND_MAX_RETRIES` (default 3)
   - `SEND_RETRY_BACKOFF` (seconds, default 5)
   - `SEND_DELAY_SECONDS` + `SEND_DELAY_JITTER` (seconds, default 30 ± 8)

### Option 2b: Niedersachsen 2000-Email Harvest (`niedersachsen_email_harvest.py`)
This collector builds a large Niedersachsen lead list and extracts validated email addresses until it reaches a target count.

```bash
python niedersachsen_email_harvest.py --target 2000 --output niedersachsen_2000_emails.csv
```

Key behaviors:
- Uses `niedersachsen_towns_mega.txt` as the default town seed list.
- Prioritizes larger cities and high-yield care towns first, then falls back to the rest of the seed list.
- Combines statewide OSM discovery, per-town OSM lookups, and DuckDuckGo site discovery.
- Expands discovery with care-focused queries like `Pflegedienst`, `Hospiz`, `Betreutes Wohnen`, and `Dialyse`.
- Scrapes multiple contact pages per site plus shallow internal links and keeps only valid, deduplicated mailbox addresses.
- Writes both CSV and XLSX outputs for downstream filtering or sending.

### Option 3: n8n Workflow (`n8n_pflegefachmann_workflow.json`)
If you already use n8n (as seen in the YouTube video), we have provided a visual workflow.

**How to Import**:
1. Open your n8n dashboard.
2. Create a "New workflow".
3. In the top right menu (...), click **Import from file**.
4. Select `n8n_pflegefachmann_workflow.json` from this folder.
5. You will need to click on the Nodes to add your credentials (Google Maps API, OpenAI, Gmail).
