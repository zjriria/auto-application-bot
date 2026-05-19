$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and
    $_.CommandLine -and
    $_.CommandLine.Contains('niedersachsen_email_harvest.py')
}
if ($procs) {
    $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Output ("Stopped {0} existing scraper process(es)." -f $procs.Count)
}

& 'C:/Users/LENOVO/AppData/Local/Programs/Python/Python312/python.exe' niedersachsen_email_harvest.py --skip-osm --ddgs-results 25 --ddgs-delay 0.5 --town-limit 0 --target 2000 --sleep-seconds 0.05 --max-depth 2 --max-pages-per-site 40 --checkpoint-every 100 --output niedersachsen_2000_emails.csv
