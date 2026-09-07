# hub_connect.ps1 — open an SSH session to the RavenX hub from the Windows desktop.
#
# The hub answers on its TAILNET name from anywhere, which is tried first. The LAN
# path below only matters when you are on the same network as the hub and Tailscale is
# off; the hub is on DHCP there, so that path sweeps the local /24 for an open SSH port.
#
# Tailnet first is not a preference, it is the only thing that works from another city.
# The desktop moved to Mississauga on 2026-08-28 while the hub stayed in Montreal, and
# the previous ordering spent 30 seconds failing over a LAN the hub is not on.
#
# Usage:  powershell -ExecutionPolicy Bypass -File tools\hub_connect.ps1
#         (the desktop shortcut created by tools\install_hub_shortcut.ps1 does this)

[CmdletBinding()]
param(
    [string]$HubUser = 'warlock',
    [string]$HubHost,
    [string]$RemoteDir = '/srv/ravenx/repo',
    # MagicDNS name. Stable across address changes, which the DHCP address never was.
    # Always the FQDN, never the bare node name. This desktop's own Windows hostname is
    # also WARLOCK, so bare `warlock` resolves to the local machine before MagicDNS is
    # consulted -- you connect to yourself and the failure is baffling.
    #
    # Do not rename the node in the Tailscale admin console. The MagicDNS name is what
    # Tailscale Serve holds its certificate for, so a rename leaves Serve listening on
    # 443 with a certificate for a hostname that no longer exists: the port accepts, the
    # handshake fails, and the phone keeps painting a CACHED shell so the hub still looks
    # alive. Cost an hour on 2026-09-02.
    [string]$TailnetHost = 'warlock.tail41f2a1.ts.net',
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

$candidates = @($HubHost, $TailnetHost, (Get-RememberedHost), '10.0.0.213') |
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
    Write-Host 'Check, in this order:'
    Write-Host '  1. Is Tailscale running here?  tailscale status'
    Write-Host '  2. Does the dashboard load on your phone? If yes, the hub is fine and this'
    Write-Host '     desktop is the problem.'
    Write-Host '  3. If the phone cannot reach it either, the hub is likely sitting at its LUKS'
    Write-Host '     passphrase prompt after a reboot (Bug_Backlog R-020). Nothing remote fixes'
    Write-Host '     that -- someone has to type it at the keyboard.'
    Write-Host '  4. Only if you are on the same network: 5 GHz WiFi, Mullvad LAN sharing on.'
    Read-Host 'Press Enter to close'
    exit 1
}

# Only ever remember the tailnet name. A swept LAN address is correct for exactly as
# long as you stay on that network, and writing one into `Host hub` would silently break
# `ssh hub` the next time you travel -- which is the failure this script just had.
if ($target -eq $TailnetHost) {
    if ((Get-RememberedHost) -ne $TailnetHost) {
        Set-RememberedHost $TailnetHost
        Write-Host "Remembered $TailnetHost as '$Alias' in ~/.ssh/config" -ForegroundColor DarkGray
    }
} elseif ((Get-RememberedHost) -ne $TailnetHost) {
    Write-Host "Connected over the LAN; leaving '$Alias' alone so it stays portable." -ForegroundColor DarkGray
}

$dest = '{0}@{1}' -f $HubUser, $target
$Host.UI.RawUI.WindowTitle = "RavenX hub - $dest"
Write-Host "Connecting to $dest ..." -ForegroundColor Cyan
Write-Host ''

# Land in the repo instead of the home directory. -t forces a PTY (ssh won't
# allocate one when given a remote command), and `exec $SHELL -l` replaces the
# cd with a normal login shell that inherits the new working directory. If the
# directory is missing we still want a usable session, so the cd is not fatal.
#
# Quoting: a leading ~ becomes $HOME because bash does not expand a tilde inside
# quotes, and the path must stay quoted to survive spaces. Both $HOME and $SHELL
# are escaped so PowerShell leaves them for the remote shell to expand.
if ($RemoteDir -like '~/*') {
    $dirExpr = '"$HOME/' + $RemoteDir.Substring(2) + '"'
} else {
    $dirExpr = "'" + $RemoteDir + "'"
}
$remote = "cd $dirExpr 2>/dev/null || echo 'hub_connect: $RemoteDir not found, staying in home'; exec `$SHELL -l"
ssh -t $dest $remote
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Host ''
    Write-Host "ssh exited with code $code" -ForegroundColor Yellow
    Read-Host 'Press Enter to close'
}
exit $code
