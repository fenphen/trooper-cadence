"""MAC-prefix → vendor lookup.

A short built-in table covers the usual suspects on a home network. On first run
the server also downloads the official IEEE OUI list (about 3 MB, once) into the
data folder; after that every device gets a vendor name. Set "oui_download": false
in config.json to skip the download.
"""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"

# prefix → vendor; only well-known blocks
_BUILTIN = {
    "B827EB": "Raspberry Pi", "DCA632": "Raspberry Pi", "E45F01": "Raspberry Pi", "28CDC1": "Raspberry Pi",
    "D83ADD": "Raspberry Pi", "2CCF67": "Raspberry Pi",
    "001788": "Philips Hue", "ECB5FA": "Philips Hue",
    "18B430": "Nest", "641666": "Nest",
    "000E58": "Sonos", "5CAAFD": "Sonos", "347E5C": "Sonos", "48A6B8": "Sonos", "542A1B": "Sonos", "78282C": "Sonos",
    "949F3E": "Sonos", "B8E937": "Sonos", "F0F6C1": "Sonos",
    "000C29": "VMware", "005056": "VMware", "000569": "VMware",
    "525400": "QEMU/KVM virtual machine",
    "00155D": "Hyper-V virtual machine",
    "0242AC": "Docker container",
    "001132": "Synology", "9009D0": "Synology",
    "18FE34": "Espressif (ESP8266/ESP32)", "240AC4": "Espressif (ESP8266/ESP32)", "2CF432": "Espressif (ESP8266/ESP32)",
    "30AEA4": "Espressif (ESP8266/ESP32)", "3C71BF": "Espressif (ESP8266/ESP32)", "483FDA": "Espressif (ESP8266/ESP32)",
    "5CCF7F": "Espressif (ESP8266/ESP32)", "600194": "Espressif (ESP8266/ESP32)", "7CDFA1": "Espressif (ESP8266/ESP32)",
    "84F3EB": "Espressif (ESP8266/ESP32)", "A4CF12": "Espressif (ESP8266/ESP32)", "C44F33": "Espressif (ESP8266/ESP32)",
    "0C6267": "Roku", "B83E59": "Roku", "CC6DA0": "Roku", "D83134": "Roku", "DC3A5E": "Roku",
    "001D0F": "TP-Link", "14CC20": "TP-Link", "50C7BF": "TP-Link", "5C628B": "TP-Link", "60E327": "TP-Link",
    "6C5AB0": "TP-Link", "98DAC4": "TP-Link", "A42BB0": "TP-Link", "B0BE76": "TP-Link", "C006C3": "TP-Link",
    "C46E1F": "TP-Link", "D80D17": "TP-Link", "E848B8": "TP-Link", "EC086B": "TP-Link", "F4F26D": "TP-Link",
    "30DE4B": "TP-Link", "3460F9": "TP-Link", "482254": "TP-Link", "5CE931": "TP-Link", "9C5322": "TP-Link",
    "0CEEE6": "Amazon", "10AE60": "Amazon", "40B4CD": "Amazon", "44650D": "Amazon", "4CEFC0": "Amazon",
    "50DCE7": "Amazon", "50F5DA": "Amazon", "689A87": "Amazon", "74C246": "Amazon", "7CD566": "Amazon",
    "84D6D0": "Amazon", "8871E5": "Amazon", "A002DC": "Amazon", "AC63BE": "Amazon", "B47C9C": "Amazon",
    "F0272D": "Amazon", "FCA183": "Amazon",
    "001A11": "Google", "3C5AB4": "Google", "94EB2C": "Google", "A47733": "Google",
    "F4F5D8": "Google", "F4F5E8": "Google", "6CADF8": "Google", "1CF29A": "Google",
    "001BA9": "Brother", "008077": "Brother", "3C2AF4": "Brother",
    "0026AB": "Epson", "64EB8C": "Epson", "A4EE57": "Epson",
    "000085": "Canon", "2C9EFC": "Canon", "60128B": "Canon",
    "001E0B": "HP", "002264": "HP", "0025B3": "HP", "1062E5": "HP", "18A905": "HP", "1CC1DE": "HP",
    "2C27D7": "HP", "2C41A1": "HP", "2C768A": "HP", "308D99": "HP", "3464A9": "HP", "38EAA7": "HP",
    "3C4A92": "HP", "3CD92B": "HP", "40B034": "HP", "443192": "HP", "6CC217": "HP", "80CE62": "HP",
    "842B2B": "HP", "9457A5": "HP", "98E7F4": "HP", "A08CFD": "HP", "A0B3CC": "HP", "A0D3C1": "HP",
    "A45D36": "HP", "B499BA": "HP", "B4B52F": "HP", "C8CBB8": "HP", "D0BF9C": "HP", "D48564": "HP",
    "D4C9EF": "HP", "DC4A3E": "HP", "E4E749": "HP", "EC8EB5": "HP", "EC9A74": "HP", "F0921C": "HP",
    "F4CE46": "HP", "FC15B4": "HP",
}

_table: dict[str, str] = dict(_BUILTIN)
_loaded_file: Path | None = None


def _norm(mac: str) -> str:
    return mac.replace(":", "").replace("-", "").replace(".", "").upper()[:6]


def vendor_for(mac: str | None) -> str | None:
    if not mac:
        return None
    return _table.get(_norm(mac))


def load_file(path: Path) -> int:
    """Load an IEEE oui.csv (Registry,Assignment,Organization Name,Organization Address)."""
    global _loaded_file
    n = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 3 and len(row[1]) == 6 and row[0] != "Registry":
                    _table.setdefault(row[1].upper(), _clean(row[2]))
                    n += 1
    except OSError as e:
        log.warning("could not read %s: %s", path, e)
        return 0
    _loaded_file = path
    return n


def _clean(name: str) -> str:
    name = name.strip()
    for suffix in (", Inc.", " Inc.", ", Ltd.", " Ltd.", " Co., Ltd.", " Co.,Ltd.", " Corporation", " Corp.", " LLC", " GmbH", ", Inc", " Inc", " Limited", " Technologies"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].rstrip(",. ")
    aliases = {"Hewlett Packard": "HP", "HP Inc.": "HP", "Hewlett Packard Enterprise": "HPE",
               "TP-LINK TECHNOLOGIES CO.,LTD.": "TP-Link", "Tp-Link Technologies": "TP-Link",
               "Samsung Electronics": "Samsung", "SAMSUNG ELECTRO-MECHANICS(THAILAND)": "Samsung",
               "Apple": "Apple", "Amazon": "Amazon", "Intel Corporate": "Intel", "Microsoft": "Microsoft",
               "Google": "Google", "Sonos": "Sonos", "Dell": "Dell", "LENOVO": "Lenovo", "Lenovo": "Lenovo"}
    for k, v in aliases.items():
        if name.lower().startswith(k.lower()):
            return v
    return name


async def ensure_downloaded(data_dir: Path, enabled: bool = True) -> None:
    path = data_dir / "oui.csv"
    if path.exists() and path.stat().st_size > 100_000:
        n = load_file(path)
        log.info("vendor table: %d prefixes from %s", n, path)
        return
    if not enabled:
        return
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as c:
            r = await c.get(OUI_URL, headers={"User-Agent": "HomeHub/0.1"})
        if r.status_code == 200 and b"Registry" in r.content[:200]:
            data_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            n = load_file(path)
            log.info("vendor table downloaded: %d prefixes", n)
        else:
            log.warning("vendor table download failed: HTTP %s", r.status_code)
    except httpx.HTTPError as e:
        log.warning("vendor table download failed: %s (using the small built-in table)", e)
