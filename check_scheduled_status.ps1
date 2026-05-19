Write-Output "=== Scheduled Email Send Tasks ==="
Write-Output ""

$task1 = Get-ScheduledTask -TaskName 'SendAllMailsAt8AM' -ErrorAction SilentlyContinue
if ($task1) {
    Write-Output "Task 1: SendAllMailsAt8AM"
    Write-Output "  State: $($task1.State)"
    $info1 = Get-ScheduledTaskInfo -TaskName 'SendAllMailsAt8AM' -ErrorAction SilentlyContinue
    if ($info1) {
        Write-Output "  Last Run: $($info1.LastRunTime)"
        Write-Output "  Last Result: $($info1.LastTaskResult)"
    }
} else {
    Write-Output "Task 1: SendAllMailsAt8AM - NOT FOUND"
}

Write-Output ""

$task2 = Get-ScheduledTask -TaskName 'SendEmailsIndividuallyAt8AM' -ErrorAction SilentlyContinue
if ($task2) {
    Write-Output "Task 2: SendEmailsIndividuallyAt8AM"
    Write-Output "  State: $($task2.State)"
    $info2 = Get-ScheduledTaskInfo -TaskName 'SendEmailsIndividuallyAt8AM' -ErrorAction SilentlyContinue
    if ($info2) {
        Write-Output "  Last Run: $($info2.LastRunTime)"
        Write-Output "  Last Result: $($info2.LastTaskResult)"
    }
} else {
    Write-Output "Task 2: SendEmailsIndividuallyAt8AM - NOT FOUND"
}

Write-Output ""
Write-Output "=== Summary ==="
if ($task2 -and $task2.State -eq 'Ready') {
    Write-Output "YES: SendEmailsIndividuallyAt8AM is scheduled and ready."
    Write-Output "All remaining emails will be sent individually at 8:00 AM with 20-second delays."
} else {
    Write-Output "NO: Neither task is properly active."
}
