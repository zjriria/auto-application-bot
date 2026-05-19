$ErrorActionPreference = 'Stop'

$taskName = 'SendEmailsIndividuallyAt8AM'
$scriptPath = Join-Path $PSScriptRoot 'send_from_csv.py'
$csvPath = Join-Path $PSScriptRoot 'niedersachsen_2000_emails.csv'
$delaySeconds = 20

if (-not (Test-Path $scriptPath)) {
    throw "Missing sender script: $scriptPath"
}

if (-not (Test-Path $csvPath)) {
    throw "Missing email list: $csvPath"
}

$pythonExe = 'C:/Users/LENOVO/AppData/Local/Programs/Python/Python312/python.exe'
$arguments = "send_from_csv.py --input $csvPath --sent-log applications_sent.csv --delay-seconds $delaySeconds"

$now = Get-Date
$runAt = Get-Date -Hour 8 -Minute 0 -Second 0
if ($runAt -le $now) {
    $runAt = $runAt.AddDays(1)
}

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Once -At $runAt
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Sends all Niedersachsen emails individually, one at a time with 20-second delays, starting at 8:00 AM.' | Out-Null

Write-Output "Scheduled '$taskName' for $runAt"
Write-Output "Each email will have a $delaySeconds second delay"
Write-Output "Will send from: $csvPath"
