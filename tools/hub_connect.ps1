# hub_connect.ps1 — open an SSH session to the RavenX hub from the Windows desktop.
#
# The hub is on DHCP, so its address moves. This tries the remembered address
# first, then falls back to sweeping the local /24 for an open SSH port and
# remembers whatever it finds in ~/.ssh/config under `Host hub`.
#
# Usage:  powershell -ExecutionPolicy Bypass -File tools\hub_connect.ps1
#         (the desktop shortcut created by tools\install_hub_shortcut.ps1 does this)

[CmdletBinding()]
param(
    [string]$HubUser = 'warlock',
    [string]$HubHost,
    [switch]$NoSweep
)

$ErrorActionPreference = 'Stop'
$SshConfig = Join-Path $HOME '.ssh\config'
$Alias     = 'hub'

function Test-SshPort {
    param([string]$Address, [int]$TimeoutMs = 1200)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Address, 22, $null, $null)
        if ($async.AsyncWaitHandle.WaitOne($TimeoutMs, $false) -and $client.Connected) {
            $client.EndConnect($async)
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Get-RememberedHost {
    # HostName under `Host hub` in ~/.ssh/config, if the alias exists.
    if (-not (Test-Path $SshConfig)) { return $null }
    $inBlock = $false
    foreach ($line in Get-Content $SshConfig) {
        if ($line -match '^\s*Host\s+(.+?)\s*$') {
            $inBlock = ($matches[1] -split '\s+') -contains $Alias
            continue
        }
        if ($inBlock -and $line -match '^\s*HostName\s+(\S+)') { return $matches[1] }
    }
    return $null
}

function Set-RememberedHost {
    # Rewrite (or append) the `Host hub` block so `ssh hub` keeps working too.
    param([string]$Address)

    $block = @(
        "Host $Alias"
        "  HostName $Address"
        "  User $HubUser"
    )

    $kept = @()
    if (Test-Path $SshConfig) {
        $inBlock = $false
        foreach ($line in Get-Content $SshConfig) {
            if ($line -match '^\s*Host\s+(.+?)\s*$') {
                $inBlock = ($matches[1] -split '\s+') -contains $Alias
            }
            if (-not $inBlock) { $kept += $line }
        }
    } else {
        $sshDir = Split-Path $SshConfig -Parent
        if (-not (Test-Path $sshDir)) { New-Item -ItemType Directory -Path $sshDir | Out-Null }
    }

    while ($kept.Count -gt 0 -and [string]::IsNullOrWhiteSpace($kept[-1])) {
        $kept = $kept[0..($kept.Count - 2)]
    }

    $out = @()
    if ($kept.Count -gt 0) { $out += $kept; $out += '' }
    $out += $block
    Set-Content -Path $SshConfig -Value $out -Encoding utf8
}

function Find-HubBySweep {
    # Fire non-blocking TCP connects at every host in our own /24 at once,
    # then collect whoever answered on 22.
    $local = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and
                       $_.PrefixOrigin -ne 'WellKnown' } |
        Select-Object -First 1

    if (-not $local) {
        Write-Host 'No usable local IPv4 address; cannot sweep.' -ForegroundColor Yellow
        return @()
    }

    $prefix = ($local.IPAddress -split '\.')[0..2] -join '.'
    Write-Host "Sweeping $prefix.0/24 for SSH..." -ForegroundColor DarkGray

    $pending = @()
    foreach ($n in 1..254) {
        $address = "$prefix.$n"
        $client  = New-Object System.Net.Sockets.TcpClient
        try {
            $pending += [pscustomobject]@{
                Address = $address
                Client  = $client
                Async   = $client.BeginConnect($address, 22, $null, $null)
            }
        } catch {
            $client.Close()
        }
    }

    Start-Sleep -Milliseconds 2000

    $found = @()
    foreach ($p in $pending) {
        if ($p.Client.Connected) { $found += $p.Address }
        $p.Client.Close()
    }
    return $found
}

# --- resolve an address -------------------------------------------------------

$candidates = @($HubHost, (Get-RememberedHost), '10.0.0.213') |
    Where-Object { $_ } | Select-Object -Unique

$target = $null
foreach ($c in $candidates) {
    Write-Host "Trying $c ... " -NoNewline
    if (Test-SshPort $c) {
        Write-Host 'up' -ForegroundColor Green
        $target = $c
        break
    }
    Write-Host 'no answer' -ForegroundColor DarkGray
}

if (-not $target -and -not $NoSweep) {
    $found = Find-HubBySweep | Where-Object { $_ -notin $candidates }
    if ($found.Count -eq 1) {
        $target = $found[0]
        Write-Host "Found SSH at $target" -ForegroundColor Green
    } elseif ($found.Count -gt 1) {
        Write-Host 'Several hosts answer on port 22:' -ForegroundColor Yellow
        for ($i = 0; $i -lt $found.Count; $i++) { Write-Host "  [$i] $($found[$i])" }
        $pick = Read-Host 'Which one is the hub? (number, or blank to abort)'
        if ($pick -match '^\d+$' -and [int]$pick -lt $found.Count) { $target = $found[[int]$pick] }
    }
}

if (-not $target) {
    Write-Host ''
    Write-Host 'Hub not reachable.' -ForegroundColor Red
    Write-Host 'Check: hub powered and awake, on 5 GHz WiFi, Mullvad LAN sharing still enabled.'
    Read-Host 'Press Enter to close'
    exit 1
}

if ((Get-RememberedHost) -ne $target) {
    Set-RememberedHost $target
    Write-Host "Remembered $target as '$Alias' in ~/.ssh/config" -ForegroundColor DarkGray
}

$dest = '{0}@{1}' -f $HubUser, $target
$Host.UI.RawUI.WindowTitle = "RavenX hub - $dest"
Write-Host "Connecting to $dest ..." -ForegroundColor Cyan
Write-Host ''

ssh $dest
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Host ''
    Write-Host "ssh exited with code $code" -ForegroundColor Yellow
    Read-Host 'Press Enter to close'
}
exit $code
