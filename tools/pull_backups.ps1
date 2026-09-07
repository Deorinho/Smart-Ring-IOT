# pull_backups.ps1 - copy the hub's backups to this desktop, then prove one restores.
#
# Bug_Backlog R-016. `tools/backup.py` writes verified, rotated copies on the hub, and
# every one of them lives on the same decade-old SSD as the original. That was a P3 when
# the hub was in the next room. The desktop moved to Mississauga on 2026-08-28 and the
# hub stayed in Montreal, on a LUKS-encrypted disk nobody can unlock remotely (R-020) --
# so "the only copies are on that machine" became the whole risk rather than a footnote.
#
# The pull belongs here, not on the hub: the hub has no credentials for this machine and
# cannot push (R-013), and a puller that runs where the copies land is one that fails
# loudly on the machine you are actually sitting at.
#
#     powershell -ExecutionPolicy Bypass -File tools\pull_backups.ps1
#     powershell -ExecutionPolicy Bypass -File tools\pull_backups.ps1 -SkipVerify
#
# Register it nightly (run once, from the repo root):
#
#     schtasks /create /tn "RavenX backup pull" /sc daily /st 05:30 ^
#       /tr "powershell -ExecutionPolicy Bypass -File %CD%\tools\pull_backups.ps1"
#
# 05:30 local, comfortably after the hub's own 04:00 backup timer has written the night's
# copy. Requires Tailscale up here and Mullvad NOT enforcing lockdown -- see R-023; on
# Windows the two do not coexist without split tunnelling.

[CmdletBinding()]
param(
    [string]$HubHost   = 'warlock.tail41f2a1.ts.net',
    [string]$HubUser   = 'warlock',
    [string]$RemoteDir = '/srv/ravenx/data/backups',
    # Outside the repo, deliberately: a git clean or branch switch must never be able to
    # reach the only off-site copy of the data.
    #
    # This MIRRORS THE HUB'S LAYOUT -- a data directory with a `backups` subdirectory --
    # because tools/restore.py derives BACKUP_DIR as DATA_DIR/backups. Pointing
    # RAVENX_DATA_DIR straight at a flat folder of .db files makes it search
    # <folder>/backups and find nothing, which is a confusing way to fail.
    [string]$MirrorRoot = "$HOME\Desktop\Projects\RavenXSmartRing-backups",
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$LocalDir = Join-Path $MirrorRoot 'backups'
$LogFile  = Join-Path $MirrorRoot 'pull.log'

function Write-Log {
    param([string]$Message, [string]$Colour = 'Gray')
    $stamp = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss')
    $line  = "$stamp  $Message"
    Write-Host $line -ForegroundColor $Colour
    # A scheduled task has no console. The log is the only place a 3am failure can
    # announce itself, which is the entire point of R-016.
    if (Test-Path $MirrorRoot) { Add-Content -Path $LogFile -Value $line -Encoding utf8 }
}

if (-not (Test-Path $LocalDir)) { New-Item -ItemType Directory -Path $LocalDir -Force | Out-Null }

# ${HubHost} braced: a bare $HubHost followed by ":" parses as a drive-qualified
# variable and is a syntax error, not a runtime one.
Write-Log "pull starting from $HubUser@${HubHost}:$RemoteDir"

# --- reachability -------------------------------------------------------------
# Checked separately so "the hub is unreachable" and "the copy failed" are different
# messages. They have different causes and different fixes.
$reach = & ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no `
    "$HubUser@$HubHost" "ls -1 $RemoteDir/*.db 2>/dev/null | wc -l" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Log "UNREACHABLE: $reach" 'Red'
    Write-Log "check: Tailscale running here, Mullvad fully quit (R-023), hub past its LUKS prompt (R-020)" 'Yellow'
    exit 1
}

$remoteCount = 0
[int]::TryParse(($reach | Select-Object -Last 1).ToString().Trim(), [ref]$remoteCount) | Out-Null
Write-Log "hub holds $remoteCount backup file(s)"
if ($remoteCount -eq 0) {
    Write-Log "hub has no backups - has ring-backup.timer ever fired? systemctl list-timers ring-backup" 'Yellow'
    exit 1
}

# --- copy ---------------------------------------------------------------------
# scp rather than rsync: rsync is not present on Windows by default, and the whole set
# is ~14 files of ~100 KB. Re-copying everything nightly costs nothing and avoids an
# incremental scheme that could silently skip the file that mattered.
$before = (Get-ChildItem -Path $LocalDir -Filter 'ring-*.db' -ErrorAction SilentlyContinue).Count
& scp -q -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no `
    "$HubUser@${HubHost}:$RemoteDir/*.db" $LocalDir
if ($LASTEXITCODE -ne 0) {
    Write-Log "COPY FAILED (scp exit $LASTEXITCODE)" 'Red'
    exit 1
}

$local = Get-ChildItem -Path $LocalDir -Filter 'ring-*.db' | Sort-Object Name
$newest = $local | Select-Object -Last 1
$kb = [math]::Round($newest.Length / 1KB)
Write-Log "copied: $($local.Count) file(s) local (was $before). newest $($newest.Name), $kb KB" 'Green'

if ($local.Count -lt $remoteCount) {
    Write-Log "WARNING: hub had $remoteCount, only $($local.Count) here - copy incomplete" 'Yellow'
}

# --- prove it restores --------------------------------------------------------
# Copying is not the same as having a backup. R-004 was closed only when a backup was
# actually restored and looked at, and a nightly pull that never re-checks would let the
# belief decay right back. restore.py reads the copy through hub/db.py's own query
# functions, so a pass means the application can read it -- not that bytes arrived.
if ($SkipVerify) {
    Write-Log "verification skipped (-SkipVerify)"
    exit 0
}

$python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Log "no venv at $python - copied but NOT verified" 'Yellow'
    exit 0
}

$scratch = Join-Path $env:TEMP ("ravenx-verify-" + (Get-Date).ToString('yyyyMMddHHmmss'))
$env:RAVENX_DATA_DIR = $MirrorRoot
Push-Location $RepoRoot
try {
    $out = & $python -m tools.restore --latest --into $scratch 2>&1
    $ok = ($LASTEXITCODE -eq 0)
} finally {
    Pop-Location
    Remove-Item -Recurse -Force $scratch -ErrorAction SilentlyContinue
}

foreach ($line in $out) { Write-Log "  $line" }
if ($ok) {
    Write-Log "VERIFIED - newest backup restores and serves the read path" 'Green'
    exit 0
}

Write-Log "VERIFICATION FAILED - the copy is not a usable store" 'Red'
exit 1
