"""The web server: serves the dashboard page and a small JSON API."""
from __future__ import annotations

import asyncio
import io
import logging
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, network, oui
from .config import Config
from .deco import DecoClient, DecoError
from .escl import ScanError
from .ipp import IppClient, IppError
from .printers import PrinterManager
from .testpage import test_page_pdf

log = logging.getLogger("homehub")
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

PRINT_TYPES = {
    "application/pdf": "application/pdf",
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "text/plain": "text/plain",
    "application/postscript": "application/postscript",
}


class NetworkMonitor:
    def __init__(self, config: Config, store: network.DeviceStore):
        self.config = config
        self.store = store
        self.internet: dict[str, Any] = {}
        self.wan: str | None = None
        self.wan_checked: float | None = None
        self.devices: list[dict[str, Any]] = []
        self.last_sweep: float | None = None
        self.sweeping = False
        self.deco: dict[str, Any] = {"enabled": False}
        self._tasks: list[asyncio.Task] = []
        self._deco_client: DecoClient | None = None

    async def start(self) -> None:
        self._tasks = [asyncio.create_task(self._internet_loop()), asyncio.create_task(self._sweep_loop()),
                       asyncio.create_task(self._deco_loop())]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()

    @property
    def subnet(self) -> str | None:
        return self.config.get("network", "subnet") or network.guess_subnet()

    async def _internet_loop(self) -> None:
        while True:
            try:
                self.internet = await network.internet_status(network.default_gateway())
                if self.internet.get("online") and (self.wan_checked is None or time.time() - self.wan_checked > 600):
                    self.wan = await network.wan_ip()
                    self.wan_checked = time.time()
            except Exception as e:  # noqa: BLE001
                log.warning("internet check failed: %s", e)
            await asyncio.sleep(60)

    async def _sweep_loop(self) -> None:
        await asyncio.sleep(5)
        while True:
            if self.config.get("network", "enabled", default=True):
                await self.sweep()
            await asyncio.sleep(max(60, int(self.config.get("network", "sweep_minutes", default=5) or 5) * 60))

    async def sweep(self) -> None:
        if self.sweeping:
            return
        subnet = self.subnet
        if not subnet:
            return
        self.sweeping = True
        try:
            self.devices = await network.sweep(subnet)
            self.store.record(self.devices)
            self.last_sweep = time.time()
        except Exception as e:  # noqa: BLE001
            log.warning("sweep failed: %s", e)
        finally:
            self.sweeping = False

    def deco_client(self) -> DecoClient | None:
        d = self.config.get("deco", default={}) or {}
        if not d.get("enabled") or not d.get("host") or not d.get("password"):
            return None
        if self._deco_client is None or self._deco_client.host.rstrip("/").split("://")[-1] != d["host"] or self._deco_client.password != d["password"]:
            self._deco_client = DecoClient(d["host"], d["password"], d.get("username") or "admin")
        return self._deco_client

    async def refresh_deco(self) -> dict[str, Any]:
        client = self.deco_client()
        if client is None:
            self.deco = {"enabled": False}
            return self.deco
        try:
            nodes, clients, wan = await asyncio.gather(client.nodes(), client.clients(), client.wan())
            self.deco = {"enabled": True, "ok": True, "nodes": nodes, "clients": clients, "wan": wan,
                         "checked_at": time.time(), "error": None}
        except (DecoError, Exception) as e:  # noqa: BLE001
            self.deco = {"enabled": True, "ok": False, "error": str(e), "checked_at": time.time(),
                         "nodes": self.deco.get("nodes", []), "clients": self.deco.get("clients", []), "wan": self.deco.get("wan")}
            log.warning("Deco: %s", e)
        return self.deco

    async def _deco_loop(self) -> None:
        await asyncio.sleep(3)
        while True:
            await self.refresh_deco()
            await asyncio.sleep(120)

    def device_view(self) -> list[dict[str, Any]]:
        known = {d["mac"]: d for d in self.store.all_devices()}
        deco_by_mac = {c["mac"]: c for c in (self.deco.get("clients") or []) if c.get("mac")}
        out = []
        for mac, d in known.items():
            dc = deco_by_mac.get(mac, {})
            out.append({
                "mac": mac, "ip": d["ip"], "hostname": d.get("hostname"), "vendor": d.get("vendor") or oui.vendor_for(mac),
                "name": d.get("name") or dc.get("name"), "online": bool(d.get("online")),
                "first_seen": d.get("first_seen"), "last_seen": d.get("last_seen"),
                "connection": dc.get("connection"), "deco_type": dc.get("type"),
                "down_kbps": dc.get("down_kbps"), "up_kbps": dc.get("up_kbps"), "is_me": mac == "self",
            })
        out.sort(key=lambda d: (not d["online"], tuple(int(p) for p in (d["ip"] or "0.0.0.0").split(".")) if d["ip"] else ()))
        return out

    def view(self) -> dict[str, Any]:
        devices = self.device_view()
        return {
            "internet": self.internet, "wan_ip": self.wan, "subnet": self.subnet, "local_ip": network.local_ip(),
            "gateway": self.internet.get("gateway"), "last_sweep": self.last_sweep, "sweeping": self.sweeping,
            "online_count": sum(1 for d in devices if d["online"]), "device_count": len(devices),
            "devices": devices, "deco": self.deco,
        }


def create_app(config_path: Path | None = None) -> FastAPI:
    config = Config(config_path or ROOT / "config.json")
    store = network.DeviceStore(config.data_dir / "homehub.db")
    printers = PrinterManager(config)
    net = NetworkMonitor(config, store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        asyncio.create_task(oui.ensure_downloaded(config.data_dir, bool(config.get("oui_download", default=True))))
        await printers.start()
        await net.start()
        log.info("Home Hub %s ready on port %s", __version__, config.get("port"))
        yield
        await printers.stop()
        await net.stop()

    app = FastAPI(title="Home Hub", version=__version__, lifespan=lifespan)
    app.state.config = config
    app.state.printers = printers
    app.state.network = net

    def printer_or_404(pid: str):
        p = printers.printers.get(pid)
        if not p:
            raise HTTPException(404, "printer not found")
        return p

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/overview")
    async def overview():
        return {"version": __version__, "now": time.time(), "printers": printers.views(),
                "discovering": printers.discovering, "last_discovery": printers.last_discovery,
                "network": net.view(), "settings": config.public()}

    # ---- printers
    @app.get("/api/printers")
    async def list_printers():
        return printers.views()

    @app.post("/api/printers/discover")
    async def discover():
        n = await printers.discover(5.0)
        return {"new": n, "printers": printers.views()}

    @app.post("/api/printers")
    async def add_printer(body: dict[str, Any]):
        p = await printers.add_manual(body.get("host"), body.get("name"))
        if not p:
            raise HTTPException(400, "host is required")
        return p.view()

    @app.patch("/api/printers/{pid}")
    async def rename_printer(pid: str, body: dict[str, Any]):
        p = printers.rename(pid, str(body.get("name", "")))
        if not p:
            raise HTTPException(404, "printer not found")
        return p.view()

    @app.delete("/api/printers/{pid}")
    async def delete_printer(pid: str):
        if not printers.remove(pid):
            raise HTTPException(404, "printer not found")
        return {"ok": True}

    @app.post("/api/printers/{pid}/refresh")
    async def refresh_printer(pid: str):
        p = printer_or_404(pid)
        await printers.poll(p)
        return p.view()

    @app.post("/api/printers/{pid}/wake")
    async def wake_printer(pid: str):
        p = printer_or_404(pid)
        printers.start_wake(p)
        return p.view()

    @app.post("/api/printers/{pid}/testpage")
    async def print_test_page(pid: str):
        p = printer_or_404(pid)
        if not p.ipp_uri:
            raise HTTPException(400, "no IPP address for this printer")
        pdf = test_page_pdf(p.name, p.model, p.host)
        try:
            res = await IppClient(p.ipp_uri).print_job(pdf, job_name="Home Hub test page", mime="application/pdf")
        except (IppError, httpx.HTTPError) as e:
            raise HTTPException(502, f"printer did not accept the job: {e}") from e
        if not res.ok:
            raise HTTPException(502, f"printer refused the job: {res.status_message}")
        asyncio.create_task(printers.poll(p))
        return {"ok": True, "job": res.job}

    @app.post("/api/printers/{pid}/print")
    async def print_file(pid: str, file: UploadFile = File(...), copies: int = Form(1)):
        p = printer_or_404(pid)
        if not p.ipp_uri:
            raise HTTPException(400, "no IPP address for this printer")
        data = await file.read()
        if not data:
            raise HTTPException(400, "empty file")
        if len(data) > 100 * 1024 * 1024:
            raise HTTPException(413, "file is larger than 100 MB")
        mime = (file.content_type or "").split(";")[0].strip().lower()
        name = (file.filename or "").lower()
        if mime not in PRINT_TYPES:
            if name.endswith(".pdf"):
                mime = "application/pdf"
            elif name.endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            elif name.endswith(".png"):
                mime = "image/png"
            elif name.endswith(".txt"):
                mime = "text/plain"
            else:
                raise HTTPException(415, "Printers accept PDF, JPEG, PNG and plain text here. For Word or other files, print from the app or save as PDF first.")
        supported = set(p.ipp.get("formats") or [])
        send_mime = mime if (not supported or mime in supported) else "application/octet-stream"
        try:
            res = await IppClient(p.ipp_uri).print_job(data, job_name=file.filename or "Home Hub print", mime=send_mime,
                                                       copies=max(1, min(int(copies), 99)))
        except (IppError, httpx.HTTPError) as e:
            raise HTTPException(502, f"printer did not accept the job: {e}") from e
        if not res.ok:
            raise HTTPException(502, f"printer refused the job: {res.status_message}")
        asyncio.create_task(printers.poll(p))
        return {"ok": True, "job": res.job, "format": send_mime}

    @app.get("/api/printers/{pid}/scanner")
    async def scanner(pid: str):
        p = printer_or_404(pid)
        try:
            return await printers.scanner_info(p)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/api/printers/{pid}/scan")
    async def scan(pid: str, source: str = "Platen", color: str = "RGB24", resolution: int = 300, format: str = "pdf"):
        p = printer_or_404(pid)
        fmt = "application/pdf" if format == "pdf" else "image/jpeg"
        try:
            sc = printers.scanner_for(p)
            docs = await sc.scan(source=source, color_mode=color, resolution=max(75, min(resolution, 1200)), fmt=fmt)
        except (ValueError, ScanError, httpx.HTTPError) as e:
            raise HTTPException(502, str(e)) from e
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        if len(docs) == 1:
            ext = "pdf" if fmt == "application/pdf" else "jpg"
            return Response(docs[0], media_type=fmt,
                            headers={"Content-Disposition": f'attachment; filename="scan_{stamp}.{ext}"'})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for i, d in enumerate(docs, 1):
                z.writestr(f"scan_{stamp}_page{i}.{'pdf' if fmt == 'application/pdf' else 'jpg'}", d)
        return Response(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="scan_{stamp}.zip"'})

    # ---- network
    @app.get("/api/network")
    async def get_network():
        return net.view()

    @app.post("/api/network/scan")
    async def network_scan():
        asyncio.create_task(net.sweep())
        return {"started": True}

    @app.patch("/api/network/devices/{mac}")
    async def name_device(mac: str, body: dict[str, Any]):
        store.set_name(mac.lower(), (body.get("name") or "").strip() or None)
        return {"ok": True}

    @app.delete("/api/network/devices/{mac}")
    async def forget_device(mac: str):
        store.forget(mac.lower())
        return {"ok": True}

    @app.get("/api/network/devices/{mac}/history")
    async def device_history(mac: str):
        return store.history(mac.lower())

    @app.post("/api/deco/refresh")
    async def deco_refresh():
        return await net.refresh_deco()

    # ---- settings
    @app.get("/api/settings")
    async def get_settings():
        return config.public()

    @app.put("/api/settings")
    async def put_settings(body: dict[str, Any]):
        if "network" in body and isinstance(body["network"], dict):
            n = body["network"]
            if "subnet" in n:
                config.set((n["subnet"] or "").strip() or None, "network", "subnet")
            if "sweep_minutes" in n:
                config.set(max(1, int(n["sweep_minutes"] or 5)), "network", "sweep_minutes")
            if "enabled" in n:
                config.set(bool(n["enabled"]), "network", "enabled")
        if "deco" in body and isinstance(body["deco"], dict):
            d = body["deco"]
            if "enabled" in d:
                config.set(bool(d["enabled"]), "deco", "enabled")
            if "host" in d:
                config.set((d["host"] or "").strip(), "deco", "host")
            if "username" in d:
                config.set((d["username"] or "admin").strip(), "deco", "username")
            if d.get("password") and d["password"] != "********":
                config.set(d["password"], "deco", "password")
            asyncio.create_task(net.refresh_deco())
        if "poll_seconds" in body:
            config.set(max(10, int(body["poll_seconds"])), "poll_seconds")
        return config.public()

    @app.get("/api/health")
    async def health():
        return {"ok": True, "version": __version__}

    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
    return app


def main() -> None:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser(description="Home Hub: printer, scanner and network dashboard")
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--port", type=int)
    ap.add_argument("--bind")
    ap.add_argument("--log", default="info")
    args = ap.parse_args()
    cfg_path = Path(args.config)
    log_dir = cfg_path.parent / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    # Under pythonw.exe (the hidden startup task) there is no console: stdout/stderr are None
    # and anything that touches them crashes the process. Point them at a file instead.
    import sys
    if sys.stdout is None or sys.stderr is None:
        console = open(log_dir / "console.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or console
        sys.stderr = sys.stderr or console
    from logging.handlers import RotatingFileHandler
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr),
                                       RotatingFileHandler(log_dir / "homehub.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")]
    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)
    try:
        app = create_app(cfg_path)
        cfg: Config = app.state.config
        uvicorn.run(app, host=args.bind or cfg.get("bind", default="0.0.0.0"),
                    port=args.port or int(cfg.get("port", default=8080)), log_level=args.log, log_config=None)
    except Exception:
        logging.getLogger("homehub").exception("Home Hub stopped because of an error")
        raise


if __name__ == "__main__":
    main()
