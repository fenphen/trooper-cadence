"""eSCL scanning (the AirPrint / Mopria scan protocol every modern HP MFP speaks).

  GET  /eSCL/ScannerCapabilities  what it can do
  GET  /eSCL/ScannerStatus        Idle / Processing, ADF state
  POST /eSCL/ScanJobs             start a job (201 + Location)
  GET  <job>/NextDocument         fetch each page/document (404 = done)
  DELETE <job>                    clean up
"""
from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from typing import Any

import httpx

SCAN_NS = "http://schemas.hp.com/imaging/escl/2011/05/03"
PWG_NS = "http://www.pwg.org/schemas/2010/12/sm"


class ScanError(Exception):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _texts(root: ET.Element, name: str) -> list[str]:
    return [el.text.strip() for el in root.iter() if _local(el.tag) == name and el.text and el.text.strip()]


def _first(root: ET.Element, name: str) -> str | None:
    t = _texts(root, name)
    return t[0] if t else None


def parse_capabilities(xml_bytes: bytes) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return {}
    sources = []
    for el in root.iter():
        n = _local(el.tag)
        if n == "Platen":
            sources.append({"id": "Platen", "label": "Flatbed"})
        elif n == "Adf":
            duplex = any(_local(x.tag) == "AdfDuplexInputCaps" for x in el.iter())
            sources.append({"id": "Feeder", "label": "Document feeder"})
            if duplex:
                sources.append({"id": "FeederDuplex", "label": "Feeder, both sides"})
    resolutions = sorted({int(r) for r in _texts(root, "XResolution") if r.isdigit()})
    color_modes = sorted(set(_texts(root, "ColorMode")))
    formats = sorted(set(_texts(root, "DocumentFormat") + _texts(root, "DocumentFormatExt")))
    return {
        "make_and_model": _first(root, "MakeAndModel"),
        "version": _first(root, "Version"),
        "sources": sources or [{"id": "Platen", "label": "Flatbed"}],
        "resolutions": resolutions or [75, 150, 200, 300, 600],
        "color_modes": color_modes or ["RGB24", "Grayscale8", "BlackAndWhite1"],
        "formats": formats or ["application/pdf", "image/jpeg"],
    }


def parse_status(xml_bytes: bytes) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return {}
    return {
        "state": _first(root, "State"),
        "adf_state": _first(root, "AdfState"),
    }


def build_scan_settings(source: str = "Platen", color_mode: str = "RGB24", resolution: int = 300,
                        fmt: str = "application/pdf", width_in: float = 8.5, height_in: float = 11.0,
                        version: str = "2.63") -> str:
    source_xml = {"Platen": "Platen", "Feeder": "Feeder", "FeederDuplex": "Feeder"}.get(source, "Platen")
    duplex = "<scan:Duplex>true</scan:Duplex>" if source == "FeederDuplex" else ""
    w = int(width_in * 300)
    h = int(height_in * 300)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<scan:ScanSettings xmlns:pwg="{PWG_NS}" xmlns:scan="{SCAN_NS}">'
        f"<pwg:Version>{version}</pwg:Version>"
        "<pwg:ScanRegions><pwg:ScanRegion>"
        "<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
        f"<pwg:Height>{h}</pwg:Height><pwg:Width>{w}</pwg:Width>"
        "<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset>"
        "</pwg:ScanRegion></pwg:ScanRegions>"
        f"<scan:InputSource>{source_xml}</scan:InputSource>{duplex}"
        f"<scan:ColorMode>{color_mode}</scan:ColorMode>"
        f"<scan:XResolution>{resolution}</scan:XResolution><scan:YResolution>{resolution}</scan:YResolution>"
        f"<pwg:DocumentFormat>{fmt}</pwg:DocumentFormat>"
        f"<scan:DocumentFormatExt>{fmt}</scan:DocumentFormatExt>"
        "</scan:ScanSettings>"
    )


class EsclScanner:
    def __init__(self, host: str, port: int = 80, path: str = "/eSCL", timeout: float = 8.0):
        scheme = "https" if port == 443 else "http"
        self.base = f"{scheme}://{host}:{port}{path.rstrip('/')}"
        self.timeout = timeout

    async def capabilities(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as c:
            r = await c.get(self.base + "/ScannerCapabilities")
        if r.status_code != 200:
            raise ScanError(f"scanner capabilities: HTTP {r.status_code}")
        return parse_capabilities(r.content)

    async def status(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as c:
            r = await c.get(self.base + "/ScannerStatus")
        if r.status_code != 200:
            raise ScanError(f"scanner status: HTTP {r.status_code}")
        return parse_status(r.content)

    async def scan(self, source: str = "Platen", color_mode: str = "RGB24", resolution: int = 300,
                   fmt: str = "application/pdf", max_wait: float = 180.0) -> list[bytes]:
        """Run a scan and return the documents it produced (one PDF, or one JPEG per page)."""
        body = build_scan_settings(source, color_mode, resolution, fmt)
        docs: list[bytes] = []
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as c:
            r = await c.post(self.base + "/ScanJobs", content=body,
                             headers={"Content-Type": "text/xml"})
            if r.status_code not in (200, 201):
                raise ScanError(f"scanner refused the job (HTTP {r.status_code}): {r.text[:200]}")
            location = r.headers.get("Location")
            if not location:
                raise ScanError("scanner did not return a job location")
            if location.startswith("/"):
                location = self.base.split("/eSCL")[0] + location
            job_url = location.rstrip("/")
            deadline = asyncio.get_event_loop().time() + max_wait
            try:
                while asyncio.get_event_loop().time() < deadline:
                    try:
                        r = await c.get(job_url + "/NextDocument", timeout=httpx.Timeout(60.0, connect=self.timeout))
                    except httpx.ReadTimeout:
                        continue
                    if r.status_code == 200 and r.content:
                        docs.append(r.content)
                        continue
                    if r.status_code == 404:
                        break  # no more documents
                    if r.status_code in (503, 409):
                        await asyncio.sleep(1.0)
                        continue
                    if r.status_code >= 400:
                        if docs:
                            break
                        raise ScanError(f"scan failed (HTTP {r.status_code})")
                    await asyncio.sleep(1.0)
            finally:
                try:
                    await c.delete(job_url)
                except httpx.HTTPError:
                    pass
        if not docs:
            raise ScanError("the scanner produced no pages (is something on the glass or in the feeder?)")
        return docs
