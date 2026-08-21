# HUB_SETUP.md — 2014 MacBook Air as an always-on home hub

Goal state: lid closed, plugged into the wall, silent, reachable over SSH and Tailscale,
Bluetooth working, running Python services 24/7. Useful for RavenX Smart Ring and anything
else you throw at it later. A laptop makes a surprisingly good home server — the battery
is a built-in UPS.

Assumes Linux Mint Cinnamon (21.x or 22.x). Commands are copy-paste ready; review before running.

---

## 0. Hub facts and layout

The machine as it actually exists, so nothing has to be re-derived each session.

| | |
| --- | --- |
| User / address | `warlock@10.0.0.213` — **DHCP, can change.** Never hardcode it; Tailscale's MagicDNS name replaces it once installed. |
| Python | 3.12.3 |
| Bluetooth | Broadcom BCM20702B0, BT 4.0. Firmware loads clean. Stack initializes ~43 s into boot — services must wait for it. |
| WiFi | Must stay on **5 GHz**: one Broadcom radio is shared with Bluetooth, and 2.4 GHz degrades BLE scanning intermittently. |
| VPN | Mullvad runs here. **Local network sharing must stay enabled** or SSH and the dashboard break. |

Directory layout — **`/srv`, not `$HOME`**:

```text
/srv/ravenx/
├── repo/        # the git repo; .venv lives inside it
└── data/        # SQLite store + backups — OUTSIDE the repo on purpose

~/Projects/
├── ProjectScratchpad/   # throwaway BLE scripts; interactive use only
└── Beltest/             # session 1 Bluetooth scratch venv; historical
```

**Nothing a systemd service needs may live under `$HOME` on this machine.**
`/home/warlock` is eCryptfs-encrypted and does not exist until someone logs in
interactively, so anything a service reads from there is missing at boot and missing
again the moment you log out. That cost a P1 (Bug_Backlog R-018) and days of silently
failed syncs — see §6.

The data directory sits outside the working tree for a separate reason: a `git pull`, a
branch switch, or a `git clean` must never be able to touch the SQLite file.
`hub/config.py` encodes both paths — change them there, not in scripts.

Interactive scratch work can stay in `~/Projects`; it only runs when you are logged in
anyway, which is exactly the condition an encrypted home satisfies.

---

## 1. Keep it awake with the lid closed

Two layers control this on Mint and both must agree.

**systemd-logind:**

```bash
sudo nano /etc/systemd/logind.conf
```

Set (uncomment and edit):

```text
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
```

Apply with a reboot (safest — restarting logind live can kill your session).

**Cinnamon power manager** (overrides logind while a desktop session exists):
System Settings → Power Management → "When the lid is closed: Do nothing" (on A/C).
Also set "Suspend when inactive: Never" on A/C.

Optional, aggressive — forbid all sleep states entirely:

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

## 2. Remote administration (SSH)

```bash
sudo apt update && sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

From the desktop PC: `ssh <user>@<hub-ip>`. Once this works, the hub never needs its
own keyboard again. Key-based auth recommended:

```bash
# on desktop PC
ssh-copy-id <user>@<hub-ip>
```

**One-click launcher (Windows desktop).** `tools/hub_connect.ps1` opens the session and
copes with the hub's DHCP address moving: it tries the address remembered under `Host hub`
in `~/.ssh/config`, then `10.0.0.213`, then sweeps the local /24 for an open port 22 —
and writes whatever it finds back to `~/.ssh/config`, so plain `ssh hub` stays correct.
Run `tools/install_hub_shortcut.ps1` once to drop a "RavenX Hub" shortcut on the Desktop.
Both become obsolete once Tailscale MagicDNS gives the hub a stable name.

## 2a. Viewing any hub service from the desktop — the standing method

**Default to an SSH tunnel. Do not open a firewall port to look at something.**

**Run this on the desktop, in a terminal that is *not* already SSH'd into the hub.**
Both machines use the username `warlock` and the hub's hostname is also `WARLOCK`, so
the shell prompt is no help in telling them apart. Running it inside an existing SSH
session fails with `Could not resolve hostname hub` — the `hub` alias exists only in the
desktop's `~/.ssh/config`, and that error is the tell that you are on the wrong box.

```bash
ssh -L <local-port>:localhost:<hub-port> hub
```

Use the `hub` alias, not a literal address — §0's address is DHCP and `hub_connect.ps1`
keeps `Host hub` in `~/.ssh/config` pointed at wherever the machine actually is.

Leave that session sitting open and browse `http://localhost:<local-port>` on the
desktop. Two in constant use:

```bash
ssh -L 8000:localhost:8000 hub   # the live dashboard
ssh -L 8001:localhost:8001 hub   # a restore drill on 8001
```

Why this is the default rather than a workaround:

- **`ufw` becomes irrelevant.** The traffic arrives inside an existing SSH connection on
  port 22, which is already allowed. This sidesteps the failure in §6a entirely — the one
  where a service works perfectly on the hub and is invisible from the network with no
  error logged anywhere.
- **Nothing new is exposed.** No LAN port, no rule to remember to delete later. A rule
  added "just to check something" is exactly the kind that survives for months.
- **It keeps working while the network is in pieces.** During the Tailscale and Mullvad
  work in §5, routing is deliberately being broken and repaired. The tunnel rides SSH, so
  it stays available as a way to see the dashboard even when the tailnet does not — which
  makes it the fallback when you are trying to determine whether a change broke *routing*
  or broke *the service*.
- **A service bound to `127.0.0.1` is reachable this way and only this way**, which is
  the right binding for anything temporary.

Once Tailscale Serve is running, the tailnet URL replaces this for normal viewing. Keep
the tunnel in the toolkit anyway; it is the thing that still works when Serve does not.

## 3. Verify Bluetooth (the ring's radio path)

The 2014 Air has a Broadcom BT 4.0 chip; Mint usually supports it out of the box.

```bash
rfkill list                 # ensure bluetooth not blocked
bluetoothctl show           # controller present, Powered: yes
bluetoothctl scan on        # should list nearby BLE devices — let it run 20s
```

If no controller appears: `sudo apt install -y linux-firmware bluez` and reboot.
Later, the ring will show up in this scan as R09/R10 with a QRing-family name —
this scan is the day-one smoke test when hardware arrives.

## 4. Python environment

Mint splits `ensurepip` out of the base Python package, so the versioned `-venv`
package is required or `python3 -m venv` fails with a misleading error:

```bash
sudo apt install -y python3.12-venv python3-pip git
```

```bash
cd ~/Projects/RavenXSmartRing-IOT && python3 -m venv .venv && .venv/bin/pip install bleak fastapi "uvicorn[standard]"
```

```bash
.venv/bin/python -c "import bleak, fastapi; print('env ok')"
```

**Never move or rename the repo directory without rebuilding the venv.** Python bakes
an absolute path into the shebang of every console script in `.venv/bin`, so after a
move `pip`, `uvicorn` and friends fail with `cannot execute: required file not found`.
This bit once already: the venv was created at `~/projectring` before the directory
became `~/Projects/RavenXSmartRing-IOT`.

The trap is that it fails *selectively*. `.venv/bin/python3` is a symlink to the system
interpreter and keeps working, so `python -m hub.sync` runs fine while
`ring-dashboard.service` — which calls `.venv/bin/uvicorn` — dies at startup. You get a
working sync, a dead dashboard, and no obvious connection between them. Verify both:

```bash
.venv/bin/python -c "import bleak, fastapi, uvicorn; print('deps ok')" && .venv/bin/uvicorn --version
```

The fix is always the same, and costs nothing because `requirements.txt` pins everything:

```bash
rm -rf .venv && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

BLE smoke test (no ring needed — scans anything nearby):

```bash
python -c "
import asyncio
from bleak import BleakScanner
async def main():
    for d in await BleakScanner.discover(timeout=10):
        print(d.address, d.name)
asyncio.run(main())"
```

## 5. Tailscale (secure access from anywhere, no port forwarding)

**Read this before running anything: Mullvad is already on this hub** (Bug_Backlog
R-001). Two WireGuard clients both asserting control over routing and firewall rules is
the single most likely way to lock yourself out of a headless machine. Change one thing
at a time.

**Step 1 — prove Tailscale works with Mullvad out of the way.**

```bash
mullvad disconnect
```

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

```bash
sudo tailscale up
```

Authenticate via the printed link, install the Tailscale app on the iPhone under the
same account, and confirm the hub answers on its `100.x.x.x` address. Only once that
works should Mullvad come back.

**Step 2 — HTTPS, which the PWA needs.**

A service worker requires a secure context, so `http://100.x.x.x:8000` can never be
installed as a real home-screen app. Tailscale Serve issues a genuine certificate for
the tailnet name:

```bash
sudo tailscale serve --bg 8000
```

`tailscale serve status` prints the `https://<hub>.<tailnet>.ts.net` URL. That is the
address to open on the phone — not the raw port.

Note this is `serve`, not `funnel`. Serve is tailnet-only; nothing is exposed to the
public internet, and the privacy claim stays intact. Funnel would only be needed for the
Architecture B satellite's `/ingest`, which does not exist yet.

**Step 3 — reintroduce Mullvad and find out what breaks.**

```bash
mullvad connect
```

Then immediately re-test, in this order: SSH from the desktop, `tailscale status`, and
the dashboard from the phone. If Tailscale traffic dies, Mullvad's firewall is capturing
it — LAN sharing does not cover `100.64.0.0/10`, because the tailnet is not your LAN.

The fix is split tunnelling `tailscaled` out of Mullvad (`mullvad split-tunnel --help`
on this version), or dropping Mullvad on the hub and using Tailscale's own Mullvad exit
node instead, which puts one client in charge of routing rather than two. Whichever you
pick, record it here — this is exactly the interaction that eats a session when it
surprises someone six weeks later.

**Step 4 — install the PWA.** On the iPhone, open the `https://` URL in Safari, then
Share → Add to Home Screen. It launches without browser chrome and keeps its own icon.

## 6. Service skeleton (systemd user units)

Every long-running piece (sync service, FastAPI) runs as a systemd unit so it
survives reboots and crashes. Template — `~/.config/systemd/user/ring-dashboard.service`:

```ini
[Unit]
Description=RavenX Smart Ring dashboard (FastAPI)
After=network.target

[Service]
WorkingDirectory=%h/Projects/RavenXSmartRing-IOT
ExecStart=%h/Projects/RavenXSmartRing-IOT/.venv/bin/uvicorn hub.api:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable pattern:

```bash
systemctl --user daemon-reload
systemctl --user enable --now ring-dashboard
loginctl enable-linger $USER    # user services run without an active login
journalctl --user -u ring-dashboard -f    # live logs
```

The BLE sync service gets an identical unit later (`ring-sync.service`).

### None of the above survives a reboot on THIS machine

**`/home/warlock` is eCryptfs-encrypted and only decrypts on interactive login.**

```text
/home/.ecryptfs/warlock/.Private on /home/warlock type ecryptfs
```

At boot the systemd user manager starts exactly as `enable-linger` promises, reads an
empty `~/.config/systemd/user/`, finds no units, and reports `Startup finished in 471ms`
having started nothing. Log in over SSH and the home decrypts, so every by-hand check
afterwards works perfectly — which is precisely what makes this hard to catch.

**`loginctl enable-linger` does not fix it and is already enabled.** Nor do plain system
units in `/etc/systemd/system/`: `WorkingDirectory` and `.venv/bin/uvicorn` are
themselves inside the encrypted home, so a root-run service fails for the same reason.

Symptoms, for recognition later:

| Observation | Meaning |
| --- | --- |
| Phone gets **502** from the tailnet URL | Serve is alive; the thing it proxies to is dead. A **timeout** would mean the network instead |
| `systemctl --user list-timers` shows no ring timers | Nothing was ever started |
| `status` says `loaded; enabled` but `list-units --all` omits the unit | `status` re-read the file *after* your login decrypted the home. It was invisible at boot |
| `systemctl --user show <unit> -p WantedBy` is **empty** | The graph was built at boot from an encrypted directory |

Two consequences worth stating plainly. `ring-sync.service`'s `After=bluetooth.target`
was always inert — that is a *system* target and a user manager cannot order against it,
so the R-005 mitigation written in session 1 never applied. And **rebooting is part of
testing any unattended claim.** "It ran for a day without me" and "it survives a restart"
are different statements, and only the second one is what a 24/7 hub needs.

**This is fixed by §6b.** Everything above describes the user-unit layout that could
never work on this machine; it is kept because the failure is worth recognising on the
next box, not because it is the current design.

## 6b. The migration — user units to system units

Run this once. It moves the repo, venv and data to `/srv/ravenx` and converts all six
unit files to system units. **Do not skip step 1**: this moves the only live copy of
data that cannot be re-created.

**1. Back up, and get the copy off the hub.**

```bash
cd ~/Projects/RavenXSmartRing-IOT && .venv/bin/python -m tools.backup
```

From the **desktop**, before touching anything else:

```bash
scp hub:~/Projects/RavenXSmartRing-data/backups/*.db "C:/Users/Warlock/Desktop/Projects/RavenXSmartRing-backups/"
```

**2. Create the tree.**

```bash
sudo mkdir -p /srv/ravenx && sudo chown warlock:warlock /srv/ravenx
```

**3. Clone fresh — do not move the old directory.**

```bash
git clone https://github.com/Deorinho/Smart-Ring-IOT.git /srv/ravenx/repo
```

Cloning rather than `mv` leaves the old tree untouched as a fallback until the reboot
test passes. Disk is not the constraint here; a working rollback is.

**4. Build the venv at its final path.**

```bash
cd /srv/ravenx/repo && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**Never copy a venv.** Python bakes absolute paths into every console script in
`.venv/bin`, and the failure is selective — `.venv/bin/python3` is a symlink and keeps
working while `.venv/bin/uvicorn` dies. See §4; this has already bitten once.

```bash
.venv/bin/python -c "import bleak, fastapi, uvicorn; print('deps ok')" && .venv/bin/uvicorn --version
```

**5. Copy the data across and verify it before trusting it.**

```bash
mkdir -p /srv/ravenx/data && cp -a ~/Projects/RavenXSmartRing-data/. /srv/ravenx/data/
```

```bash
cd /srv/ravenx/repo && RAVENX_DATA_DIR=/srv/ravenx/data .venv/bin/python -m tools.restore --latest
```

`restore.py` reads the copy back through the application layer, so a pass means the
services will be able to read it — not merely that the bytes arrived.

**6. Stop and disable the old user units.**

```bash
systemctl --user disable --now ring-dashboard ring-sync.timer ring-backup.timer
rm -f ~/.config/systemd/user/ring-*.service ~/.config/systemd/user/ring-*.timer
systemctl --user daemon-reload
```

Removing the files matters. Two copies of a unit with the same name in two managers is
a debugging session nobody enjoys.

**7. Install the system units and the sudoers rule.**

```bash
sudo cp /srv/ravenx/repo/hub/systemd/ring-*.service /srv/ravenx/repo/hub/systemd/ring-*.timer /etc/systemd/system/
sudo install -m 0440 -o root -g root /srv/ravenx/repo/hub/systemd/ravenx-sudoers /etc/sudoers.d/ravenx
sudo visudo -c -f /etc/sudoers.d/ravenx
sudo systemctl daemon-reload
```

**`visudo -c` before you trust it.** A malformed sudoers file can lock you out of `sudo`
entirely, and this is a headless machine.

**8. Enable and start.**

```bash
sudo systemctl enable --now ring-dashboard ring-sync.timer ring-backup.timer
systemctl status ring-dashboard --no-pager
```

**9. Prove it before rebooting.**

```bash
curl -s localhost:8000/api/health | head -c 120
curl -s -o /dev/null -w "sync trigger: %{http_code}
" -X POST localhost:8000/api/sync
systemctl list-timers 'ring-*' --no-pager
```

`202` from the trigger means the sudoers rule works. Have the ring nearby — that starts
a real sync.

**10. The exit criterion. Reboot, and do not log in.**

```bash
sudo reboot
```

Wait two minutes, then open the dashboard **on your phone** without SSH-ing in first.
If it loads, R-018 is closed and every service on this hub survives a restart.

Then confirm from a shell:

```bash
systemctl list-timers 'ring-*' --no-pager && systemctl is-active ring-dashboard
```

**11. Only now, retire the old tree.**

```bash
mv ~/Projects/RavenXSmartRing-IOT ~/Projects/RavenXSmartRing-IOT.old
mv ~/Projects/RavenXSmartRing-data ~/Projects/RavenXSmartRing-data.old
```

Rename rather than delete, and reboot once more. If anything still points at the old
paths it will fail loudly now, while the data is still there, instead of quietly in a
month. Delete them a week later.

## 6a. The firewall will silently eat your first service

Mint ships `ufw` **active**, defaulting to deny-incoming, and installing
`openssh-server` adds an allow rule for port 22 automatically. The result is a machine
where SSH works perfectly and every service you subsequently run is invisible from the
network — with no error anywhere, because the packets are dropped rather than refused.
It presents as "the server stopped responding" in a browser.

Diagnose it in two commands. If the process is bound correctly and the port still times
out from another machine, it is the firewall:

```bash
ss -tlnp | grep 8000
```

```bash
sudo ufw status verbose
```

Scope the rule to the LAN rather than opening it to anywhere:

```bash
sudo ufw allow from 10.0.0.0/24 to any port 8000 proto tcp comment 'RavenX dashboard (LAN)'
```

**Delete this rule once Tailscale Serve is running.** Serve receives on the `tailscale0`
interface and proxies to localhost, so no inbound LAN port is required — and then the
dashboard is reachable only from your own devices instead of anything on the WiFi.

## 7. Hygiene for a 24/7 box

```bash
sudo apt install -y unattended-upgrades      # security patches apply themselves
sudo dpkg-reconfigure -plow unattended-upgrades
```

- Thermals: the 2014 Air throttles gracefully; keep the vent (rear hinge) unobstructed.
- Battery: decade-old cell + permanent A/C is fine; it degrades to a small UPS, which
  is exactly what you want.

## 7a. Backups, and the restore drill that makes them real

**Do not use `cp`.** The store runs in WAL mode, so a file copy taken while the sync
service is mid-write can capture a database whose `-wal` sidecar it no longer matches —
a copy that restores corrupt, which is worse than no copy because you believe in it.
`tools/backup.py` uses SQLite's own backup API, which copies pages under a read lock and
cannot be torn by a concurrent writer. It runs nightly at 04:00 under
`ring-backup.timer`.

Mint has no bare `python` — it is `python3`, and these run from the venv anyway, which
is what the systemd units call. Run them from the repo root:

```bash
systemctl --user list-timers ring-backup          # confirm it is actually scheduled
.venv/bin/python -m tools.backup                  # write, verify, rotate
.venv/bin/python -m tools.backup --verify-only    # re-check every existing backup
```

**Verifying a backup is not restoring it.** `backup.py` checks the file it just wrote,
in the process that wrote it. That answers "did the write succeed?" and never "could I
get my data back?" `tools/restore.py` answers the second question — it copies a backup to
a scratch directory, verifies it, then reads it back through `hub/db.py`'s own query
functions, the same ones `hub/api.py` calls:

```bash
.venv/bin/python -m tools.restore --list
.venv/bin/python -m tools.restore --latest
```

It refuses to write anywhere near the live store, so it cannot destroy the thing it is
testing. Exit status is 0 only if the copy verified *and* served the read path, which
makes it safe to schedule later. A store with a valid schema and zero rows is reported
as a **failure**, not a success — that case passes `integrity_check` cleanly and is the
one a checksum cannot catch.

Finish the drill by looking at the data with your own eyes. `restore.py` prints this
line with the real path filled in:

```bash
RAVENX_DATA_DIR=/tmp/ravenx-restore-<stamp> .venv/bin/uvicorn hub.api:app --port 8001
```

That command has no `--host`, so uvicorn binds `127.0.0.1` and the restore is reachable
only from the hub itself — deliberate, since a drill should not be exposable by accident.
View it with the tunnel from §2a, run on the **desktop**:

```bash
ssh -L 8001:localhost:8001 hub
```

Then open `http://localhost:8001` and confirm the heart-rate panel draws. Two details
that keep the drill safe: it is port **8001**, so the live dashboard on 8000 is
untouched, and `RAVENX_DATA_DIR` points at the restore directory, so nothing can write
to the real store. Stop the uvicorn with Ctrl-C when done.

If you only want a yes/no rather than a look, from a second SSH session on the hub:

```bash
curl -s localhost:8001/api/health
```

**Still your job: getting a copy off the hub.** Everything above lives on the same disk
as the original, which covers corruption and mistakes but not that disk dying. From the
desktop:

```bash
rsync -av warlock@10.0.0.213:~/Projects/RavenXSmartRing-data/backups/ ./backups/
```

## 7a-bis. The battery alert (Bug_Backlog R-009)

The ring has run itself flat twice unnoticed: 80% to 1% during the factory week, and 4%
on 2026-08-20 — the second time *after* the dashboard gained a battery indicator. An
indicator informs; it does not notify. The gap it has to cover is nobody looking at the
dashboard.

**Why this is a Shortcut and not Web Push.** Web Push genuinely works on an installed
iOS PWA, and the hub could send it — push is outbound, so a tailnet-only hub is no
obstacle. It was rejected on reliability: iOS expires push subscriptions for apps you
have not opened recently, so a warning needed once every 5.5 days would depend on a
mechanism designed to garbage-collect exactly that dormancy. Its failure mode is
silence, and you would find out by not being warned. A daily Shortcut cannot expire, and
at ~17–18%/day you cannot act on a low battery faster than the next time you pass a
charger anyway.

The hub does the thinking so the phone side stays trivial:

```bash
curl -s https://warlock.<tailnet>.ts.net/api/alert
```

```json
{"alert": true, "message": "Ring battery 22% - about 1 day left", "checked_utc": "..."}
```

It reports two conditions, not one. A flat ring and a **stopped hub** are equally
invisible, and only the first is one anybody thinks to check — R-018 ate every scheduled
sync for days and nothing said so.

**Build the automation** on the iPhone, in Shortcuts → Automation → **+** → Time of Day:

1. **09:00, Daily**, and turn **Ask Before Running** OFF
2. **Get Contents of URL** → `https://warlock.<tailnet>.ts.net/api/alert`
3. **If** → `Get Dictionary Value` `alert` → **is** → `1`
4. **Show Notification** → `Get Dictionary Value` `message`

**Verify it once, deliberately.** An alert that only fires when something is wrong gives
you no evidence it works — the same trap as an unrestored backup, which this project has
already fallen into once. Temporarily lower the bar so it must fire:

```bash
sudo sed -i 's/^BATTERY_ALERT_PERCENT = 30/BATTERY_ALERT_PERCENT = 100/' /srv/ravenx/repo/hub/config.py
sudo systemctl restart ring-dashboard
```

Run the automation by hand from Shortcuts, confirm the notification arrives, then put it
back to `30` and restart again. Do not skip this. A notification path you have never
seen deliver is a belief.

Requires Tailscale connected on the phone when it runs — which, since Mullvad came off
the phone (R-019), is now the normal state.

## 7b. Hardening pass

Threat model first — hardening without one is ritual.

**In scope:** anything else on the house WiFi, including guests and whatever firmware
runs on the IoT devices; automated scanning if a port is ever exposed by accident; a
stolen or compromised Tailscale credential; the laptop being taken while powered off; a
broken or malicious package update.

**Out of scope, deliberately:** a targeted attacker with physical access to a running
machine, or anyone who can compel the account. A 2014 MacBook Air in a house does not win
that fight, and pretending otherwise buys complexity instead of safety.

### Already correct — do not undo these

| Property | Why it matters |
| --- | --- |
| `ufw` default-deny incoming, port 22 the only allow rule | Every other service is invisible from the LAN |
| Dashboard reachable only over the tailnet (§5) | No LAN port, nothing public |
| `hub/api.py` has **no write path at all** | A bug or compromise in the reader cannot corrupt the store |
| Funnel off — `serve status` reports `(tailnet only)` | Nothing published to the internet |
| No routing role — see "deliberate non-roles" below | The box does one job |

### SSH — read this before changing anything

Disabling password authentication is the obvious hardening step and **on this machine it
can lock you out of a headless box.** `~/.ssh/authorized_keys` lives inside the
eCryptfs-encrypted home (R-018). Before you log in, that directory does not exist, so
`sshd` cannot read your key — which means password auth is currently what gets you in
after a reboot, whether or not you realised it.

Check what you actually have:

```bash
sudo sshd -T | grep -E "^(passwordauthentication|permitrootlogin|pubkeyauthentication|authorizedkeysfile)"
```

**The safe order is: move the keys out of the encrypted home first, prove it works, then
turn passwords off.** Never the reverse.

```bash
sudo mkdir -p /etc/ssh/authorized_keys
sudo cp ~/.ssh/authorized_keys /etc/ssh/authorized_keys/warlock
sudo chown root:root /etc/ssh/authorized_keys/warlock
sudo chmod 644 /etc/ssh/authorized_keys/warlock
```

```bash
sudo tee /etc/ssh/sshd_config.d/99-ravenx.conf >/dev/null <<'EOF'
AuthorizedKeysFile /etc/ssh/authorized_keys/%u .ssh/authorized_keys
PermitRootLogin no
EOF
sudo sshd -t && sudo systemctl reload ssh
```

Now **reboot and log in without touching the machine.** If a key-based login succeeds
while the home is still encrypted, the keys are genuinely outside it. Only then add
`PasswordAuthentication no` and `KbdInteractiveAuthentication no` to that same file and
reload again.

`sshd -t` validates syntax, not that your key works. **Keep a second SSH session open for
every step here**, and test from a third before closing either.

### Automatic security updates — verify, don't assume

§7 recommends `unattended-upgrades`. Installed is not the same as running:

```bash
systemctl is-active unattended-upgrades && apt-config dump APT::Periodic::Unattended-Upgrade
```

A `1` means daily. A `0`, or a missing key, means it was installed and never enabled —
which is the same class of mistake as a backup nobody has restored.

### Tailscale ACLs

By default every device on a tailnet reaches every other device on every port. With two
nodes that both belong to you, that is acceptable and not worth the complexity.

**It stops being acceptable when Architecture B arrives.** The ESP32-C3 satellite is an
embedded device running firmware you wrote, sitting in another building, and it needs
exactly one thing: POST to `/ingest`. It should never be able to reach SSH. Write the ACL
when the node is added, not after:

```jsonc
// Tailscale admin console -> Access Controls
{
  "acls": [
    { "action": "accept", "src": ["tag:satellite"], "dst": ["tag:hub:8000"] },
    { "action": "accept", "src": ["autogroup:member"], "dst": ["*:*"] }
  ]
}
```

A satellite is the most likely thing on this tailnet to be compromised — it is physically
remote, unattended, and running the least-reviewed code in the project.

### At-rest encryption: a regression you are choosing

The `/srv/ravenx` migration (R-018, session 8) moves `ring.db` **out of the encrypted
home**. That is a deliberate trade and it should be recorded as one rather than
discovered later.

What is actually lost is narrow: eCryptfs protects data when the machine is **off**. This
hub is powered on essentially always, and while it runs, the home is decrypted whenever
anyone is logged in — so the protection covered "laptop stolen while shut down" and
little else. What is gained is a system that survives reboots at all.

Full-disk encryption does not rescue this either: unattended boot needs the key available
without a human, and a key the machine can read by itself is a key an attacker with the
disk can read too. The honest position is that **this box trades at-rest encryption for
unattended operation**, and its real protection is physical — it lives in your home.

If that ever stops being acceptable, the answer is not LUKS-with-a-keyfile; it is keeping
the sensitive store on hardware that is not expected to boot unattended.

### Deliberate non-roles

Recorded so a future session does not "helpfully" add them back:

- **No IP forwarding, no exit node.** Considered 2026-08-20 to work around iOS allowing
  only one VPN (R-019) and **rejected**. It enables routing kernel-wide on a machine whose
  job is storing data, couples a phone's general browsing to the box holding health data,
  makes the Tailscale account a more valuable target, and puts sustained traffic on the
  same radio the ring sync depends on (R-003). Back out with
  `sudo tailscale up --advertise-exit-node=false`.
- **No Funnel.** Serve only. The privacy claim is the project.
- **No inbound LAN ports.** The SSH tunnel in §2a covers every "I just need to look at
  it" case without one.

## 8. Verification checklist

- [ ] Lid closed 10 minutes → still answers ping and SSH
- [ ] Survives reboot → SSH back in without touching the machine
- [ ] `bluetoothctl scan on` sees nearby BLE devices
- [ ] Python venv imports bleak + fastapi
- [ ] Tailscale: iPhone reaches the hub with WiFi off (cellular) — this is also
      the privacy-segment demo shot for the video
- [ ] **Services survive a reboot with nobody logging in** — the phone loads the
      dashboard after `sudo reboot` and no SSH session. This is the item that matters;
      "it ran unattended for a day" is a different and much weaker claim (R-018)
- [ ] `sudo sshd -T` shows pubkey auth on, root login off — and passwords off **only
      after** a cold-boot key login is proven to work (§7b: the keys must be outside the
      encrypted home first, or you lock yourself out of a headless machine)
- [ ] `unattended-upgrades` is *active*, not merely installed
- [ ] `tailscale serve status` reports `(tailnet only)`; Funnel off
- [ ] No IP forwarding, no exit node — a deliberate non-role (§7b)
- [ ] `tailscale status` shows the phone *online* before diagnosing any "dashboard is
      down" report (R-019 — the hub was healthy for two days while it looked broken)

## Beyond RavenX Smart Ring

Once this box exists it's a general-purpose home server: Syncthing node for file
sync, backup target, cron-job host, network-wide ad blocking, a place to run any
long-lived script. Everything in sections 1–2 and 5–7 is project-agnostic.
