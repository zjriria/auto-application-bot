$proc = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and
    $_.CommandLine.Contains('niedersachsen_email_harvest.py') -and
    $_.CommandLine.Contains('--town-limit 40') -and
    $_.CommandLine.Contains('--ddgs-results 25')
}

if ($proc) {
    Write-Output 'RUNNING'
    $proc | Select-Object ProcessId, CreationDate | Format-Table -AutoSize
} else {
    Write-Output 'FINISHED'
    if (Test-Path 'niedersachsen_2000_emails_fast.csv') {
        $rows = (Import-Csv 'niedersachsen_2000_emails_fast.csv').Count
        Write-Output ("UNIQUE_EMAILS={0}" -f $rows)
    } else {
        Write-Output 'UNIQUE_EMAILS_FILE_NOT_FOUND'
    }
}
