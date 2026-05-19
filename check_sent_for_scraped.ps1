$scrapedPath = 'niedersachsen_2000_emails.csv'
$sentLogPath = 'applications_sent.csv'
$outPath = 'niedersachsen_sent_history_check.csv'

if (-not (Test-Path $scrapedPath)) {
    throw "Missing file: $scrapedPath"
}
if (-not (Test-Path $sentLogPath)) {
    throw "Missing file: $sentLogPath"
}

$scraped = Import-Csv $scrapedPath
$sentLog = Import-Csv $sentLogPath

$sentByEmail = @{}
foreach ($row in $sentLog) {
    if (-not $row.Email) { continue }

    $emailKey = $row.Email.Trim().ToLower()
    if (-not $sentByEmail.ContainsKey($emailKey)) {
        $sentByEmail[$emailKey] = New-Object System.Collections.ArrayList
    }

    [void]$sentByEmail[$emailKey].Add($row)
}

$uniqueScraped = $scraped |
    Where-Object { $_.Email -and $_.Email.Trim() -ne '' } |
    Sort-Object Email -Unique

$result = foreach ($row in $uniqueScraped) {
    $emailKey = $row.Email.Trim().ToLower()
    $history = @()

    if ($sentByEmail.ContainsKey($emailKey)) {
        $history = $sentByEmail[$emailKey]
    }

    $statuses = $history | ForEach-Object { "$(($_.Status).Trim().ToLower())" }
    $everSent = $statuses -contains 'sent'
    $everFailed = $statuses -contains 'failed'

    $lastEntry = $null
    if ($history.Count -gt 0) {
        $lastEntry = $history |
            Sort-Object { [datetime]::Parse($_.'Date Sent') } -Descending |
            Select-Object -First 1
    }

    [PSCustomObject]@{
        Email = $row.Email
        EverSentViaApp = $everSent
        EverFailedViaApp = $everFailed
        LastKnownStatus = if ($lastEntry) { $lastEntry.Status } else { '' }
        LastSentTimestamp = if ($lastEntry) { $lastEntry.'Date Sent' } else { '' }
        ClinicName = $row.'Clinic Name'
        Town = $row.Town
    }
}

$result | Export-Csv -Path $outPath -NoTypeInformation -Encoding UTF8

$total = $result.Count
$sentCount = ($result | Where-Object { $_.EverSentViaApp -eq $true }).Count
$failedOnlyCount = ($result | Where-Object { $_.EverSentViaApp -ne $true -and $_.EverFailedViaApp -eq $true }).Count
$neverProcessedCount = ($result | Where-Object { $_.EverSentViaApp -ne $true -and $_.EverFailedViaApp -ne $true }).Count

Write-Output "TOTAL_CHECKED=$total"
Write-Output "EVER_SENT=$sentCount"
Write-Output "FAILED_ONLY=$failedOnlyCount"
Write-Output "NEVER_PROCESSED=$neverProcessedCount"
Write-Output "OUTPUT_FILE=$outPath"
