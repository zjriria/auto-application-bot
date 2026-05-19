$ErrorActionPreference = 'Stop'

$taskName = 'InformatikerBewerbungSendMonday'
$scriptPath = Join-Path $PSScriptRoot 'run_informatiker_sender_scheduled.ps1'

if (-not (Test-Path $scriptPath)) {
    throw "Missing sender wrapper script: $scriptPath"
}

$now = Get-Date
$runAt = Get-Date -Hour 8 -Minute 0 -Second 0
while ($runAt.DayOfWeek -ne 'Monday' -or $runAt -le $now) {
    $runAt = $runAt.AddDays(1)
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Once -At $runAt
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Starts sending informatiker applications on Monday 8 AM.' | Out-Null

Write-Output "Scheduled '$taskName' for $runAt"
Write-Output "It will run wrapper: $scriptPath"
