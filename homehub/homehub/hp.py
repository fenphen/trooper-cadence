"""HP's built-in web status API (the same XML the printer's own web page reads).

Every network HP printer from the last ~12 years answers these on port 80:
  /DevMgmt/ProductStatusDyn.xml      status category, alerts
  /DevMgmt/ConsumableConfigDyn.xml   ink / toner levels per cartridge
  /DevMgmt/ProductConfigDyn.xml      model, serial, product number
  /DevMgmt/ProductUsageDyn.xml       page counters
  /DevMgmt/NetAppsDyn.xml, /DevMgmt/IoConfigDyn.xml  (network bits, unused)
The dashboard uses IPP as the primary source and this as a richer second opinion.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx

STATUS_LABELS = {
    "ready": "Ready",
    "processing": "Printing",
    "initializing": "Starting up",
    "inPowerSave": "Sleeping",
    "powerSave": "Sleeping",
    "sleep": "Sleeping",
    "closeDoorOrCover": "Door or cover open",
    "trayEmptyOrOpen": "Out of paper",
    "inkLow": "Ink low",
    "tonerLow": "Toner low",
    "inkVeryLow": "Ink very low",
    "cartridgeMissing": "Cartridge missing",
    "jamInPrinter": "Paper jam",
    "scannerError": "Scanner error",
    "scanProcessing": "Scanning",
    "copyProcessing": "Copying",
    "shuttingDown": "Shutting down",
    "cancelJob": "Cancelling",
    "offline": "Offline",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter(root: ET.Element, name: str):
    for el in root.iter():
        if _local(el.tag) == name:
            yield el


def _text(root: ET.Element, name: str) -> str | None:
    for el in _iter(root, name):
        if el.text and el.text.strip():
            return el.text.strip()
    return None


def _parse(xml_bytes: bytes) -> ET.Element | None:
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None


def parse_status(xml_bytes: bytes) -> dict[str, Any]:
    root = _parse(xml_bytes)
    if root is None:
        return {}
    categories = [el.text.strip() for el in _iter(root, "StatusCategory") if el.text]
    alerts = []
    for a in _iter(root, "Alert"):
        alerts.append({
            "id": _text(a, "AlertID") or _text(a, "ProductStatusAlertID"),
            "severity": _text(a, "Severity"),
            "category": _text(a, "AlertCategory"),
        })
    primary = categories[0] if categories else None
    return {
        "categories": categories,
        "label": STATUS_LABELS.get(primary, primary) if primary else None,
        "sleeping": any(c in ("inPowerSave", "powerSave", "sleep") for c in categories),
        "alerts": alerts,
    }


def parse_consumables(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = _parse(xml_bytes)
    if root is None:
        return []
    out = []
    for c in _iter(root, "ConsumableInfo"):
        label = _text(c, "ConsumableLabelCode") or _text(c, "MarkerColor") or "?"
        level = _text(c, "ConsumablePercentageLevelRemaining")
        try:
            level_val: int | None = int(level) if level is not None else None
        except ValueError:
            level_val = None
        out.append({
            "label": label,
            "color": _text(c, "MarkerColor"),
            "type": _text(c, "ConsumableTypeEnum"),
            "level": level_val,
            "state": _text(c, "ConsumableLifeState") or _text(c, "ConsumableState"),
            "selectibility": _text(c, "ConsumableSelectibilityNumber"),
            "pages_remaining": _text(c, "EstimatedPagesRemaining"),
        })
    return out


def parse_config(xml_bytes: bytes) -> dict[str, Any]:
    root = _parse(xml_bytes)
    if root is None:
        return {}
    return {
        "make_and_model": _text(root, "MakeAndModel"),
        "serial": _text(root, "SerialNumber"),
        "product_number": _text(root, "ProductNumber"),
        "firmware": _text(root, "Revision") or _text(root, "FirmwareRevision"),
        "device_name": _text(root, "DeviceDescription") or _text(root, "HostName"),
    }


def parse_usage(xml_bytes: bytes) -> dict[str, Any]:
    root = _parse(xml_bytes)
    if root is None:
        return {}
    total = _text(root, "TotalImpressions")
    out: dict[str, Any] = {}
    if total and total.isdigit():
        out["total_pages"] = int(total)
    for sub in _iter(root, "PrinterSubunit"):
        for k, name in (("mono_pages", "MonochromeImpressions"), ("color_pages", "ColorImpressions"),
                        ("jams", "JamEvents"), ("mispicks", "MispickEvents")):
            v = _text(sub, name)
            if v and v.isdigit():
                out[k] = int(v)
        break
    scanner = next(iter(_iter(root, "ScannerEngineSubunit")), None)
    if scanner is not None:
        v = _text(scanner, "ScanImages")
        if v and v.isdigit():
            out["scans"] = int(v)
    return out


class HpWebApi:
    def __init__(self, host: str, timeout: float = 5.0):
        self.base = f"http://{host}"
        self.timeout = timeout

    async def _get(self, client: httpx.AsyncClient, path: str) -> bytes | None:
        try:
            r = await client.get(self.base + path)
            if r.status_code == 200 and r.content.strip().startswith(b"<"):
                return r.content
        except httpx.HTTPError:
            pass
        return None

    async def fetch(self) -> dict[str, Any]:
        """Fetch everything we can. Missing endpoints are simply absent."""
        out: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            status = await self._get(client, "/DevMgmt/ProductStatusDyn.xml")
            if status is None:
                return out  # not an HP web API (or printer asleep too deeply)
            out["status"] = parse_status(status)
            cons = await self._get(client, "/DevMgmt/ConsumableConfigDyn.xml")
            if cons:
                out["consumables"] = parse_consumables(cons)
            cfg = await self._get(client, "/DevMgmt/ProductConfigDyn.xml")
            if cfg:
                out["config"] = parse_config(cfg)
            usage = await self._get(client, "/DevMgmt/ProductUsageDyn.xml")
            if usage:
                out["usage"] = parse_usage(usage)
        return out
