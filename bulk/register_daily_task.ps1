$ErrorActionPreference = "Stop"

$name = "cninfo-daily-fetch"
$vbs  = "C:\Users\iq112\codes\cninfo-disclosure\bulk\fetch_daily_launcher.vbs"
$wscript = "C:\WINDOWS\System32\wscript.exe"

if (-not (Test-Path $vbs)) { throw "找不到 $vbs" }
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    Write-Host "已存在同名任务，先删除后重建"
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $wscript -Argument "`"$vbs`""
$trigger = New-ScheduledTaskTrigger -Daily -At "02:30"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "iq112" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "每天 02:30 增量抓取 A 股财报/IPO/业绩预告/业绩快报（cninfo by_date 增量层）" `
    -Force | Select-Object TaskName, State | Format-Table -AutoSize | Out-String
