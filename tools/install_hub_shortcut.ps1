# install_hub_shortcut.ps1 — put a clickable "RavenX Hub" shortcut on the Desktop
# that runs tools\hub_connect.ps1. Run once; re-run after moving the repo.
#
#   powershell -ExecutionPolicy Bypass -File tools\install_hub_shortcut.ps1

[CmdletBinding()]
param(
    [string]$ShortcutName = 'RavenX Hub',
    [string]$Location = [Environment]::GetFolderPath('Desktop')
)

$ErrorActionPreference = 'Stop'

$script   = Join-Path $PSScriptRoot 'hub_connect.ps1'
$repoRoot = Split-Path $PSScriptRoot -Parent
$lnk      = Join-Path $Location "$ShortcutName.lnk"

if (-not (Test-Path $script)) { throw "Missing $script" }

$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($lnk)
$s.TargetPath       = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$s.Arguments        = "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$s.WorkingDirectory = $repoRoot
$s.IconLocation     = "$env:SystemRoot\System32\SHELL32.dll,18"
$s.Description      = 'SSH into the RavenX hub (2014 MacBook Air)'
$s.Save()

Write-Host "Created $lnk" -ForegroundColor Green
