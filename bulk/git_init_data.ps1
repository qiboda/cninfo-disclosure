# Initialize the cninfo dataset directory as a local git repository using Git LFS.
#
# LFS-tracked: *.pdf (96,226 files / 181 GB), *.jsonl and *.csv (machine-generated ledgers)
# Ignored:     redundant intermediate state backups (*.bak*, ~84 MB)
#
# Run detached; progress is appended to <Root>\_state\gitinit.log
param(
    [string]$Root = "C:\Users\iq112\Documents\cninfo"
)

$ErrorActionPreference = "Continue"
$log = Join-Path $Root "_state\gitinit.log"

function Say([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

Set-Location $Root
Say "START root=$Root"

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Say "step1: git init -b main"
    git init -b main 2>&1 | Out-String | ForEach-Object { Say $_ }
} else {
    Say "step1: .git already exists, skip init"
}

Say "step2: git lfs install --local"
git lfs install --local 2>&1 | Out-String | ForEach-Object { Say $_ }

Say "step3: write .gitattributes / .gitignore"
@'
*.pdf   filter=lfs diff=lfs merge=lfs -text
*.jsonl filter=lfs diff=lfs merge=lfs -text
*.csv   filter=lfs diff=lfs merge=lfs -text
'@ | Set-Content -Path (Join-Path $Root ".gitattributes") -Encoding utf8

@'
# redundant intermediate download-state snapshots (regenerable from done.jsonl)
*.bak
*.bak2
*.bak-*
'@ | Set-Content -Path (Join-Path $Root ".gitignore") -Encoding utf8

git config --local core.quotepath false
git config --local gc.auto 0

Say "step4: add metadata files"
git add -f .gitattributes .gitignore 2>&1 | Out-String | ForEach-Object { Say $_ }
git add README.md manifest.csv _state 2>&1 | Out-String | ForEach-Object { Say $_ }

Say "step5: add reports/ (LFS, large - be patient)"
git add reports 2>&1 | Out-String | ForEach-Object { Say $_ }
Say "step5 done"

Say "step6: add prospectus/ (LFS)"
git add prospectus 2>&1 | Out-String | ForEach-Object { Say $_ }
Say "step6 done"

Say "step7: staged file count"
git diff --cached --name-only 2>&1 | Measure-Object | Select-Object -ExpandProperty Count |
    ForEach-Object { Say "staged entries: $_" }

Say "step8: commit"
git -c core.safecrlf=false commit -m "data: A-share 2022-now financial reports and IPO prospectuses (96,226 PDFs, 181 GB, Git LFS)" 2>&1 |
    Out-String | ForEach-Object { Say $_ }

Say "step9: summary"
git log --oneline -1 2>&1 | ForEach-Object { Say $_ }
git count-objects -vH 2>&1 | ForEach-Object { Say $_ }
Say "DONE"
