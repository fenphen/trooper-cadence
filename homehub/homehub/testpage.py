"""Generate a tiny one-page PDF test page without any PDF library."""
from __future__ import annotations

from datetime import datetime


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def test_page_pdf(printer_name: str, model: str | None, host: str, sender: str = "Home Hub") -> bytes:
    now = datetime.now().strftime("%A %d %B %Y, %H:%M")
    lines = [
        ("Helv", 28, f"{sender} test page"),
        ("Helv", 14, ""),
        ("Helv", 14, f"Printer:  {printer_name}"),
        ("Helv", 14, f"Model:    {model or 'unknown'}"),
        ("Helv", 14, f"Address:  {host}"),
        ("Helv", 14, f"Printed:  {now}"),
        ("Helv", 14, ""),
        ("Helv", 12, "If you can read this, the dashboard can print to this printer."),
        ("Helv", 12, "The box below should have crisp edges and the text should not be cut off."),
    ]
    content = ["q", "2 w", "36 36 540 720 re S", "Q"]
    y = 700
    for font, size, text in lines:
        content.append(f"BT /F1 {size} Tf 72 {y} Td ({_esc(text)}) Tj ET")
        y -= int(size * 1.6)
    # a row of grey/colour swatches so colour and gradient problems show up
    shades = [(0.1, 0.1, 0.1), (0.4, 0.4, 0.4), (0.7, 0.7, 0.7), (0.9, 0.1, 0.1), (0.1, 0.6, 0.1), (0.1, 0.2, 0.9), (0.9, 0.8, 0.1)]
    x = 72
    for r, g, b in shades:
        content.append(f"q {r} {g} {b} rg {x} 420 56 56 re f Q")
        x += 66
    content.append("BT /F1 10 Tf 72 400 Td (Swatches: black, dark grey, light grey, red, green, blue, yellow) Tj ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objs: list[bytes] = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
