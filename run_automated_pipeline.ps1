Set-Content -Path "live_status.json" -Value '{"status": "Starting Pipeline", "message": "Initializing the automated background pipeline...", "current": 0, "total": 0}'

Write-Host "Starting Lead Scraper..."
python lead_scraper.py

if (Test-Path "scraped_leads.xlsx") {
    Move-Item -Force "scraped_leads.xlsx" "input.xlsx"
}

if (Test-Path "input.xlsx") {
    Write-Host "Normalizing and validating scraped emails..."
    python prepare_leads.py --input input.xlsx --output converted_output.csv --sent-log applications_sent.csv --city-label Sachsen
} else {
    Write-Host "WARNING: No input.xlsx present. Skipping email normalization."
}

Set-Content -Path "live_status.json" -Value '{"status": "Sending Emails", "message": "Scraping finished. Starting AI Bewerbung pipeline...", "current": 1, "total": 1}'

Write-Host "Running pflegefachmann_bewerbung.py..."
python pflegefachmann_bewerbung.py

Set-Content -Path "live_status.json" -Value '{"status": "Completed", "message": "All applications have been fully processed.", "current": 1, "total": 1}'
