"""A small Internet Printing Protocol (IPP, RFC 8010/8011) client.

Only what the dashboard needs: encode a request, decode a response, and two
operations (Get-Printer-Attributes and Print-Job). No external IPP library, so
the whole wire format is in one file and testable without a printer.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

import httpx

# Operation ids
GET_PRINTER_ATTRIBUTES = 0x000B
PRINT_JOB = 0x0002
GET_JOBS = 0x000A

# Group tags
OPERATION_ATTRS = 0x01
JOB_ATTRS = 0x02
END_OF_ATTRS = 0x03
PRINTER_ATTRS = 0x04
UNSUPPORTED_ATTRS = 0x05

# Value tags
T_INTEGER = 0x21
T_BOOLEAN = 0x22
T_ENUM = 0x23
T_OCTETSTRING = 0x30
T_DATETIME = 0x31
T_RESOLUTION = 0x32
T_RANGE = 0x33
T_BEG_COLLECTION = 0x34
T_TEXT_LANG = 0x35
T_NAME_LANG = 0x36
T_END_COLLECTION = 0x37
T_TEXT = 0x41
T_NAME = 0x42
T_KEYWORD = 0x44
T_URI = 0x45
T_URISCHEME = 0x46
T_CHARSET = 0x47
T_NATURAL_LANG = 0x48
T_MIME = 0x49
T_MEMBER_NAME = 0x4A

OUT_OF_BAND = {0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16}
STRING_TAGS = {T_OCTETSTRING, T_TEXT, T_NAME, T_KEYWORD, T_URI, T_URISCHEME, T_CHARSET,
               T_NATURAL_LANG, T_MIME, T_MEMBER_NAME}

PRINTER_STATES = {3: "idle", 4: "processing", 5: "stopped"}

STATUS_OK = {0x0000, 0x0001, 0x0002}  # successful-ok, -ignored-or-substituted, -conflicting


class IppError(Exception):
    pass


@dataclass
class Attr:
    tag: int
    name: str
    values: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------- encoding

def _encode_value(tag: int, value: Any) -> bytes:
    if tag in (T_INTEGER, T_ENUM):
        return struct.pack(">i", int(value))
    if tag == T_BOOLEAN:
        return b"\x01" if value else b"\x00"
    if tag in STRING_TAGS:
        return str(value).encode("utf-8")
    if tag == T_RANGE:
        return struct.pack(">ii", *value)
    if tag == T_RESOLUTION:
        return struct.pack(">iib", *value)
    raise IppError(f"cannot encode tag {tag:#x}")


def encode_request(operation: int, request_id: int, operation_attrs: list[Attr],
                   job_attrs: list[Attr] | None = None, data: bytes = b"") -> bytes:
    out = bytearray(struct.pack(">BBHI", 2, 0, operation, request_id))

    def put_group(tag: int, attrs: list[Attr]) -> None:
        nonlocal out
        out.append(tag)
        for a in attrs:
            first = True
            for v in a.values:
                name = a.name.encode("utf-8") if first else b""
                val = _encode_value(a.tag, v)
                out.append(a.tag)
                out += struct.pack(">H", len(name)) + name
                out += struct.pack(">H", len(val)) + val
                first = False

    put_group(OPERATION_ATTRS, operation_attrs)
    if job_attrs:
        put_group(JOB_ATTRS, job_attrs)
    out.append(END_OF_ATTRS)
    return bytes(out) + data


def base_operation_attrs(printer_uri: str, user: str = "homehub") -> list[Attr]:
    return [
        Attr(T_CHARSET, "attributes-charset", ["utf-8"]),
        Attr(T_NATURAL_LANG, "attributes-natural-language", ["en"]),
        Attr(T_URI, "printer-uri", [printer_uri]),
        Attr(T_NAME, "requesting-user-name", [user]),
    ]


# ---------------------------------------------------------------- decoding

def _decode_value(tag: int, raw: bytes) -> Any:
    if tag in (T_INTEGER, T_ENUM):
        return struct.unpack(">i", raw)[0] if len(raw) == 4 else None
    if tag == T_BOOLEAN:
        return bool(raw and raw[0])
    if tag in STRING_TAGS:
        return raw.decode("utf-8", "replace")
    if tag in (T_TEXT_LANG, T_NAME_LANG):
        # lang-len, lang, text-len, text
        try:
            ll = struct.unpack(">H", raw[:2])[0]
            tl = struct.unpack(">H", raw[2 + ll:4 + ll])[0]
            return raw[4 + ll:4 + ll + tl].decode("utf-8", "replace")
        except struct.error:
            return raw.decode("utf-8", "replace")
    if tag == T_RANGE and len(raw) == 8:
        return list(struct.unpack(">ii", raw))
    if tag == T_RESOLUTION and len(raw) == 9:
        x, y, u = struct.unpack(">iib", raw)
        return {"x": x, "y": y, "units": "dpi" if u == 3 else "dpcm"}
    if tag == T_DATETIME and len(raw) == 11:
        y, mo, d, h, mi, s, ds, sign, oh, om = struct.unpack(">HBBBBBBcBB", raw)
        return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}{sign.decode()}{oh:02d}:{om:02d}"
    if tag in OUT_OF_BAND:
        return None
    return raw.hex()


@dataclass
class Response:
    version: tuple[int, int]
    status: int
    request_id: int
    groups: list[tuple[int, dict[str, Any]]]
    data: bytes = b""

    @property
    def ok(self) -> bool:
        return self.status in STATUS_OK

    def group(self, tag: int) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for t, g in self.groups:
            if t == tag:
                merged.update(g)
        return merged

    @property
    def printer(self) -> dict[str, Any]:
        return self.group(PRINTER_ATTRS)

    @property
    def job(self) -> dict[str, Any]:
        return self.group(JOB_ATTRS)

    @property
    def status_message(self) -> str:
        return self.group(OPERATION_ATTRS).get("status-message") or f"status {self.status:#06x}"


def decode_response(buf: bytes) -> Response:
    if len(buf) < 9:
        raise IppError("response too short")
    major, minor, status, request_id = struct.unpack(">BBHI", buf[:8])
    pos = 8
    groups: list[tuple[int, dict[str, Any]]] = []
    current: dict[str, Any] | None = None
    current_tag = 0
    last_name = ""
    # collection parsing: stack of (dict, pending_member_name)
    stack: list[list[Any]] = []

    def store(name: str, tag: int, value: Any) -> None:
        nonlocal last_name
        target = stack[-1][0] if stack else current
        if target is None:
            return
        if name:
            last_name = name
            target[name] = [value]
        else:
            existing = target.get(last_name)
            if isinstance(existing, list):
                existing.append(value)
            else:
                target[last_name] = [existing, value]

    while pos < len(buf):
        tag = buf[pos]
        pos += 1
        if tag == END_OF_ATTRS:
            if current is not None:
                groups.append((current_tag, current))
            return Response((major, minor), status, request_id, groups, buf[pos:])
        if tag < 0x10:  # group delimiter
            if current is not None:
                groups.append((current_tag, current))
            current, current_tag = {}, tag
            continue
        name_len = struct.unpack(">H", buf[pos:pos + 2])[0]
        pos += 2
        name = buf[pos:pos + name_len].decode("utf-8", "replace")
        pos += name_len
        val_len = struct.unpack(">H", buf[pos:pos + 2])[0]
        pos += 2
        raw = buf[pos:pos + val_len]
        pos += val_len

        if tag == T_BEG_COLLECTION:
            coll: dict[str, Any] = {}
            store(name, tag, coll)
            stack.append([coll, None])
            continue
        if tag == T_END_COLLECTION:
            if stack:
                stack.pop()
            continue
        if tag == T_MEMBER_NAME and stack:
            stack[-1][1] = raw.decode("utf-8", "replace")
            continue
        value = _decode_value(tag, raw)
        if stack:
            member = stack[-1][1]
            if member is not None:
                if stack[-1][0].get(member) is None:
                    stack[-1][0][member] = value
                else:
                    cur = stack[-1][0][member]
                    stack[-1][0][member] = (cur if isinstance(cur, list) else [cur]) + [value]
            continue
        store(name, tag, value)

    if current is not None:
        groups.append((current_tag, current))
    return Response((major, minor), status, request_id, groups, b"")


def first(attrs: dict[str, Any], name: str, default: Any = None) -> Any:
    v = attrs.get(name)
    if isinstance(v, list):
        return v[0] if v else default
    return default if v is None else v


def all_of(attrs: dict[str, Any], name: str) -> list[Any]:
    v = attrs.get(name)
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


# ---------------------------------------------------------------- client

WANTED_PRINTER_ATTRS = [
    "printer-state", "printer-state-reasons", "printer-state-message", "printer-make-and-model",
    "printer-info", "printer-location", "printer-uuid", "printer-name", "printer-is-accepting-jobs",
    "queued-job-count", "printer-up-time", "printer-firmware-string-version", "printer-firmware-name",
    "marker-names", "marker-levels", "marker-colors", "marker-types", "marker-high-levels",
    "marker-low-levels", "printer-alert", "printer-alert-description", "media-ready",
    "document-format-supported", "printer-icons", "printer-more-info", "printer-device-id",
    "printer-supply", "printer-supply-description", "printer-input-tray", "printer-output-tray",
    "printer-config-change-date-time", "printer-current-time", "copies-supported", "sides-supported",
    "print-color-mode-supported", "printer-dns-sd-name", "printer-strings-languages-supported",
]


class IppClient:
    """Talks to one printer. `uri` is like ipp://192.168.0.20:631/ipp/print."""

    def __init__(self, uri: str, timeout: float = 6.0):
        self.uri = uri
        self.timeout = timeout
        self._request_id = 0

    @property
    def http_url(self) -> str:
        u = self.uri
        if u.startswith("ipps://"):
            return "https://" + u[len("ipps://"):]
        if u.startswith("ipp://"):
            return "http://" + u[len("ipp://"):]
        return u

    def _next_id(self) -> int:
        self._request_id = (self._request_id % 0x7FFFFFFF) + 1
        return self._request_id

    async def _send(self, payload: bytes, timeout: float | None = None) -> Response:
        async with httpx.AsyncClient(timeout=timeout or self.timeout, verify=False) as client:
            r = await client.post(self.http_url, content=payload,
                                  headers={"Content-Type": "application/ipp"})
        if r.status_code != 200:
            raise IppError(f"HTTP {r.status_code} from printer")
        return decode_response(r.content)

    async def get_printer_attributes(self, requested: list[str] | None = None,
                                     timeout: float | None = None) -> Response:
        attrs = base_operation_attrs(self.uri)
        attrs.append(Attr(T_KEYWORD, "requested-attributes", requested or WANTED_PRINTER_ATTRS))
        return await self._send(encode_request(GET_PRINTER_ATTRIBUTES, self._next_id(), attrs), timeout)

    async def print_job(self, data: bytes, job_name: str = "Home Hub", mime: str = "application/octet-stream",
                        copies: int = 1, user: str = "homehub") -> Response:
        attrs = base_operation_attrs(self.uri, user)
        attrs.append(Attr(T_NAME, "job-name", [job_name]))
        attrs.append(Attr(T_MIME, "document-format", [mime]))
        job: list[Attr] = []
        if copies > 1:
            job.append(Attr(T_INTEGER, "copies", [copies]))
        payload = encode_request(PRINT_JOB, self._next_id(), attrs, job, data)
        return await self._send(payload, timeout=max(self.timeout, 60.0))

    async def get_jobs(self) -> Response:
        attrs = base_operation_attrs(self.uri)
        attrs.append(Attr(T_KEYWORD, "which-jobs", ["not-completed"]))
        attrs.append(Attr(T_KEYWORD, "requested-attributes", ["job-id", "job-name", "job-state", "job-state-reasons", "job-impressions-completed"]))
        return await self._send(encode_request(GET_JOBS, self._next_id(), attrs))


def summarize_printer(attrs: dict[str, Any]) -> dict[str, Any]:
    """Turn raw Get-Printer-Attributes into the fields the dashboard shows."""
    state_num = first(attrs, "printer-state")
    reasons = [r for r in all_of(attrs, "printer-state-reasons") if r and r != "none"]
    supplies = []
    names = all_of(attrs, "marker-names")
    levels = all_of(attrs, "marker-levels")
    colors = all_of(attrs, "marker-colors")
    types = all_of(attrs, "marker-types")
    lows = all_of(attrs, "marker-low-levels")
    for i, name in enumerate(names):
        level = levels[i] if i < len(levels) else None
        supplies.append({
            "name": name,
            "level": level if isinstance(level, int) and level >= 0 else None,  # -1 unknown, -2 unknown, -3 "some"
            "color": colors[i] if i < len(colors) else None,
            "type": types[i] if i < len(types) else None,
            "low_at": lows[i] if i < len(lows) else None,
        })
    return {
        "state": PRINTER_STATES.get(state_num, "unknown"),
        "state_reasons": reasons,
        "state_message": first(attrs, "printer-state-message"),
        "make_and_model": first(attrs, "printer-make-and-model"),
        "info": first(attrs, "printer-info"),
        "location": first(attrs, "printer-location"),
        "uuid": first(attrs, "printer-uuid"),
        "accepting_jobs": first(attrs, "printer-is-accepting-jobs"),
        "queued_jobs": first(attrs, "queued-job-count"),
        "up_time_seconds": first(attrs, "printer-up-time"),
        "firmware": first(attrs, "printer-firmware-string-version"),
        "alerts": all_of(attrs, "printer-alert-description"),
        "media_ready": all_of(attrs, "media-ready"),
        "formats": all_of(attrs, "document-format-supported"),
        "more_info": first(attrs, "printer-more-info"),
        "icons": all_of(attrs, "printer-icons"),
        "sides": all_of(attrs, "sides-supported"),
        "color_modes": all_of(attrs, "print-color-mode-supported"),
        "supplies": supplies,
    }
