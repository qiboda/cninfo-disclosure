<#
.SYNOPSIS
    三季报季值守守护 —— 按固定间隔增量抓取「最新一批」财报与 IPO 招股书。

.DESCRIPTION
    循环调用 fetch_by_date.py，每轮取「最近 N 天」作为窗口重新检索：

      * 为什么是滑动窗口而不是「只抓当天」——三季报在披露季里是**回溯补发**的，
        某天漏跑一轮，只抓当天就永久缺那一天；7 天窗口让漏跑自动自愈，
        已下载的内容靠 manifest + 本地文件双重去重，不会重复下载。
      * 为什么每轮重新起一个 python 进程 —— 无状态、崩溃自恢复，
        任何一轮失败都不影响下一轮。

    实测 2025 年三季报季节奏（用于预判何时该加密）：
        10-11 首批 2 家 → 10-18 起 30+/天 → 10-21 起 60~250/天
        → 10-29~31 高峰 708/1160/1732 家。整季约 5,400 份。

.PARAMETER Root
    落盘根目录（含 `by_date/`、`reports/`、`manifest.csv` 的那个）。默认 cninfo 数据集。

.PARAMETER IntervalHours
    两轮之间的间隔小时数。默认 8（即每天 3 轮，成长期与高峰期的当天数据当天落地）。

.PARAMETER CatchUpDays
    每轮回溯天数，默认 7。

.PARAMETER Streams
    抓取流，默认 `q3,ipo`。

.PARAMETER ReportYear
    定期报告所属年份，0 表示取当前年份。

.PARAMETER Until
    超过该日期（含）后守护自动退出，默认 2026-11-05（法定截止 10 月底后几天）。

.EXAMPLE
    pwsh -File watch_season.ps1
    pwsh -File watch_season.ps1 -IntervalHours 4 -CatchUpDays 3
#>
param(
    [string]$Root = "C:\Users\iq112\Documents\cninfo",
    [int]$IntervalHours = 8,
    [int]$CatchUpDays = 7,
    [string]$Streams = "q3,ipo",
    [int]$ReportYear = 0,
    [string]$Until = "2026-11-05",
    [string]$Python = "python"
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $here "fetch_by_date.py"
if (-not (Test-Path $target)) { throw "找不到 $target" }
if ($ReportYear -le 0) { $ReportYear = (Get-Date).Year }
$deadline = [datetime]::ParseExact($Until, "yyyy-MM-dd", $null)

$logDir = Join-Path $Root "_state"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$watchLog = Join-Path $logDir ("watch_season-{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Write-Watch([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $watchLog -Value $line -Encoding utf8
}

Write-Watch ("守护启动 pid={0} root={1} interval={2}h catchup={3}d streams={4} year={5} until={6}" -f `
    $PID, $Root, $IntervalHours, $CatchUpDays, $Streams, $ReportYear, $Until)

$round = 0
while ($true) {
    $now = Get-Date
    if ($now -gt $deadline) {
        Write-Watch "已过截止日 $Until，守护正常退出"
        break
    }

    $round++
    $winSince = $now.AddDays(-$CatchUpDays).ToString("yyyy-MM-dd")
    $winUntil = $now.ToString("yyyy-MM-dd")
    Write-Watch "── 第 $round 轮开始：窗口 $winSince ~ $winUntil"

    & $Python $target run --root $Root --since $winSince --until $winUntil `
        --streams $Streams --report-year $ReportYear --workers 6 2>&1 |
        ForEach-Object {
            Add-Content -Path $watchLog -Value $_ -Encoding utf8
            Write-Host $_
        }
    Write-Watch "── 第 $round 轮结束（python exit=$LASTEXITCODE），休眠 $IntervalHours 小时"
    Start-Sleep -Seconds ($IntervalHours * 3600)
}
