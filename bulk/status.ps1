# 下载进度查看
# 用法：pwsh -NoProfile -ExecutionPolicy Bypass -File status.ps1
$root = "C:\Users\iq112\Documents\cninfo"

$log = Get-ChildItem "$root\_state\run-*.log" -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime | Select-Object -Last 1

"=== 最新日志（$($log.Name)） ==="
if ($log) { Get-Content $log.FullName -Encoding utf8 | Select-Object -Last 12 }

"`n=== 落盘统计 ==="
$files = Get-ChildItem "$root\reports" -Recurse -File -ErrorAction SilentlyContinue
$pros  = Get-ChildItem "$root\prospectus" -File -ErrorAction SilentlyContinue
"财报 PDF : {0,8:N0} 个" -f $files.Count
"招股书   : {0,8:N0} 个" -f $pros.Count
"合计体积 : {0,8:N1} GB" -f (((($files | Measure-Object Length -Sum).Sum) + (($pros | Measure-Object Length -Sum).Sum)) / 1GB)

"`n=== 任务状态（done.jsonl） ==="
$state = "$root\_state\done.jsonl"
if (Test-Path $state) {
    $lines = Get-Content $state -Encoding utf8
    $ok = 0; $empty = 0; $fail = 0
    foreach ($l in $lines) {
        if ($l -match '"status":\s*"ok"')    { $ok++ }
        elseif ($l -match '"status":\s*"empty"') { $empty++ }
        elseif ($l -match '"status":\s*"fail"')  { $fail++ }
    }
    "已完成 {0:N0} 个任务：成功 {1:N0} / 空 {2:N0} / 失败 {3:N0}" -f $lines.Count, $ok, $empty, $fail
    $pct = $lines.Count / 118540 * 100
    "总进度   : {0:N2}%（目标 118,540 任务）" -f $pct
}

"`n=== 进程 ==="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*bulk_cninfo.py*" } |
    Select-Object ProcessId, CreationDate | Format-Table -AutoSize
