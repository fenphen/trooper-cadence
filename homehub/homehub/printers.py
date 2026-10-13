"""Keeps the list of printers and their latest status; wakes them on request."""
from __future__ import annotations

import asyncio
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import discovery, hp
from .config import Config
from .escl import EsclScanner
from .ipp import IppClient, IppError, summarize_printer
from .network import read_arp_table

log = logging.getLogger(__name__)

REASON_TEXT = {
    "media-empty": "Out of paper", "media-needed": "Needs paper", "media-jam": "Paper jam",
    "media-low": "Paper running low", "cover-open": "Cover open", "door-open": "Door open",
    "input-tray-missing": "Paper tray missing", "output-area-full": "Output tray full",
    "marker-supply-low": "Ink or toner low", "marker-supply-empty": "Ink or toner empty",
    "toner-low": "Toner low", "toner-empty": "Toner empty", "marker-waste-almost-full": "Waste ink tank almost full",
    "marker-waste-full": "Waste ink tank full", "paused": "Paused", "shutdown": "Shutting down",
    "spool-area-full": "Memory full", "stopped-partly": "Partly stopped", "moving-to-paused": "Pausing",
    "connecting-to-device": "Connecting", "timed-out": "Timed out", "other": "Printer reports a problem",
    "cups-missing-filter": "Driver problem", "offline-report": "Printer reports offline",
}


def reason_text(reason: str) -> str:
    base = reason
    for suffix in ("-error", "-warning", "-report"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return REASON_TEXT.get(base, base.replace("-", " ").capitalize())


ATTENTION_REASONS = ("media-empty", "media-jam", "media-needed", "cover-open", "door-open", "input-tray-missing",
                     "marker-supply-empty", "marker-supply-low", "toner-empty", "toner-low", "spool-area-full",
                     "stopped-partly", "stopping", "paused", "shutdown", "other")


@dataclass
class Printer:
    id: str
    host: str
    name: str
    model: str | None = None
    hostname: str | None = None
    uuid: str | None = None
    ipp_uri: str | None = None
    scan_base: str | None = None
    admin_url: str | None = None
    manual: bool = False
    mac: str | None = None
    # live
    state: str = "unknown"          # ready | printing | sleeping | attention | offline | waking | unknown
    summary: str = ""
    ipp: dict[str, Any] = field(default_factory=dict)
    web: dict[str, Any] = field(default_factory=dict)
    supplies: list[dict[str, Any]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    last_ok: float | None = None
    last_poll: float | None = None
    last_error: str | None = None
    wake: dict[str, Any] | None = None
    scanner: dict[str, Any] | None = None

    def view(self) -> dict[str, Any]:
        return {
            "id": self.id, "host": self.host, "name": self.name, "model": self.model,
            "hostname": self.hostname, "uuid": self.uuid, "ipp_uri": self.ipp_uri, "scan_base": self.scan_base,
            "admin_url": self.admin_url or f"http://{self.host}/", "manual": self.manual, "mac": self.mac,
            "state": self.state, "summary": self.summary, "supplies": self.supplies, "messages": self.messages,
            "last_ok": self.last_ok, "last_poll": self.last_poll, "last_error": self.last_error, "wake": self.wake,
            "can_scan": bool(self.scan_base), "scanner": self.scanner,
            "details": {
                "firmware": self.ipp.get("firmware") or (self.web.get("config") or {}).get("firmware"),
                "serial": (self.web.get("config") or {}).get("serial"),
                "product_number": (self.web.get("config") or {}).get("product_number"),
                "pages": self.web.get("usage") or {},
                "media_ready": self.ipp.get("media_ready", []),
                "sides": self.ipp.get("sides", []),
                "color_modes": self.ipp.get("color_modes", []),
                "queued_jobs": self.ipp.get("queued_jobs"),
                "up_time_seconds": self.ipp.get("up_time_seconds"),
                "location": self.ipp.get("location"),
            },
        }


def _printer_id(found: discovery.Found) -> str:
    if found.uuid:
        return "uuid-" + re.sub(r"[^a-z0-9]", "", found.uuid.lower())[:16]
    if found.hostname:
        return "host-" + re.sub(r"[^a-z0-9]", "", found.hostname.lower())[:32]
    return "ip-" + found.host.replace(".", "-")


class PrinterManager:
    def __init__(self, config: Config):
        self.config = config
        self.printers: dict[str, Printer] = {}
        self._tasks: list[asyncio.Task] = []
        self._wake_tasks: dict[str, asyncio.Task] = {}
        self.last_discovery: float | None = None
        self.discovering = False

    # ----- lifecycle
    async def start(self) -> None:
        for entry in self.config.get("printers", default=[]) or []:
            await self.add_manual(entry.get("host"), entry.get("name"), save=False)
        self._tasks.append(asyncio.create_task(self._discovery_loop()))
        self._tasks.append(asyncio.create_task(self._poll_loop()))

    async def stop(self) -> None:
        for t in self._tasks + list(self._wake_tasks.values()):
            t.cancel()

    # ----- discovery
    async def discover(self, seconds: float = 5.0) -> int:
        if self.discovering:
            return 0
        self.discovering = True
        try:
            found = await discovery.discover(seconds)
        except Exception as e:  # noqa: BLE001
            log.warning("mDNS discovery failed: %s", e)
            found = []
        finally:
            self.discovering = False
        self.last_discovery = time.time()
        names = self.config.get("printer_names", default={}) or {}
        new = 0
        for f in found:
            pid = _printer_id(f)
            existing = self.printers.get(pid) or next((p for p in self.printers.values() if p.host == f.host), None)
            if existing:
                existing.model = f.model or existing.model
                existing.hostname = f.hostname or existing.hostname
                existing.uuid = f.uuid or existing.uuid
                existing.ipp_uri = f.ipp_uri or f.ipps_uri or existing.ipp_uri
                existing.scan_base = f.scan_base or existing.scan_base
                existing.admin_url = f.admin_url or existing.admin_url
                existing.host = f.host
                continue
            p = Printer(id=pid, host=f.host, name=names.get(pid) or f.model or f.name or f.host,
                        model=f.model, hostname=f.hostname, uuid=f.uuid, ipp_uri=f.ipp_uri or f.ipps_uri,
                        scan_base=f.scan_base, admin_url=f.admin_url)
            self.printers[pid] = p
            new += 1
            log.info("found printer %s (%s) at %s", p.name, p.model, p.host)
        self._refresh_macs()
        if new:
            asyncio.create_task(self.poll_all())
        return new

    async def add_manual(self, host: str | None, name: str | None, save: bool = True) -> Printer | None:
        if not host:
            return None
        f = await discovery.probe_host(host.strip())
        pid = "manual-" + re.sub(r"[^a-z0-9]", "-", host.strip().lower())
        p = self.printers.get(pid)
        if p is None:
            p = Printer(id=pid, host=f.host, name=name or host, hostname=f.hostname, ipp_uri=f.ipp_uri,
                        scan_base=f.scan_base, admin_url=f.admin_url, manual=True)
            self.printers[pid] = p
        if name:
            p.name = name
        if save:
            entries = [e for e in (self.config.get("printers", default=[]) or []) if e.get("host") != host]
            entries.append({"host": host, "name": p.name})
            self.config.set(entries, "printers")
            asyncio.create_task(self.poll(p))
        return p

    def remove(self, pid: str) -> bool:
        p = self.printers.pop(pid, None)
        if not p:
            return False
        if p.manual:
            entries = [e for e in (self.config.get("printers", default=[]) or []) if e.get("host") != p.host]
            self.config.set(entries, "printers")
        return True

    def rename(self, pid: str, name: str) -> Printer | None:
        p = self.printers.get(pid)
        if not p:
            return None
        p.name = name.strip() or p.model or p.host
        names = dict(self.config.get("printer_names", default={}) or {})
        names[pid] = p.name
        self.config.set(names, "printer_names")
        if p.manual:
            entries = self.config.get("printers", default=[]) or []
            for e in entries:
                if e.get("host") == p.host:
                    e["name"] = p.name
            self.config.set(entries, "printers")
        return p

    def _refresh_macs(self) -> None:
        try:
            arp = read_arp_table()
        except Exception:  # noqa: BLE001
            return
        for p in self.printers.values():
            p.mac = arp.get(p.host) or p.mac

    async def _discovery_loop(self) -> None:
        await self.discover(6.0)
        await self.poll_all()
        while True:
            await asyncio.sleep(max(60, int(self.config.get("discovery_minutes", default=10) or 10) * 60))
            await self.discover(5.0)

    # ----- polling
    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(max(10, int(self.config.get("poll_seconds", default=30) or 30)))
            await self.poll_all()

    async def poll_all(self) -> None:
        await asyncio.gather(*(self.poll(p) for p in list(self.printers.values())), return_exceptions=True)
        self._refresh_macs()

    async def poll(self, p: Printer, timeout: float = 5.0) -> bool:
        """Ask the printer how it is. Returns True if it answered at all."""
        p.last_poll = time.time()
        ipp_ok = False
        err: str | None = None
        if p.ipp_uri:
            try:
                res = await IppClient(p.ipp_uri, timeout=timeout).get_printer_attributes()
                if res.ok or res.printer:
                    p.ipp = summarize_printer(res.printer)
                    ipp_ok = True
                else:
                    err = f"IPP: {res.status_message}"
            except (IppError, httpx.HTTPError, OSError, ValueError) as e:
                err = f"IPP: {e.__class__.__name__}: {e}"
        web: dict[str, Any] = {}
        try:
            web = await hp.HpWebApi(p.host, timeout=timeout).fetch()
        except Exception as e:  # noqa: BLE001
            log.debug("hp web api %s: %s", p.host, e)
        if web:
            p.web = web
            cfg = web.get("config") or {}
            if cfg.get("make_and_model") and not p.model:
                p.model = cfg["make_and_model"]
        if ipp_ok and p.ipp.get("make_and_model"):
            p.model = p.model or p.ipp["make_and_model"]
        answered = ipp_ok or bool(web)
        if answered:
            p.last_ok = time.time()
            p.last_error = None
        else:
            p.last_error = err or "no answer"
        self._derive_state(p, answered)
        return answered

    def _derive_state(self, p: Printer, answered: bool) -> None:
        if p.wake and p.wake.get("active"):
            p.state = "waking"
        msgs: list[str] = []
        if not answered:
            p.state = "offline" if not (p.wake and p.wake.get("active")) else "waking"
            p.summary = "Not answering. It may be asleep or switched off."
            p.supplies = p.supplies  # keep the last known levels
            p.messages = []
            return
        web_status = (p.web or {}).get("status") or {}
        ipp = p.ipp or {}
        reasons = ipp.get("state_reasons") or []
        bad = [r for r in reasons if any(r.startswith(a) for a in ATTENTION_REASONS) or r.endswith("-error")]
        warn = [r for r in reasons if r.endswith("-warning") and r not in bad]
        for r in bad + warn:
            t = reason_text(r)
            if t not in msgs:
                msgs.append(t)
        for a in ipp.get("alerts") or []:
            if a and a not in msgs:
                msgs.append(a)
        if ipp.get("state_message") and ipp["state_message"] not in msgs:
            msgs.append(ipp["state_message"])
        label = web_status.get("label")
        if ipp.get("state") == "processing" or label in ("Printing", "Scanning", "Copying"):
            p.state = "printing"
            p.summary = label if label in ("Scanning", "Copying") else "Printing"
        elif ipp.get("state") == "stopped" or bad or (label and label not in ("Ready", "Sleeping", "Starting up")):
            p.state = "attention"
            p.summary = label if label and label not in ("Ready", "Sleeping") else (msgs[0] if msgs else "Needs attention")
        elif web_status.get("sleeping"):
            p.state = "sleeping"
            p.summary = "Sleeping (answers the network; wakes on the first print)"
        else:
            p.state = "ready"
            p.summary = "Ready"
            if ipp.get("accepting_jobs") is False:
                p.state = "attention"
                p.summary = "Not accepting jobs"
        if p.wake and p.wake.get("active"):
            p.state = "waking"
        p.messages = [m for m in msgs if m != p.summary]
        # supplies: HP's own numbers first, IPP markers otherwise
        cons = (p.web or {}).get("consumables") or []
        if cons:
            p.supplies = [{
                "name": _supply_name(c["label"], c.get("color"), c.get("type")),
                "level": c.get("level"), "color": _css_color(c["label"], c.get("color")),
                "type": c.get("type"), "state": c.get("state"), "pages_remaining": c.get("pages_remaining"),
            } for c in cons]
        elif ipp.get("supplies"):
            p.supplies = [{
                "name": s["name"], "level": s["level"], "color": _css_color(s["name"], s.get("color")),
                "type": s.get("type"), "state": None, "pages_remaining": None,
            } for s in ipp["supplies"]]

    # ----- wake
    def start_wake(self, p: Printer, max_seconds: int = 90) -> None:
        t = self._wake_tasks.get(p.id)
        if t and not t.done():
            return
        p.wake = {"active": True, "started": time.time(), "attempts": 0, "result": None, "max_seconds": max_seconds}
        p.state = "waking"
        self._wake_tasks[p.id] = asyncio.create_task(self._wake(p, max_seconds))

    async def _wake(self, p: Printer, max_seconds: int) -> None:
        deadline = time.time() + max_seconds
        self._send_wol(p)
        while time.time() < deadline:
            assert p.wake is not None
            p.wake["attempts"] += 1
            # Poke every door at once: IPP on 631, the web page on 80, and a WoL packet.
            await asyncio.gather(self._poke_http(p.host), self._poke_tcp(p.host, 9100), return_exceptions=True)
            answered = await self.poll(p, timeout=3.0)
            if answered and p.state != "sleeping":
                p.wake.update(active=False, result="awake", finished=time.time())
                self._derive_state(p, True)
                return
            if answered and p.state == "sleeping" and p.wake["attempts"] >= 3:
                # It answers but still reports power-save: that is normal for HP; it will print fine.
                p.wake.update(active=False, result="answering", finished=time.time())
                self._derive_state(p, True)
                return
            await asyncio.sleep(3.0)
        assert p.wake is not None
        p.wake.update(active=False, result="timeout", finished=time.time())
        await self.poll(p)

    async def _poke_http(self, host: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                await c.get(f"http://{host}/")
        except httpx.HTTPError:
            pass

    async def _poke_tcp(self, host: str, port: int) -> None:
        try:
            _, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=3.0)
            w.close()
        except (OSError, asyncio.TimeoutError):
            pass

    def _send_wol(self, p: Printer) -> None:
        if not p.mac or p.mac == "self":
            return
        try:
            mac = bytes.fromhex(p.mac.replace(":", "").replace("-", ""))
            packet = b"\xff" * 6 + mac * 16
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(packet, ("255.255.255.255", 9))
            s.close()
        except (OSError, ValueError) as e:
            log.debug("WoL failed for %s: %s", p.host, e)

    # ----- scanner
    async def scanner_info(self, p: Printer) -> dict[str, Any]:
        if not p.scan_base:
            raise ValueError("this printer did not advertise a scanner")
        host, port, path = _split_base(p.scan_base)
        sc = EsclScanner(host, port, path)
        caps, status = await asyncio.gather(sc.capabilities(), sc.status(), return_exceptions=True)
        info = {"capabilities": caps if isinstance(caps, dict) else None,
                "status": status if isinstance(status, dict) else None,
                "error": str(caps) if isinstance(caps, Exception) else (str(status) if isinstance(status, Exception) else None)}
        p.scanner = info
        return info

    def scanner_for(self, p: Printer) -> EsclScanner:
        if not p.scan_base:
            raise ValueError("this printer did not advertise a scanner")
        host, port, path = _split_base(p.scan_base)
        return EsclScanner(host, port, path)

    def views(self) -> list[dict[str, Any]]:
        return [p.view() for p in sorted(self.printers.values(), key=lambda x: x.name.lower())]


def _split_base(base: str) -> tuple[str, int, str]:
    m = re.match(r"^(https?)://([^/:]+)(?::(\d+))?(/.*)?$", base)
    if not m:
        return base, 80, "/eSCL"
    scheme, host, port, path = m.groups()
    return host, int(port or (443 if scheme == "https" else 80)), path or "/eSCL"


def _supply_name(label: str, color: str | None, typ: str | None) -> str:
    names = {"K": "Black", "C": "Cyan", "M": "Magenta", "Y": "Yellow", "CMY": "Tri-colour", "PK": "Photo black",
             "MK": "Matte black", "LC": "Light cyan", "LM": "Light magenta", "GY": "Grey"}
    base = names.get(label.upper(), label)
    if typ and typ.lower() in ("ink", "toner", "inkcartridge", "tonercartridge"):
        kind = "ink" if "ink" in typ.lower() else "toner"
        return f"{base} {kind}"
    if typ and "printhead" in typ.lower():
        return f"{base} printhead"
    if typ and "maintenance" in typ.lower():
        return "Maintenance kit"
    if typ and "drum" in typ.lower():
        return f"{base} drum"
    return base


def _css_color(label: str, color: str | None) -> str:
    l = (label or "").upper()
    c = (color or "").lower()
    if "#" in c and len(c) == 7:
        return c
    if l in ("K", "BLACK") or "black" in c:
        return "#222"
    if l == "C" or "cyan" in c:
        return "#00a9e0"
    if l == "M" or "magenta" in c:
        return "#e6007e"
    if l == "Y" or "yellow" in c:
        return "#f5d000"
    if l == "CMY":
        return "linear-gradient(90deg,#00a9e0,#e6007e,#f5d000)"
    return "#888"
