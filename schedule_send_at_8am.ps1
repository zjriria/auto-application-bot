$ErrorActionPreference = 'Stop'

$taskName = 'SendAllMailsAt8AM'
$scriptPath = Join-Path $PSScriptRoot 'send_all_remaining_batches.ps1'

if (-not (Test-Path $scriptPath)) {
    throw "Missing sender script: $scriptPath"
}

$now = Get-Date
$runAt = Get-Date -Hour 8 -Minute 0 -Second 0
if ($runAt -le $now) {
    $runAt = $runAt.AddDays(1)
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Once -At $runAt
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Starts the remaining mail batches at 8:00 AM.' | Out-Null

Write-Output "Scheduled '$taskName' for $runAt"
Write-Output "It will run: $scriptPath"