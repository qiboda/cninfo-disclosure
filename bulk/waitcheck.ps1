# 等待 + 进度快照
# 用法：pwsh -NoProfile -ExecutionPolicy Bypass -File waitcheck.ps1 -Seconds 575 -View brief|full
param(
    [int]$Seconds = 575,
    [ValidateSet("brief", "full")]
    [string]$View = "brief"
)

$root = "C:\Users\iq112\Documents\cninfo"
Start-Sleep -Seconds $Seconds

$log = (Get-ChildItem "$root\_state\run-*.log" | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$tail = Get-Content $log -Encoding utf8 | Select-Object -Last 1
"[$([datetime]::Now.ToString('HH:mm:ss'))] $tail"

$proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*bulk_cninfo.py*" }
if (-not $proc) { "!! 下载进程已退出" }

if ($View -eq "full") {
    $files = Get-ChildItem "$root\reports", "$root\prospectus" -Recurse -File -ErrorAction SilentlyContinue
    # 注意：PowerShell 的 1GB = 2^30（即 GiB），与 Python 侧 /1e9 的十进制 GB 不同，勿混用
    $gb = [math]::Round((($files | Measure-Object Length -Sum).Sum) / 1GB, 1)
    $pros = (Get-ChildItem "$root\prospectus" -File -ErrorAction SilentlyContinue).Count
    $zero = ($files | Where-Object { $_.Length -lt 10KB }).Count
    "文件 {0:N0} 个（招股书 {1}）｜{2} GiB｜<10KB 疑似损坏 {3} 个" -f $files.Count, $pros, $gb, $zero
    $fails = Select-String -Path "$root\_state\done.jsonl" -Pattern '"status": "fail"' -Encoding utf8 |
             Measure-Object | Select-Object -ExpandProperty Count
    "失败任务累计 $fails 条"
}
