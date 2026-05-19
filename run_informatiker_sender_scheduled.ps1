cd $PSScriptRoot
Write-Output "Starting scheduled sender at $(Get-Date)" >> "informatiker_scheduled_send.log"
python informatiker_bewerbung.py >> "informatiker_scheduled_send.log" 2>&1
Write-Output "Finished scheduled sender at $(Get-Date)" >> "informatiker_scheduled_send.log"
