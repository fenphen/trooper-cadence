"""A pretend HP printer for tests and demos: answers IPP on one port and the HP web
API + eSCL on another. Run it directly to try the dashboard without a real printer:

    python tests/fake_printer.py            # IPP on 6631, web on 6080
then add  localhost  ... actually add "127.0.0.1" won't work since ports differ;
use:  python -m homehub --config demo.json  with  {"printers":[{"host":"127.0.0.1"}]}
and set FAKE_STD_PORTS=1 to listen on 631/80 (needs admin on Windows/Linux).
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from homehub import ipp  # noqa: E402

STATE = {"sleeping": False, "printing": False, "jobs": [], "scans": 0, "level_k": 42, "level_cmy": 8}

STATUS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<psdyn:ProductStatusDyn xmlns:psdyn="http://www.hp.com/schemas/imaging/con/ledm/productstatusdyn/2009/03/16" xmlns:pscat="http://www.hp.com/schemas/imaging/con/ledm/productstatuscategories/2007/10/31" xmlns:locid="http://www.hp.com/schemas/imaging/con/ledm/localizationids/2007/10/31">
<psdyn:Status><pscat:StatusCategory>{cat}</pscat:StatusCategory><locid:StringId>{sid}</locid:StringId></psdyn:Status>
{alerts}
</psdyn:ProductStatusDyn>"""

CONSUMABLES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ccdyn:ConsumableConfigDyn xmlns:ccdyn="http://www.hp.com/schemas/imaging/con/ledm/consumableconfigdyn/2007/11/19" xmlns:dd="http://www.hp.com/schemas/imaging/con/dictionaries/1.0/">
<ccdyn:ConsumableInfo><dd:ConsumableLabelCode>K</dd:ConsumableLabelCode><dd:MarkerColor>Black</dd:MarkerColor><dd:ConsumableTypeEnum>ink</dd:ConsumableTypeEnum><dd:ConsumablePercentageLevelRemaining>{k}</dd:ConsumablePercentageLevelRemaining><dd:ConsumableLifeState>ok</dd:ConsumableLifeState></ccdyn:ConsumableInfo>
<ccdyn:ConsumableInfo><dd:ConsumableLabelCode>CMY</dd:ConsumableLabelCode><dd:MarkerColor>CyanMagentaYellow</dd:MarkerColor><dd:ConsumableTypeEnum>ink</dd:ConsumableTypeEnum><dd:ConsumablePercentageLevelRemaining>{cmy}</dd:ConsumablePercentageLevelRemaining><dd:ConsumableLifeState>low</dd:ConsumableLifeState></ccdyn:ConsumableInfo>
</ccdyn:ConsumableConfigDyn>"""

CONFIG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<prdcfgdyn:ProductConfigDyn xmlns:prdcfgdyn="http://www.hp.com/schemas/imaging/con/ledm/productconfigdyn/2009/03/16" xmlns:dd="http://www.hp.com/schemas/imaging/con/dictionaries/1.0/">
<prdcfgdyn:ProductInformation><dd:MakeAndModel>HP OfficeJet Pro 9015 (fake)</dd:MakeAndModel><dd:SerialNumber>FAKE12345</dd:SerialNumber><dd:ProductNumber>1KR42A</dd:ProductNumber></prdcfgdyn:ProductInformation>
</prdcfgdyn:ProductConfigDyn>"""

USAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<pudyn:ProductUsageDyn xmlns:pudyn="http://www.hp.com/schemas/imaging/con/ledm/productusagedyn/2007/12/11" xmlns:dd="http://www.hp.com/schemas/imaging/con/dictionaries/1.0/">
<pudyn:PrinterSubunit><dd:TotalImpressions>12345</dd:TotalImpressions><dd:MonochromeImpressions>10000</dd:MonochromeImpressions><dd:ColorImpressions>2345</dd:ColorImpressions><dd:JamEvents>3</dd:JamEvents></pudyn:PrinterSubunit>
<pudyn:ScannerEngineSubunit><dd:ScanImages>678</dd:ScanImages></pudyn:ScannerEngineSubunit>
</pudyn:ProductUsageDyn>"""

CAPS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerCapabilities xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03" xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
<pwg:Version>2.63</pwg:Version><pwg:MakeAndModel>HP OfficeJet Pro 9015 (fake)</pwg:MakeAndModel>
<scan:Platen><scan:PlatenInputCaps><scan:SettingProfiles><scan:SettingProfile>
<scan:ColorModes><scan:ColorMode>BlackAndWhite1</scan:ColorMode><scan:ColorMode>Grayscale8</scan:ColorMode><scan:ColorMode>RGB24</scan:ColorMode></scan:ColorModes>
<scan:DocumentFormats><pwg:DocumentFormat>application/pdf</pwg:DocumentFormat><pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat></scan:DocumentFormats>
<scan:SupportedResolutions><scan:DiscreteResolutions><scan:DiscreteResolution><scan:XResolution>75</scan:XResolution><scan:YResolution>75</scan:YResolution></scan:DiscreteResolution><scan:DiscreteResolution><scan:XResolution>300</scan:XResolution><scan:YResolution>300</scan:YResolution></scan:DiscreteResolution><scan:DiscreteResolution><scan:XResolution>600</scan:XResolution><scan:YResolution>600</scan:YResolution></scan:DiscreteResolution></scan:DiscreteResolutions></scan:SupportedResolutions>
</scan:SettingProfile></scan:SettingProfiles></scan:PlatenInputCaps></scan:Platen>
<scan:Adf><scan:AdfSimplexInputCaps></scan:AdfSimplexInputCaps></scan:Adf>
</scan:ScannerCapabilities>"""

STATUS_SCAN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerStatus xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03" xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
<pwg:Version>2.63</pwg:Version><pwg:State>Idle</pwg:State><scan:AdfState>ScannerAdfEmpty</scan:AdfState></scan:ScannerStatus>"""

FAKE_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj trailer<</Root 1 0 R>>"


class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes = b"", ctype: str = "text/xml", extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path
        if STATE["sleeping"] and p.startswith("/DevMgmt"):
            STATE["sleeping"] = False  # any request wakes it
            cat, sid = "inPowerSave", "PowerSave"
        else:
            cat, sid = ("processing", "Printing") if STATE["printing"] else ("ready", "Ready")
        if p == "/DevMgmt/ProductStatusDyn.xml":
            alerts = "" if STATE["level_cmy"] > 10 else "<psdyn:AlertTable><psdyn:Alert><dd:AlertID xmlns:dd='x'>inkLow</dd:AlertID><dd:Severity xmlns:dd='x'>Warning</dd:Severity></psdyn:Alert></psdyn:AlertTable>"
            self._send(200, STATUS_XML.format(cat=cat, sid=sid, alerts=alerts).encode())
        elif p == "/DevMgmt/ConsumableConfigDyn.xml":
            self._send(200, CONSUMABLES_XML.format(k=STATE["level_k"], cmy=STATE["level_cmy"]).encode())
        elif p == "/DevMgmt/ProductConfigDyn.xml":
            self._send(200, CONFIG_XML.encode())
        elif p == "/DevMgmt/ProductUsageDyn.xml":
            self._send(200, USAGE_XML.encode())
        elif p == "/eSCL/ScannerCapabilities":
            self._send(200, CAPS_XML.encode())
        elif p == "/eSCL/ScannerStatus":
            self._send(200, STATUS_SCAN_XML.encode())
        elif p.startswith("/eSCL/ScanJobs/") and p.endswith("/NextDocument"):
            job = p.split("/")[3]
            n = STATE.setdefault("served", {}).get(job, 0)
            if n == 0:
                STATE["served"][job] = 1
                self._send(200, FAKE_PDF, "application/pdf")
            else:
                self._send(404)
        elif p == "/":
            self._send(200, b"<html><body>fake HP printer</body></html>", "text/html")
        else:
            self._send(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        if self.path == "/eSCL/ScanJobs":
            STATE["scans"] += 1
            STATE["last_scan_settings"] = body.decode("utf-8", "replace")
            self._send(201, b"", extra={"Location": f"/eSCL/ScanJobs/job{STATE['scans']}"})
        else:
            self._send(404)

    def do_DELETE(self):
        self._send(200)


class IppHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        req = ipp.decode_response(body)  # same wire format; status field = operation id
        op = req.status
        rid = req.request_id
        if op == ipp.GET_PRINTER_ATTRIBUTES:
            attrs = [
                ipp.Attr(ipp.T_CHARSET, "attributes-charset", ["utf-8"]),
                ipp.Attr(ipp.T_NATURAL_LANG, "attributes-natural-language", ["en"]),
            ]
            printer = [
                ipp.Attr(ipp.T_ENUM, "printer-state", [4 if STATE["printing"] else 3]),
                ipp.Attr(ipp.T_KEYWORD, "printer-state-reasons", ["marker-supply-low-warning"] if STATE["level_cmy"] <= 10 else ["none"]),
                ipp.Attr(ipp.T_TEXT, "printer-make-and-model", ["HP OfficeJet Pro 9015 (fake)"]),
                ipp.Attr(ipp.T_URI, "printer-uuid", ["urn:uuid:12345678-1234-1234-1234-123456789abc"]),
                ipp.Attr(ipp.T_BOOLEAN, "printer-is-accepting-jobs", [True]),
                ipp.Attr(ipp.T_INTEGER, "queued-job-count", [len(STATE["jobs"])]),
                ipp.Attr(ipp.T_INTEGER, "printer-up-time", [86400 * 3 + 3600]),
                ipp.Attr(ipp.T_TEXT, "printer-firmware-string-version", ["FAKE_1.0"]),
                ipp.Attr(ipp.T_NAME, "marker-names", ["Black ink", "Tri-colour ink"]),
                ipp.Attr(ipp.T_INTEGER, "marker-levels", [STATE["level_k"], STATE["level_cmy"]]),
                ipp.Attr(ipp.T_NAME, "marker-colors", ["#000000", "#00FFFF#FF00FF#FFFF00"]),
                ipp.Attr(ipp.T_KEYWORD, "marker-types", ["ink-cartridge", "ink-cartridge"]),
                ipp.Attr(ipp.T_KEYWORD, "media-ready", ["na_letter_8.5x11in"]),
                ipp.Attr(ipp.T_MIME, "document-format-supported", ["application/pdf", "image/jpeg", "application/octet-stream"]),
                ipp.Attr(ipp.T_KEYWORD, "sides-supported", ["one-sided", "two-sided-long-edge"]),
            ]
            out = ipp.encode_request(0x0000, rid, attrs)  # status successful-ok
            # replace the operation group tail with printer group: easier to build manually
            out = _build_response(0x0000, rid, attrs, printer)
        elif op == ipp.PRINT_JOB:
            fmt = ipp.first(req.group(ipp.OPERATION_ATTRS), "document-format")
            STATE["jobs"].append({"name": ipp.first(req.group(ipp.OPERATION_ATTRS), "job-name"), "format": fmt, "bytes": len(req.data)})
            attrs = [ipp.Attr(ipp.T_CHARSET, "attributes-charset", ["utf-8"]), ipp.Attr(ipp.T_NATURAL_LANG, "attributes-natural-language", ["en"])]
            job = [ipp.Attr(ipp.T_INTEGER, "job-id", [len(STATE["jobs"])]), ipp.Attr(ipp.T_ENUM, "job-state", [3]),
                   ipp.Attr(ipp.T_URI, "job-uri", [f"ipp://fake/jobs/{len(STATE['jobs'])}"])]
            out = _build_response(0x0000, rid, attrs, job, group_tag=ipp.JOB_ATTRS)
        else:
            attrs = [ipp.Attr(ipp.T_CHARSET, "attributes-charset", ["utf-8"]), ipp.Attr(ipp.T_NATURAL_LANG, "attributes-natural-language", ["en"]),
                     ipp.Attr(ipp.T_TEXT, "status-message", ["server-error-operation-not-supported"])]
            out = _build_response(0x0501, rid, attrs, [])
        self.send_response(200)
        self.send_header("Content-Type", "application/ipp")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def _build_response(status: int, rid: int, op_attrs, group_attrs, group_tag: int = ipp.PRINTER_ATTRS) -> bytes:
    # encode_request writes: header, op group, [job group], end. We want header, op group, printer group, end.
    head = ipp.encode_request(status, rid, op_attrs)  # ends with 0x03
    head = head[:-1]
    if group_attrs:
        body = ipp.encode_request(0, 0, [], group_attrs)  # header(8) + 0x01 + 0x02 + attrs + 0x03
        body = bytes([group_tag]) + body[10:]  # drop header and the two group tags, keep attrs + end
        return head + body
    return head + b"\x03"


def start(ipp_port: int = 0, web_port: int = 0):
    ipp_srv = ThreadingHTTPServer(("127.0.0.1", ipp_port), IppHandler)
    web_srv = ThreadingHTTPServer(("127.0.0.1", web_port), WebHandler)
    for s in (ipp_srv, web_srv):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    return ipp_srv, web_srv


if __name__ == "__main__":
    std = os.environ.get("FAKE_STD_PORTS") == "1"
    i, w = start(631 if std else 6631, 80 if std else 6080)
    print(f"fake printer: IPP on port {i.server_address[1]}, web/eSCL on port {w.server_address[1]}")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
