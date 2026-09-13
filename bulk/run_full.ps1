# 全量下载启动器（独立进程运行，避免会话中断杀死任务）
# 用法：pwsh -NoProfile -ExecutionPolicy Bypass -File run_full.ps1
$ErrorActionPreference = "Continue"

$root = "C:\Users\iq112\Documents\cninfo"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$py     = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$driver = "C:\Users\iq112\codes\cninfo-disclosure\bulk\bulk_cninfo.py"
$logDir = Join-Path $root "_state"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$log   = Join-Path $logDir "run-$stamp.log"

# 让 Python 自己写 UTF-8 日志（stdout 走 shell 会变乱码，这里只保留 stderr 排错）
$env:CNINFO_LOG = $log

& $py $driver run --root $root --workers 10 --progress 250 2>> (Join-Path $logDir "stderr.log") | Out-Null
"finished $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') exit=$LASTEXITCODE" | Out-File -FilePath $log -Append -Encoding utf8
