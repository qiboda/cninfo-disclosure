<#
.SYNOPSIS
    历史回填「业绩预告 + 业绩快报」到 by_date/{披露日期}/ 下。

.DESCRIPTION
    按**年**循环，而不是一次查 2022~2026 五年：
    `category_yjygjxz_szsh` 每年约 6,100~6,900 条 = 205~230 页，稳稳落在
    `--max-pages 250` 之内；合成一个五年区间是 1,086 页，会多次触发
    `_fill_range()` 的二分递归，白白重复翻已经翻过的页。

    为什么只跑 yjyg,yjkb 而不带上 q3,ipo：三季报与招股书的历史档已经由
    `bulk_cninfo.py` 全量抓进 `reports/` 与 `prospectus/`，`fetch_by_date.py`
    的 `load_existing()` 会把它们全部判为「已归档」跳过 —— 带上只是白翻 500 多页。

.EXAMPLE
    pwsh -File backfill_yjyg.ps1
#>
param(
    [string]$Root = "C:\Users\iq112\Documents\cninfo",
    [string]$Streams = "yjyg,yjkb",
    [int]$Workers = 10,
    [int]$From = 2022,
    [string]$Until = "2026-10-11",
    [string]$Python = "python"
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $here "fetch_by_date.py"
$untilYear = [int]$Until.Substring(0, 4)

$sw = [Diagnostics.Stopwatch]::StartNew()
$failedYears = @()
for ($y = $From; $y -le $untilYear; $y++) {
    $since = "$y-01-01"
    $end = if ($y -eq $untilYear) { $Until } else { "$y-12-31" }
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host "### $y  ($since ~ $end)   已用 $([math]::Round($sw.Elapsed.TotalMinutes,1)) 分钟"
    Write-Host ("=" * 78)
    & $Python $target run --root $Root --since $since --until $end `
        --streams $Streams --report-year $y --workers $Workers
    $code = $LASTEXITCODE
    Write-Host "### $y 结束 exit=$code"
    if ($code -ne 0) {
        # fetch_by_date 现在会用 exit=2 报告「有区间没检索到」。历史的教训：
        # 2022 年那轮 exit=0 + 候选 0 条，看起来像「这一年本来就没东西」，
        # 实际是 504 把整年 6,893 条公告吞了。所以这里必须记账并最终非零退出。
        $failedYears += $y
        Write-Host "!!! $y 有区间检索失败或下载失败（exit=$code），该年**不完整**，修好后请重跑："
        Write-Host "    pwsh -File $($MyInvocation.MyCommand.Name) -From $y -Until $end"
    }
}
Write-Host ""
if ($failedYears.Count -gt 0) {
    Write-Host "回填结束，总耗时 $([math]::Round($sw.Elapsed.TotalMinutes,1)) 分钟"
    Write-Host "⚠️ 以下年份不完整，需重跑：$($failedYears -join ', ')"
    exit 2
}
Write-Host "回填全部完成，总耗时 $([math]::Round($sw.Elapsed.TotalMinutes,1)) 分钟"
exit 0
