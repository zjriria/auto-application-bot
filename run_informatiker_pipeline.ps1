# Automation Pipeline for Informatiker Ausbildung Applications

Write-Host "🚀 Starting Germany-wide Informatiker Ausbildung Pipeline..." -ForegroundColor Cyan

# 1. Scraping Phase
# Scan the first 5 cities for beginning, can be increased later
Write-Host "`n[1/2] Scraping for new IT leads (First 5 cities)..." -ForegroundColor Yellow
python informatiker_lead_scraper.py --limit 5

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ Scraper encountered an error but continuing to sender phase..." -ForegroundColor Red
}

read-host "Press Enter to start sending applications (Ctrl+C to abort)..."

# 2. Application Phase
Write-Host "`n[2/2] Sending application emails..." -ForegroundColor Yellow
python informatiker_bewerbung.py

Write-Host "`n✅ Pipeline execution finished!" -ForegroundColor Green
Write-Host "Check 'informatiker_leads.csv' and 'informatiker_applications_sent.csv' for details."
