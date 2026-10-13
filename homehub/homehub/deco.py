"""TP-Link Deco local API client (unofficial, reverse-engineered).

The Deco app talks to the master Deco over its cloud, but the master also serves
the same JSON API on the LAN at http://<deco-ip>/cgi-bin/luci/ with an
RSA + AES handshake. This follows the widely used Home Assistant integration's
protocol. It needs the Deco admin password (the one the Deco app asks for), and
the Deco's LAN address (usually your gateway, e.g. 192.168.68.1).

EXPERIMENTAL: written without a Deco on hand. If it fails, the error message is
shown in the dashboard so it can be fixed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time
from typing import Any

import httpx
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad

log = logging.getLogger(__name__)


class DecoError(Exception):
    pass


def _b64_decode_name(s: str | None) -> str | None:
    if not s:
        return s
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return s


class DecoClient:
    def __init__(self, host: str, password: str, username: str = "admin", timeout: float = 10.0, verify_ssl: bool = False):
        self.host = host.rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._stok: str | None = None
        self._seq: int | None = None
        self._auth_key: RSA.RsaKey | None = None
        self._aes_key: bytes = b""
        self._aes_iv: bytes = b""
        self._hash: str = ""
        self._logged_in_at = 0.0

    # ----- crypto helpers
    def _rsa_from(self, pair: list[str]) -> RSA.RsaKey:
        n = int(pair[0], 16)
        e = int(pair[1], 16)
        return RSA.construct((n, e))

    def _rsa_encrypt(self, key: RSA.RsaKey, data: bytes) -> str:
        cipher = PKCS1_v1_5.new(key)
        chunk = key.size_in_bytes() - 11
        out = b""
        for i in range(0, len(data), chunk):
            out += cipher.encrypt(data[i:i + chunk])
        return out.hex()

    def _aes_encrypt(self, text: str) -> str:
        c = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
        return base64.b64encode(c.encrypt(pad(text.encode("utf-8"), 16))).decode()

    def _aes_decrypt(self, text: str) -> str:
        c = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
        return unpad(c.decrypt(base64.b64decode(text)), 16).decode("utf-8", "replace")

    def _sign(self, data_len: int, login: bool = False) -> str:
        assert self._auth_key is not None and self._seq is not None
        if login:
            s = f"k={self._aes_key.decode()}&i={self._aes_iv.decode()}&h={self._hash}&s={self._seq + data_len}"
        else:
            s = f"h={self._hash}&s={self._seq + data_len}"
        return self._rsa_encrypt(self._auth_key, s.encode())

    # ----- http
    async def _post(self, client: httpx.AsyncClient, path: str, **kw: Any) -> dict[str, Any]:
        url = f"{self.host}/cgi-bin/luci/;stok={self._stok or ''}/{path}"
        try:
            r = await client.post(url, **kw)
        except httpx.HTTPError as e:
            raise DecoError(f"cannot reach Deco at {self.host}: {e}") from e
        try:
            return r.json()
        except ValueError as e:
            raise DecoError(f"Deco returned something that is not JSON (HTTP {r.status_code})") from e

    async def login(self) -> None:
        async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl) as client:
            keys = await self._post(client, "login?form=keys", json={"operation": "read"})
            if keys.get("error_code") != 0:
                raise DecoError(f"keys request failed: {keys}")
            password_key = self._rsa_from(keys["result"]["password"])
            auth = await self._post(client, "login?form=auth", json={"operation": "read"})
            if auth.get("error_code") != 0:
                raise DecoError(f"auth request failed: {auth}")
            self._auth_key = self._rsa_from(auth["result"]["key"])
            self._seq = int(auth["result"]["seq"])
            self._hash = hashlib.md5(f"{self.username}{self.password}".encode()).hexdigest()
            self._aes_key = "".join(secrets.choice("0123456789") for _ in range(16)).encode()
            self._aes_iv = "".join(secrets.choice("0123456789") for _ in range(16)).encode()
            enc_pw = self._rsa_encrypt(password_key, self.password.encode())
            payload = json.dumps({"params": {"password": enc_pw}, "operation": "login"})
            data = self._aes_encrypt(payload)
            sign = self._sign(len(data), login=True)
            self._stok = None
            res = await self._post(client, "login?form=login", data={"sign": sign, "data": data})
            if res.get("error_code") != 0:
                raise DecoError(f"login refused (error {res.get('error_code')}); check the Deco password")
            try:
                inner = json.loads(self._aes_decrypt(res["result"]["data"]))
            except (KeyError, ValueError) as e:
                raise DecoError(f"could not decrypt login reply: {res}") from e
            if inner.get("error_code") not in (0, None):
                raise DecoError(f"login failed: {inner}")
            self._stok = inner.get("result", {}).get("stok") or inner.get("stok")
            if not self._stok:
                raise DecoError(f"login reply had no session token: {inner}")
            self._logged_in_at = time.time()

    async def call(self, path: str, payload: dict[str, Any], _retry: bool = True) -> dict[str, Any]:
        if not self._stok:
            await self.login()
        data = self._aes_encrypt(json.dumps(payload))
        sign = self._sign(len(data))
        async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl) as client:
            res = await self._post(client, path, data={"sign": sign, "data": data})
        if res.get("error_code") == -40401 and _retry:  # invalid stok → log in again
            self._stok = None
            return await self.call(path, payload, _retry=False)
        if res.get("error_code") != 0:
            raise DecoError(f"{path}: error {res.get('error_code')}")
        try:
            inner = json.loads(self._aes_decrypt(res["result"]["data"]))
        except (KeyError, ValueError) as e:
            raise DecoError(f"could not decrypt reply from {path}") from e
        if inner.get("error_code") not in (0, None):
            if inner.get("error_code") == -40401 and _retry:
                self._stok = None
                return await self.call(path, payload, _retry=False)
            raise DecoError(f"{path}: Deco error {inner.get('error_code')}")
        return inner.get("result", {})

    # ----- high level
    async def nodes(self) -> list[dict[str, Any]]:
        res = await self.call("admin/device?form=device_list", {"operation": "read"})
        out = []
        for d in res.get("device_list", []):
            out.append({
                "name": _b64_decode_name(d.get("nickname")) or d.get("custom_nickname") or d.get("device_model"),
                "model": d.get("device_model"),
                "hw": d.get("hardware_ver"),
                "fw": d.get("software_ver"),
                "ip": d.get("device_ip"),
                "mac": d.get("mac"),
                "role": d.get("role"),
                "online": d.get("inet_status") == "online" or d.get("online", True),
                "signal": d.get("signal_level"),
                "connection": d.get("connection_type"),
                "parent": d.get("parent_device_id") or d.get("parent"),
            })
        return out

    async def clients(self) -> list[dict[str, Any]]:
        res = await self.call("admin/client?form=client_list", {"operation": "read", "params": {"device_mac": "default"}})
        out = []
        for c in res.get("client_list", []):
            out.append({
                "name": _b64_decode_name(c.get("name")),
                "ip": c.get("ip"),
                "mac": (c.get("mac") or "").replace("-", ":").lower() or None,
                "online": bool(c.get("online", True)),
                "connection": c.get("connection_type"),
                "interface": c.get("interface"),
                "wire_type": c.get("wire_type"),
                "down_kbps": c.get("down_speed"),
                "up_kbps": c.get("up_speed"),
                "type": c.get("client_type"),
                "via": c.get("owner_id") or c.get("deco_mac") or c.get("access_host"),
            })
        return out

    async def wan(self) -> dict[str, Any]:
        res = await self.call("admin/network?form=wan_ipv4", {"operation": "read"})
        wan = res.get("wan", {}) or {}
        info = wan.get("ip_info", {}) or {}
        return {
            "ip": info.get("ip"),
            "gateway": info.get("gateway"),
            "dns": [info.get("dns1"), info.get("dns2")],
            "dial_type": wan.get("dial_type"),
            "mac": info.get("mac"),
        }

    async def internet(self) -> dict[str, Any]:
        try:
            res = await self.call("admin/network?form=internet", {"operation": "read"})
        except DecoError:
            return {}
        return res if isinstance(res, dict) else {}
