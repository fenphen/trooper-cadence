# 🖨️ Home Hub

A status page for the house: **both HP printers, their scanners, and the network**, served from
the always-on PC and bookmarked on every other computer and phone.

```
http://<always-on-pc>:8080/
```

Nothing to install on the other PCs, no HP software, no cloud. The page talks to the printers with
the same protocols Windows, macOS and phones already use (IPP for printing, eSCL for scanning, HP's
built-in web API for ink levels and page counts).

## What it shows and does

**Printers & scanners**

- Finds the HP printers by itself (Bonjour/mDNS) and shows each one as a card: *Ready · Busy ·
  Sleeping · Needs attention · Not responding*, plus a plain-English reason (out of paper, cover
  open, ink low…).
- Ink/toner levels per cartridge, pages printed, serial number, firmware, paper loaded, duplex.
- **Wake**: pokes the printer on every port it listens on (IPP, web, raw print, Wake-on-LAN) and
  keeps trying for 90 seconds. A sleeping HP wakes within a few seconds. One that is switched off
  at the power button cannot be woken over the network, and the card says so.
- **Test page**: prints a one-page PDF with the printer's name, time and colour swatches.
- **Print a file**: send a PDF, JPEG, PNG or text file from any PC, with a copy count.
- **Scan**: flatbed or document feeder, colour/grey/black-and-white, 75–600 dpi, PDF or JPEG. The
  file downloads in the browser when the scan finishes. Works from any PC or phone.
- Rename printers (Upstairs / Downstairs), add one by address, link to the printer's own web page.

**Network**

- Internet up/down, latency to the router and to the outside, public (WAN) address.
- Every device on the LAN: IP, MAC, vendor, hostname, online/offline, first and last seen. Give
  devices your own names; they are remembered.
- **TP-Link Deco** (optional, experimental): your Deco units with role and signal, every client
  with the name from the Deco app, wired vs 2.4/5 GHz, live up/down speed, and the WAN details.
  Uses the Deco's local API with the admin password. See *Deco* below.

## Setting it up on the always-on Windows PC

1. Install Python 3.10 or newer from <https://www.python.org/downloads/windows/>. Tick
   **"Add python.exe to PATH"** in the installer.
2. Download this folder (`homehub/`) to the PC, e.g. `C:\HomeHub`. (On GitHub: **Code → Download
   ZIP**, unzip, keep the `homehub` folder.)
3. Right-click **`install-windows.ps1` → Run with PowerShell**. It asks for admin once and then:
   - installs the packages into a private `.venv`,
   - opens port 8080 in Windows Firewall for the home network,
   - registers a **"Home Hub"** scheduled task that starts at boot (no login needed) and restarts
     itself if it ever stops,
   - writes **`Home Hub.url`**: copy that file to any PC's desktop, or open the address in a
     browser and bookmark it. On phones use *Share → Add to Home Screen*.

   If PowerShell refuses to run scripts, open PowerShell as administrator and run
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

To just try it without installing anything permanent, double-click `run.bat` instead.

The page is then at `http://<pc-name>:8080/` from any device in the house. If the PC name does not
resolve, use its IP address (the installer prints both). Give the always-on PC a fixed IP in the
Deco app (*Device → Reserve IP*) so the shortcut never breaks.

### Deco (optional)

Settings → *TP-Link Deco*: tick enable, enter the Deco's address (usually your gateway, shown on
the Network tab, e.g. `192.168.68.1`) and the **Deco admin password** (the one the Deco app asks
for; the owner's TP-Link ID password is usually the same). *Save & test* says whether it worked.

This uses the unofficial local API the Deco app itself uses on the LAN; it is **experimental** and
was written without a Deco to test against. If it fails, the exact error is shown in Settings, so
it can be fixed. The password only lives in `config.json` on the always-on PC.

### Running it elsewhere (Pi, Linux, NAS)

```sh
cd homehub
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m homehub            # http://localhost:8080/
```
Needs `ping` and `ip` for the network scan (present on any Linux). A `systemd` unit is just
`ExecStart=/path/to/homehub/.venv/bin/python -m homehub` with `WorkingDirectory=/path/to/homehub`.

## Settings and files

| File | Purpose |
|---|---|
| `config.json` | Port, Deco credentials, subnet, intervals, manual printers, names. Edited by the Settings tab; see `config.example.json`. |
| `data/homehub.db` | Device history (SQLite). |
| `data/oui.csv` | Vendor list downloaded once from the IEEE so MAC addresses get a vendor name. Set `"oui_download": false` to skip. |

Privacy: everything runs on the LAN. The only outside requests are the one-time vendor list
download and a "what is my public IP" lookup every 10 minutes.

## For developers

```sh
python -m unittest tests.test_homehub      # protocol tests + an end-to-end run against a fake HP printer
python tests/fake_printer.py               # a pretend HP printer on ports 6631 (IPP) and 6080 (web/eSCL)
```

Layout: `homehub/ipp.py` (IPP wire format + client), `hp.py` (HP `/DevMgmt/*.xml`), `escl.py`
(scanning), `discovery.py` (mDNS), `printers.py` (state machine, wake), `network.py` (ping sweep,
ARP, SQLite history), `deco.py` (Deco API), `app.py` (FastAPI routes), `static/index.html` (the page).

API (JSON, used by the page; handy for scripts):
`GET /api/overview`, `POST /api/printers/{id}/wake|refresh|testpage`, `POST /api/printers/{id}/print`
(multipart `file`, `copies`), `POST /api/printers/{id}/scan?source=Platen|Feeder&color=RGB24|Grayscale8&resolution=300&format=pdf|jpeg`,
`GET /api/network`, `POST /api/network/scan`, `GET|PUT /api/settings`.

## Ideas for later

- Scan straight to a shared folder, or email a scan.
- Alerts (phone push or email) when ink is low, a printer goes offline, or an unknown device joins.
- Speed test history chart; per-device online timeline.
- Kasa/Tapo smart plugs: power on the printer from the page even when it is switched off at the plug.
