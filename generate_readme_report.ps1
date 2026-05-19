$extractedPath = 'niedersachsen_2000_emails.csv'
$sentLogPath = 'applications_sent.csv'
$outPath = 'read.me'

if (-not (Test-Path $extractedPath)) {
    throw "Missing file: $extractedPath"
}
if (-not (Test-Path $sentLogPath)) {
    throw "Missing file: $sentLogPath"
}

$extracted = Import-Csv $extractedPath
$sentLog = Import-Csv $sentLogPath

$extractedEmails = $extracted |
    Where-Object { $_.Email -and $_.Email.Trim() -ne '' } |
    ForEach-Object { $_.Email.Trim().ToLower() } |
    Sort-Object -Unique

$sentForExtracted = $sentLog |
    Where-Object { $_.Email -and $_.Status } |
    Where-Object { $extractedEmails -contains $_.Email.Trim().ToLower() }

$sentEmails = $sentForExtracted |
    Where-Object { $_.Status.Trim().ToLower() -eq 'sent' } |
    ForEach-Object { $_.Email.Trim().ToLower() } |
    Sort-Object -Unique

$failedEmails = $sentForExtracted |
    Where-Object { $_.Status.Trim().ToLower() -eq 'failed' } |
    ForEach-Object { $_.Email.Trim().ToLower() } |
    Sort-Object -Unique

$notProcessed = $extracted |
    Where-Object { $_.Email -and $_.Email.Trim() -ne '' } |
    Where-Object { ($sentEmails -notcontains $_.Email.Trim().ToLower()) -and ($failedEmails -notcontains $_.Email.Trim().ToLower()) }

$lines = @()
$lines += '# Niedersachsen Email Extraction Report'
$lines += ''
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$lines += ''
$lines += '## Summary'
$lines += "- Total extracted emails: $($extractedEmails.Count)"
$lines += "- Sent (unique emails): $($sentEmails.Count)"
$lines += "- Failed (unique emails): $($failedEmails.Count)"
$lines += "- Not processed yet: $($notProcessed.Count)"
$lines += ''
$lines += '## Not Processed Yet (Who Not)'

if ($notProcessed.Count -eq 0) {
    $lines += '- None'
} else {
    foreach ($row in $notProcessed) {
        $clinic = if ($row.'Clinic Name') { $row.'Clinic Name' } else { 'Unknown Clinic' }
        $town = if ($row.Town) { $row.Town } else { 'Unknown Town' }
        $email = $row.Email
        $lines += "- $clinic | $town | $email"
    }
}

$lines += ''
$lines += '## Files Used'
$lines += "- $extractedPath"
$lines += "- $sentLogPath"

Set-Content -Path $outPath -Value $lines -Encoding UTF8
Write-Output "Report written to $outPath"
