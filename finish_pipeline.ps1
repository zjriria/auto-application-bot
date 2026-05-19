while ($true) {
    $scraper = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "lead_scraper.py" }
    if (-not $scraper) {
        Write-Host "Scraper finished! Moving to next step..."
        break
    }
    Write-Host "Scraper still running... waiting 60 seconds."
    Start-Sleep -Seconds 60
}

if (Test-Path "scraped_leads.xlsx") {
    Move-Item -Force "scraped_leads.xlsx" "input.xlsx"
    Write-Host "Moved scraped leads to input.xlsx"
} else {
    Write-Host "No scraped_leads.xlsx found, using existing input.xlsx if it exists."
}

Write-Host "Running pflegefachmann_bewerbung.py..."
python pflegefachmann_bewerbung.py
Write-Host "Pipeline completely finished!"
