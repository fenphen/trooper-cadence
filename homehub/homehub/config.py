"""config.json: a plain file next to the app that the dashboard also edits for you."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "port": 8080,
    "bind": "0.0.0.0",
    "poll_seconds": 30,
    "discovery_minutes": 10,
    "printers": [],              # manual entries: {"host": "192.168.68.20", "name": "Upstairs"}
    "printer_names": {},         # printer id -> friendly name
    "network": {"enabled": True, "subnet": None, "sweep_minutes": 5},
    "deco": {"enabled": False, "host": "", "password": "", "username": "admin"},
    "oui_download": True,
}


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, path: Path):
        self.path = path
        self.data_dir = path.parent / "data"
        self._lock = threading.Lock()
        self.values: dict[str, Any] = json.loads(json.dumps(DEFAULTS))
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.values = _merge(DEFAULTS, json.loads(self.path.read_text("utf-8")))
            except (OSError, ValueError) as e:
                log.error("config.json is not valid, using defaults: %s", e)
        else:
            self.save()

    def save(self) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.values, indent=2), "utf-8")
            tmp.replace(self.path)

    def get(self, *keys: str, default: Any = None) -> Any:
        cur: Any = self.values
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def set(self, value: Any, *keys: str) -> None:
        cur = self.values
        for k in keys[:-1]:
            cur = cur.setdefault(k, {})
        cur[keys[-1]] = value
        self.save()

    def public(self) -> dict[str, Any]:
        """Settings safe to send to the browser (no password)."""
        v = json.loads(json.dumps(self.values))
        v["deco"]["password"] = "" if not v["deco"].get("password") else "********"
        return v
