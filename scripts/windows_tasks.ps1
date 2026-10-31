# Runs crypto-bot on this Windows PC instead of GitHub Actions, with no visible windows.
# Run once in PowerShell from the repo folder:  powershell -ExecutionPolicy Bypass -File scripts\windows_tasks.ps1
$repo = (Get-Location).Path
$py = (Get-Command pythonw.exe -ErrorAction Stop).Source
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$scan = New-ScheduledTaskAction -Execute $py -Argument "-m bot.scan" -WorkingDirectory $repo
$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(7) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName "crypto-bot scan" -Action $scan -Trigger $hourly -Settings $settings -Force | Out-Null
$bt = New-ScheduledTaskAction -Execute $py -Argument "-m bot.run_backtest --notify" -WorkingDirectory $repo
$monthly = New-ScheduledTaskTrigger -Weekly -WeeksInterval 4 -DaysOfWeek Sunday -At 3am
Register-ScheduledTask -TaskName "crypto-bot backtest" -Action $bt -Trigger $monthly -Settings $settings -Force | Out-Null
Write-Output "Registered 'crypto-bot scan' (hourly at :07) and 'crypto-bot backtest' (every 4 weeks)."
