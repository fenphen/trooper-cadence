"""Network status: internet reachability, gateway, WAN address, and a LAN device sweep.

Works on Windows and Linux with only the OS's own ping and arp commands, so there
is nothing to install (no Npcap, no nmap). Device history lives in SQLite.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import platform
import re
import socket
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from . import oui

log = logging.getLogger(__name__)
IS_WINDOWS = platform.system() == "Windows"
MAC_RE = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")


# ---------------------------------------------------------------- basics

def local_ip() -> str | None:
    """The address of the interface that routes to the internet (no packets are sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def default_gateway() -> str | None:
    try:
        if IS_WINDOWS:
            out = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=5).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    return parts[2]
        else:
            out = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"default via (\S+)", out)
            if m:
                return m.group(1)
    except (OSError, subprocess.SubprocessError):
        pass
    ip = local_ip()
    if ip:
        return str(ipaddress.ip_network(ip + "/24", strict=False).network_address + 1)
    return None


def _netmask_for(ip: str) -> str | None:
    """Read the subnet mask of the interface that owns `ip` from the OS."""
    try:
        if IS_WINDOWS:
            out = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5).stdout
            lines = out.splitlines()
            for i, line in enumerate(lines):
                if "IPv4" in line and line.strip().endswith(ip):
                    for nxt in lines[i + 1:i + 4]:
                        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s*$", nxt)
                        if "Subnet" in nxt and m:
                            return m.group(1)
        else:
            out = subprocess.run(["ip", "-o", "-4", "addr"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(rf"inet {re.escape(ip)}/(\d+)", out)
            if m:
                return str(ipaddress.ip_network(f"0.0.0.0/{m.group(1)}").netmask)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def guess_subnet() -> str | None:
    """The LAN range to scan. Deco meshes use a /22 (192.168.68.0 - 192.168.71.255), so the
    real mask matters; fall back to /24 if the OS will not tell us."""
    ip = local_ip()
    if not ip:
        return None
    mask = _netmask_for(ip)
    try:
        net = ipaddress.ip_network(f"{ip}/{mask or 24}", strict=False)
    except ValueError:
        net = ipaddress.ip_network(ip + "/24", strict=False)
    if net.prefixlen < 22:  # don't sweep anything bigger than 1024 addresses
        net = ipaddress.ip_network(ip + "/22", strict=False)
    return str(net)


async def ping(host: str, timeout_s: float = 1.0) -> float | None:
    """Round-trip time in ms, or None if unreachable."""
    if IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", str(int(timeout_s * 1000)), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout_s))), host]
    t0 = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s + 2)
    except (OSError, asyncio.TimeoutError):
        return None
    if proc.returncode != 0:
        return None
    text = out.decode("utf-8", "replace")
    m = re.search(r"time[=<]\s*([\d.]+)\s*ms", text)
    if m:
        return float(m.group(1))
    # Windows can say "time<1ms"; fall back to the wall clock
    return (time.perf_counter() - t0) * 1000


async def tcp_check(host: str, port: int, timeout_s: float = 2.0) -> float | None:
    t0 = time.perf_counter()
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout_s)
        w.close()
        try:
            await w.wait_closed()
        except OSError:
            pass
        return (time.perf_counter() - t0) * 1000
    except (OSError, asyncio.TimeoutError):
        return None


async def wan_ip(timeout_s: float = 5.0) -> str | None:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as c:
                r = await c.get(url, headers={"User-Agent": "curl/8"})
            if r.status_code == 200 and len(r.text.strip()) < 64:
                return r.text.strip()
        except httpx.HTTPError:
            continue
    return None


async def internet_status(gateway: str | None) -> dict[str, Any]:
    gw_ms, dns_ms, web_ms = await asyncio.gather(
        ping(gateway) if gateway else asyncio.sleep(0, result=None),
        ping("1.1.1.1"),
        tcp_check("www.google.com", 443),
    )
    # ping may be blocked by a firewall; a TCP connect to a public site is the real verdict
    online = web_ms is not None or dns_ms is not None
    return {
        "online": online,
        "gateway": gateway,
        "gateway_ms": gw_ms,
        "internet_ping_ms": dns_ms,
        "web_ms": web_ms,
        "checked_at": time.time(),
    }


# ---------------------------------------------------------------- sweep

def read_arp_table() -> dict[str, str]:
    """ip -> mac for every neighbour the OS currently knows."""
    table: dict[str, str] = {}
    try:
        if IS_WINDOWS:
            out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3 and MAC_RE.fullmatch(parts[1]) and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", parts[0]):
                    mac = parts[1].replace("-", ":").lower()
                    if mac not in ("ff:ff:ff:ff:ff:ff",) and not mac.startswith("01:00:5e"):
                        table[parts[0]] = mac
        else:
            out = subprocess.run(["ip", "neigh"], capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and "lladdr" in parts and "FAILED" not in parts:
                    table[parts[0]] = parts[parts.index("lladdr") + 1].lower()
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("arp read failed: %s", e)
    return table


async def reverse_dns(ip: str) -> str | None:
    try:
        name = await asyncio.wait_for(asyncio.to_thread(socket.gethostbyaddr, ip), timeout=2.0)
        return name[0]
    except (OSError, asyncio.TimeoutError):
        return None


async def sweep(subnet: str, concurrency: int = 64) -> list[dict[str, Any]]:
    """Ping every address so the OS fills its ARP cache, then read the cache."""
    net = ipaddress.ip_network(subnet, strict=False)
    hosts = [str(h) for h in net.hosts()]
    if len(hosts) > 1024:
        hosts = hosts[:1024]
    sem = asyncio.Semaphore(concurrency)
    alive: dict[str, float | None] = {}

    async def one(ip: str) -> None:
        async with sem:
            alive[ip] = await ping(ip, 1.0)

    await asyncio.gather(*(one(h) for h in hosts))
    arp = read_arp_table()
    me = local_ip()
    devices = []
    seen_ips = set(arp) | {ip for ip, ms in alive.items() if ms is not None}
    for ip in sorted(seen_ips, key=lambda s: tuple(int(p) for p in s.split("."))):
        if ipaddress.ip_address(ip) not in net:
            continue
        mac = arp.get(ip)
        if ip == me and not mac:
            mac = "self"
        devices.append({"ip": ip, "mac": mac, "online": alive.get(ip) is not None or ip == me,
                        "ping_ms": alive.get(ip), "is_me": ip == me})
    names = await asyncio.gather(*(reverse_dns(d["ip"]) for d in devices))
    for d, n in zip(devices, names):
        d["hostname"] = n
        d["vendor"] = oui.vendor_for(d["mac"]) if d["mac"] and d["mac"] != "self" else None
    return devices


# ---------------------------------------------------------------- history

class DeviceStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                mac TEXT PRIMARY KEY, ip TEXT, hostname TEXT, vendor TEXT, name TEXT,
                first_seen REAL, last_seen REAL, online INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sightings (
                mac TEXT, at REAL, online INTEGER
            );
            CREATE INDEX IF NOT EXISTS sightings_mac ON sightings(mac, at);
            CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
        """)

    def record(self, devices: list[dict[str, Any]]) -> None:
        now = time.time()
        online_macs = set()
        with self.db:
            for d in devices:
                mac = d.get("mac")
                if not mac:
                    continue
                online_macs.add(mac)
                row = self.db.execute("SELECT * FROM devices WHERE mac=?", (mac,)).fetchone()
                if row is None:
                    self.db.execute("INSERT INTO devices(mac, ip, hostname, vendor, first_seen, last_seen, online) VALUES (?,?,?,?,?,?,1)",
                                    (mac, d["ip"], d.get("hostname"), d.get("vendor"), now, now))
                    self.db.execute("INSERT INTO sightings VALUES (?,?,1)", (mac, now))
                else:
                    self.db.execute("UPDATE devices SET ip=?, hostname=COALESCE(?, hostname), vendor=COALESCE(?, vendor), last_seen=?, online=1 WHERE mac=?",
                                    (d["ip"], d.get("hostname"), d.get("vendor"), now, mac))
                    if not row["online"]:
                        self.db.execute("INSERT INTO sightings VALUES (?,?,1)", (mac, now))
            for row in self.db.execute("SELECT mac FROM devices WHERE online=1").fetchall():
                if row["mac"] not in online_macs:
                    self.db.execute("UPDATE devices SET online=0 WHERE mac=?", (row["mac"],))
                    self.db.execute("INSERT INTO sightings VALUES (?,?,0)", (row["mac"], now))

    def all_devices(self) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM devices ORDER BY online DESC, last_seen DESC").fetchall()
        return [dict(r) for r in rows]

    def set_name(self, mac: str, name: str | None) -> None:
        with self.db:
            self.db.execute("UPDATE devices SET name=? WHERE mac=?", (name or None, mac))

    def forget(self, mac: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM devices WHERE mac=?", (mac,))
            self.db.execute("DELETE FROM sightings WHERE mac=?", (mac,))

    def history(self, mac: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT at, online FROM sightings WHERE mac=? ORDER BY at DESC LIMIT ?", (mac, limit)).fetchall()
        return [dict(r) for r in rows]

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return row["v"] if row else None

    def put(self, key: str, value: str) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, value))
