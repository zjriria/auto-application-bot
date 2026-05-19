# Automate sending emails from all remaining batches in new_email_lists_round/
# Tracks SENT/FAILED for each batch and provides final summary

$batchDir = "new_email_lists_round"
$delaySeconds = 15
$logFile = "batch_automation_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').log"
$summaryFile = "batch_automation_summary_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').txt"

# Collect all batch files
$batches = @()
1..7 | ForEach-Object {
    $file = "$batchDir\new_round_list_$_.csv"
    if (Test-Path $file) {
        $batches += $file
    }
}

if ($batches.Count -eq 0) {
    Write-Output "No batch files found in $batchDir"
    exit 1
}

Write-Output "Found $($batches.Count) batch files to send. Starting automation..."
Write-Output "Delay between emails: $delaySeconds seconds"
Add-Content -Path $logFile -Value "=== Batch Automation Started: $(Get-Date) ==="
Add-Content -Path $logFile -Value "Total batches: $($batches.Count)"

$overallSent = 0
$overallFailed = 0
$totalBatches = $batches.Count

foreach ($i in 0..($batches.Count-1)) {
    $batch = $batches[$i]
    $batchNum = $i + 1
    $headerMsg = "=== BATCH $batchNum / $totalBatches : " + $batch + " ==="
    
    Write-Output ""
    Write-Output $headerMsg
    Write-Output "Starting send at $(Get-Date)"
    Add-Content -Path $logFile -Value ""
    Add-Content -Path $logFile -Value $headerMsg
    Add-Content -Path $logFile -Value "Started: $(Get-Date)"
    
    # Run sender and capture output
    $output = & python send_from_csv.py --input $batch --delay-seconds $delaySeconds 2>&1
    
    # Extract final results line
    $finalLine = $output | Where-Object { $_ -match "Finished\. SENT=|SENT=.*FAILED=" } | Select-Object -Last 1
    
    if ($finalLine) {
        Write-Output $finalLine
        Add-Content -Path $logFile -Value $finalLine
        
        # Parse SENT and FAILED counts
        if ($finalLine -match "SENT=(\d+).*FAILED=(\d+)") {
            $sent = [int]$matches[1]
            $failed = [int]$matches[2]
            $overallSent += $sent
            $overallFailed += $failed
            
            Write-Output "  Summary: $sent SENT, $failed FAILED"
            Add-Content -Path $logFile -Value "  Summary: $sent SENT, $failed FAILED"
        }
    } else {
        # Fallback: count from output
        Write-Output "Could not parse final results. Full output logged."
        $output | ForEach-Object { Add-Content -Path $logFile -Value $_ }
    }
    
    Write-Output "Completed at $(Get-Date)"
    Add-Content -Path $logFile -Value "Completed: $(Get-Date)"
    
    # Final summary output
    if ($i -lt ($batches.Count - 1)) {
        Write-Output "Pausing before next batch..."
        Start-Sleep -Seconds 3
    }
}

# Generate final summary
$summary = @"
================================================================================
BATCH AUTOMATION SUMMARY - $(Get-Date)
================================================================================
Total Batches Processed: $totalBatches
Total Emails SENT: $overallSent
Total Emails FAILED: $overallFailed
Total Attempted: $($overallSent + $overallFailed)
Success Rate: $(if ($($overallSent + $overallFailed) -gt 0) { [math]::Round(($overallSent / ($overallSent + $overallFailed)) * 100, 2) } else { "N/A" })%

Batch Directory: $batchDir
Delay Between Emails: $delaySeconds seconds
Log File: $logFile
================================================================================
"@

Write-Output ""
Write-Output $summary
Add-Content -Path $summaryFile -Value $summary

Write-Output "Automation complete!"
Write-Output "Results saved to: $summaryFile"
