$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and
    $_.CommandLine -and
    $_.CommandLine.Contains('niedersachsen_email_harvest.py')
}

if ($procs) {
    $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Output ("Stopped {0} scraper process(es)." -f $procs.Count)
} else {
    Write-Output 'No scraper process found.'
}

& 'C:/Users/LENOVO/AppData/Local/Programs/Python/Python312/python.exe' niedersachsen_email_harvest.py --skip-osm --town-limit 40 --ddgs-results 25 --output niedersachsen_2000_emails_fast.csv
