$proc = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and
    $_.CommandLine.Contains('niedersachsen_email_harvest.py') -and
    $_.CommandLine.Contains('--town-limit 40') -and
    $_.CommandLine.Contains('--ddgs-results 25')
}

if ($proc) {
    $proc | Select-Object ProcessId, Name, CreationDate | Format-Table -AutoSize
} else {
    Write-Output 'NOT_RUNNING'
}
