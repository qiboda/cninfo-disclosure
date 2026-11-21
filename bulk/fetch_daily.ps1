<#
.SYNOPSIS
    按披露日期增量抓取 A 股财报 / IPO / 业绩预告 / 业绩快报 —— 跑一轮就退出。

.DESCRIPTION
    DSH 定时任务（schedule-341cf186）每天 02:30 调它一次。

    和 watch_season.ps1 的分工：
      * watch_season.ps1 是**常驻循环**，靠一个活着的终端/会话撑着。本机实测它随
        会话结束被杀过（2026-10-15 之后 21 天、11-06 之后 15 天都没人抓），只能临时用。
      * 本脚本是**一次性**的，跑完即退，由调度方负责下次再叫它。

    窗口起点用「上次扫到的日期」做**水位**，不是固定回看 N 天：
      * 平时每天只扫最近 3 天多，请求量极小（实测 32 天窗口要翻 181 页、约 10 分钟；
        4 天窗口约 20 页、1 分钟内）。
      * 断更多少天就自动补多少天，不会漏；离线上限 90 天。
      * 右端取「明天」—— 巨潮晚间公告以次日作为披露日期，只查到今天就拿不到当晚新发的。
      * **水位只在本轮零失败时前移**，否则留着让下一轮重新覆盖这些日期。

.PARAMETER Root
    数据根目录（含 by_date/、reports/、manifest.csv 的那个）。

.PARAMETER CatchUpDays
    水位文件缺失时的默认回看天数（默认 30）。平时用不到，只是兜底。

.PARAMETER Streams
    抓取流，默认 q3,ipo,yjyg,yjkb。

.PARAMETER Workers
    并发数，默认 6（巨潮查询接口是 IP 级限流，别开太大）。

.EXAMPLE
    pwsh -File fetch_daily.ps1
    pwsh -File fetch_daily.ps1 -Root E:\cninfo -CatchUpDays 45
#>
param(
    [string]$Root = "E:\cninfo",
    [int]$CatchUpDays = 30,
    [string]$Streams = "q3,ipo,yjyg,yjkb",
    [int]$ReportYear = 0,
    [int]$Workers = 6,
    [string]$Python = "python"
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $here "fetch_by_date.py"
$logDir = Join-Path $Root "_state"
$log    = Join-Path $logDir ("daily-fetch-{0}.log" -f (Get-Date -Format "yyyyMM"))
$marker = Join-Path $logDir "daily-scan.txt"

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    try { Add-Content -Path $log -Value $line -Encoding utf8 } catch { }
    Write-Host $line
}

# 盘没挂上时不要静默失败成「今天没新公告」
if (-not (Test-Path $Root)) {
    Write-Host "数据根目录不存在: $Root（盘未挂载？）"
    exit 2
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $target)) {
    Write-Log "找不到 $target"
    exit 3
}
if ($ReportYear -le 0) { $ReportYear = (Get-Date).Year }

# ── 水位 → 窗口 ──────────────────────────────────────────────
$now     = Get-Date
$untilDt = $now.AddDays(1).Date          # 右端取明天，抓当晚新发公告
$sinceDt = $null

if (Test-Path $marker) {
    $raw = (Get-Content $marker -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($raw) {
        $parsed = [datetime]::MinValue
        if ([datetime]::TryParseExact($raw.Trim(), "yyyy-MM-dd",
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::None, [ref]$parsed)) {
            $sinceDt = $parsed.Date.AddDays(-3)   # 往回多扫 3 天，兜住补发/更正
        }
    }
}
if ($null -eq $sinceDt) { $sinceDt = $now.AddDays(-$CatchUpDays).Date }

$floorDt = $now.AddDays(-90).Date
if ($sinceDt -lt $floorDt) { $sinceDt = $floorDt }
if ($sinceDt -gt $untilDt.AddDays(-2)) { $sinceDt = $untilDt.AddDays(-2) }

$since = $sinceDt.ToString("yyyy-MM-dd")
$until = $untilDt.ToString("yyyy-MM-dd")

Write-Log ("── 开始 窗口 {0} ~ {1} streams={2} year={3} workers={4} root={5}" -f `
    $since, $until, $Streams, $ReportYear, $Workers, $Root)

# ── 跑一轮 ──────────────────────────────────────────────────
$out = @()
& $Python $target run --root $Root --since $since --until $until `
    --streams $Streams --report-year $ReportYear --workers $Workers 2>&1 |
    ForEach-Object {
        $line = "$_"
        $out += $line
        try { Add-Content -Path $log -Value $line -Encoding utf8 } catch { }
    }
$code = $LASTEXITCODE

# ── 水位前移（只在零失败时）─────────────────────────────────
$sawFailure = $false
foreach ($line in $out) {
    if ($line -match '失败\s*([1-9]\d*)\s*[；;]') { $sawFailure = $true }
    if ($line -match '（失败\s*([1-9]\d*)') { $sawFailure = $true }
}

if ($code -eq 0 -and -not $sawFailure) {
    Set-Content -Path $marker -Value $until -Encoding utf8
    Write-Log "── 水位前移到 $until"
} elseif ($sawFailure) {
    Write-Log "── 本轮有条目失败，水位不前移，下一轮会重新覆盖这段日期"
} else {
    Write-Log "── python 非零退出（$code），水位不前移"
}

Write-Log "── 结束 exit=$code"
exit $code
