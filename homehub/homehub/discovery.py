"""Find printers and scanners on the LAN with mDNS / DNS-SD (Bonjour).

HP printers advertise _ipp._tcp (printing), _uscan._tcp (eSCL scanning) and
_http._tcp (their web page). We listen for a few seconds and merge what we hear
by host address.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass, field
from typing import Any

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

log = logging.getLogger(__name__)

SERVICES = ["_ipp._tcp.local.", "_ipps._tcp.local.", "_uscan._tcp.local.", "_uscans._tcp.local.",
            "_printer._tcp.local.", "_pdl-datastream._tcp.local."]


@dataclass
class Found:
    host: str                     # IP address
    hostname: str | None = None   # e.g. HP9A1B2C.local
    name: str | None = None       # the DNS-SD instance name, e.g. "HP OfficeJet Pro 9015 [9A1B2C]"
    model: str | None = None      # from the "ty" TXT record
    uuid: str | None = None
    ipp_uri: str | None = None
    ipps_uri: str | None = None
    scan_base: str | None = None  # eSCL base, e.g. http://192.168.0.20:80/eSCL
    admin_url: str | None = None
    txt: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d.pop("txt", None)
        return d


def _txt(props: dict[bytes, bytes | None]) -> dict[str, str]:
    out = {}
    for k, v in props.items():
        try:
            out[k.decode("utf-8", "replace")] = (v or b"").decode("utf-8", "replace")
        except AttributeError:
            pass
    return out


class _Listener(ServiceListener):
    def __init__(self, zc: Zeroconf):
        self.zc = zc
        self.found: dict[str, Found] = {}
        self.lock = asyncio.Lock()

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        try:
            info = zc.get_service_info(type_, name, timeout=2000)
        except Exception as e:  # noqa: BLE001
            log.debug("get_service_info failed: %s", e)
            return
        if not info:
            return
        addrs = info.parsed_addresses()
        ipv4 = [a for a in addrs if ":" not in a]
        if not ipv4:
            return
        host = ipv4[0]
        txt = _txt(info.properties or {})
        f = self.found.setdefault(host, Found(host=host))
        f.hostname = (info.server or "").rstrip(".") or f.hostname
        instance = name.replace("." + type_, "")
        f.name = f.name or instance
        f.model = txt.get("ty") or f.model
        f.uuid = txt.get("UUID") or f.uuid
        f.admin_url = txt.get("adminurl") or f.admin_url
        f.txt.update(txt)
        rp = txt.get("rp", "").lstrip("/")
        port = info.port or 0
        if type_ == "_ipp._tcp.local.":
            f.ipp_uri = f"ipp://{host}:{port}/{rp or 'ipp/print'}"
        elif type_ == "_ipps._tcp.local.":
            f.ipps_uri = f"ipps://{host}:{port}/{rp or 'ipp/print'}"
        elif type_ in ("_uscan._tcp.local.", "_uscans._tcp.local."):
            scheme = "https" if type_.startswith("_uscans") else "http"
            f.scan_base = f"{scheme}://{host}:{port}/{rp or 'eSCL'}"

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass


def discover_sync(seconds: float = 5.0) -> list[Found]:
    zc = Zeroconf()
    listener = _Listener(zc)
    browsers = [ServiceBrowser(zc, s, listener) for s in SERVICES]
    try:
        import time
        time.sleep(seconds)
    finally:
        for b in browsers:
            b.cancel()
        zc.close()
    results = list(listener.found.values())
    # Only keep things that look like a printer/scanner (have an IPP or scan endpoint)
    return [f for f in results if f.ipp_uri or f.ipps_uri or f.scan_base]


async def discover(seconds: float = 5.0) -> list[Found]:
    return await asyncio.to_thread(discover_sync, seconds)


async def probe_host(host: str) -> Found:
    """For a manually entered address: assume the standard HP paths."""
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        ip = host
    return Found(host=ip, hostname=host if host != ip else None,
                 ipp_uri=f"ipp://{ip}:631/ipp/print", scan_base=f"http://{ip}:80/eSCL",
                 admin_url=f"http://{ip}/")
