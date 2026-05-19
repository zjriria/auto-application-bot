Write-Host "Starting Pflegefachmann Scraper..." -ForegroundColor Cyan
python clinic_finder.py
python lead_scraper.py
if (Test-Path "scraped_leads.xlsx") {
    Move-Item -Force "scraped_leads.xlsx" "input.xlsx"
}
python prepare_leads.py --input input.xlsx --output converted_output.csv --sent-log applications_sent.csv --city-label Sachsen
Write-Host "Pflegefachmann Scraping Complete! You can now start the sender." -ForegroundColor Green
