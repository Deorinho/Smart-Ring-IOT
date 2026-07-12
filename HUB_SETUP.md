# HUB_SETUP.md — 2014 MacBook Air as an always-on home hub

Goal state: lid closed, plugged into the wall, silent, reachable over SSH and Tailscale,
Bluetooth working, running Python services 24/7. Useful for Project Ring and anything
else you throw at it later. A laptop makes a surprisingly good home server — the battery
is a built-in UPS.

Assumes Linux Mint Cinnamon (21.x or 22.x). Commands are copy-paste ready; review before running.

---

## 1. Keep it awake with the lid closed

Two layers control this on Mint and both must agree.

**systemd-logind:**
```bash
sudo nano /etc/systemd/logind.conf
```
Set (uncomment and edit):
```
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

```bash
sudo apt install -y python3-venv python3-pip git
mkdir -p ~/projectring && cd ~/projectring
python3 -m venv .venv
source .venv/bin/activate
pip install bleak fastapi "uvicorn[standard]" pytest
python -c "import bleak, fastapi; print('env ok')"
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

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```
Authenticate in the browser link it prints. Install the Tailscale app on the iPhone
and iPad with the same account. The hub gets a stable `100.x.x.x` address and a
MagicDNS name — the dashboard URL will be `http://<hub-name>:8000` from any of
your devices, anywhere, encrypted end to end. No data touches a third-party server;
Tailscale only coordinates the connection.

## 6. Service skeleton (systemd user units)

Every long-running piece (sync service, FastAPI) runs as a systemd unit so it
survives reboots and crashes. Template — `~/.config/systemd/user/ring-dashboard.service`:
```ini
[Unit]
Description=Project Ring dashboard (FastAPI)
After=network.target

[Service]
WorkingDirectory=%h/projectring
ExecStart=%h/projectring/.venv/bin/uvicorn hub.api:app --host 0.0.0.0 --port 8000
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

## 7. Hygiene for a 24/7 box

```bash
sudo apt install -y unattended-upgrades      # security patches apply themselves
sudo dpkg-reconfigure -plow unattended-upgrades
```
- Thermals: the 2014 Air throttles gracefully; keep the vent (rear hinge) unobstructed.
- Battery: decade-old cell + permanent A/C is fine; it degrades to a small UPS, which
  is exactly what you want.
- Backups: the SQLite file is the crown jewel. A nightly cron copying it to the
  desktop PC (or anywhere) is two lines:
  ```bash
  crontab -e
  # 0 4 * * * cp ~/projectring/data/ring.db ~/projectring/backups/ring-$(date +\%F).db
  ```

## 8. Verification checklist

- [ ] Lid closed 10 minutes — still answers ping and SSH
- [ ] Survives reboot — SSH back in without touching the machine
- [ ] `bluetoothctl scan on` sees nearby BLE devices
- [ ] Python venv imports bleak + fastapi
- [ ] Tailscale: iPhone reaches the hub with WiFi off (cellular) — this is also
      the privacy-segment demo shot for the video
- [ ] Dummy systemd user service starts on boot with linger enabled

## Beyond Project Ring

Once this box exists it's a general-purpose home server: Syncthing node for file
sync, backup target, cron-job host, network-wide ad blocking, a place to run any
long-lived script. Everything in sections 1–2 and 5–7 is project-agnostic.
