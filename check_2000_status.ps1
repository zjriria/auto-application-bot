$proc = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and
    $_.CommandLine.Contains('niedersachsen_email_harvest.py') -and
    $_.CommandLine.Contains('--target 2000')
}

if ($proc) {
    Write-Output 'RUNNING'
    $proc | Select-Object ProcessId, CreationDate | Format-Table -AutoSize
} else {
    Write-Output 'FINISHED'
}

if (Test-Path 'niedersachsen_2000_emails.csv') {
    $count = (Import-Csv 'niedersachsen_2000_emails.csv').Count
    Write-Output ("CURRENT_UNIQUE_EMAILS={0}" -f $count)
} else {
    Write-Output 'CURRENT_UNIQUE_EMAILS=0'
}
