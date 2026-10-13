import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from homehub import escl, hp, ipp, oui  # noqa: E402
from homehub.config import Config  # noqa: E402
from homehub.network import DeviceStore  # noqa: E402
from homehub.testpage import test_page_pdf  # noqa: E402
import fake_printer  # noqa: E402


class IppWireTests(unittest.TestCase):
    def test_roundtrip(self):
        attrs = ipp.base_operation_attrs("ipp://1.2.3.4:631/ipp/print")
        attrs.append(ipp.Attr(ipp.T_KEYWORD, "requested-attributes", ["a", "b"]))
        job = [ipp.Attr(ipp.T_INTEGER, "copies", [3])]
        buf = ipp.encode_request(ipp.PRINT_JOB, 7, attrs, job, b"DATA")
        res = ipp.decode_response(buf)
        self.assertEqual(res.status, ipp.PRINT_JOB)
        self.assertEqual(res.request_id, 7)
        self.assertEqual(res.group(ipp.OPERATION_ATTRS)["requested-attributes"], ["a", "b"])
        self.assertEqual(res.group(ipp.JOB_ATTRS)["copies"], [3])
        self.assertEqual(res.data, b"DATA")

    def test_collections_and_odd_values(self):
        # A hand-built response with a collection, a range, a resolution and an out-of-band value
        body = bytearray(b"\x02\x00\x00\x00\x00\x00\x00\x01")
        body.append(ipp.PRINTER_ATTRS)
        def attr(tag, name, val):
            nonlocal body
            body.append(tag); body += len(name).to_bytes(2, "big") + name.encode(); body += len(val).to_bytes(2, "big") + val
        attr(ipp.T_BEG_COLLECTION, "media-col", b"")
        attr(ipp.T_MEMBER_NAME, "", b"media-size-name")
        attr(ipp.T_KEYWORD, "", b"na_letter")
        attr(ipp.T_END_COLLECTION, "", b"")
        attr(ipp.T_RANGE, "copies-supported", (1).to_bytes(4, "big") + (99).to_bytes(4, "big"))
        attr(ipp.T_RESOLUTION, "printer-resolution-default", (600).to_bytes(4, "big") + (600).to_bytes(4, "big") + b"\x03")
        attr(0x13, "printer-alert-description", b"")
        attr(ipp.T_INTEGER, "printer-state", (3).to_bytes(4, "big"))
        body.append(ipp.END_OF_ATTRS)
        res = ipp.decode_response(bytes(body))
        self.assertTrue(res.ok)
        p = res.printer
        self.assertEqual(p["media-col"], [{"media-size-name": "na_letter"}])
        self.assertEqual(p["copies-supported"], [[1, 99]])
        self.assertEqual(p["printer-resolution-default"][0]["x"], 600)
        self.assertEqual(p["printer-state"], [3])
        s = ipp.summarize_printer(p)
        self.assertEqual(s["state"], "idle")
        self.assertEqual(s["alerts"], [None])

    def test_summarize_supplies(self):
        p = {"printer-state": [5], "printer-state-reasons": ["media-empty-error", "none"],
             "marker-names": ["Black", "Color"], "marker-levels": [50, -2], "marker-colors": ["#000000", "#00FFFF"]}
        s = ipp.summarize_printer(p)
        self.assertEqual(s["state"], "stopped")
        self.assertEqual(s["state_reasons"], ["media-empty-error"])
        self.assertEqual(s["supplies"][0]["level"], 50)
        self.assertIsNone(s["supplies"][1]["level"])


class HpXmlTests(unittest.TestCase):
    def test_status(self):
        s = hp.parse_status(fake_printer.STATUS_XML.format(cat="inPowerSave", sid="x", alerts="").encode())
        self.assertTrue(s["sleeping"])
        self.assertEqual(s["label"], "Sleeping")

    def test_consumables(self):
        c = hp.parse_consumables(fake_printer.CONSUMABLES_XML.format(k=42, cmy=8).encode())
        self.assertEqual([(x["label"], x["level"]) for x in c], [("K", 42), ("CMY", 8)])

    def test_config_and_usage(self):
        self.assertEqual(hp.parse_config(fake_printer.CONFIG_XML.encode())["serial"], "FAKE12345")
        u = hp.parse_usage(fake_printer.USAGE_XML.encode())
        self.assertEqual(u["total_pages"], 12345)
        self.assertEqual(u["scans"], 678)

    def test_garbage(self):
        self.assertEqual(hp.parse_status(b"<html>nope"), {})
        self.assertEqual(hp.parse_consumables(b""), [])


class EsclTests(unittest.TestCase):
    def test_caps(self):
        c = escl.parse_capabilities(fake_printer.CAPS_XML.encode())
        self.assertEqual([s["id"] for s in c["sources"]], ["Platen", "Feeder"])
        self.assertEqual(c["resolutions"], [75, 300, 600])
        self.assertIn("RGB24", c["color_modes"])

    def test_settings_xml(self):
        x = escl.build_scan_settings("FeederDuplex", "Grayscale8", 200, "image/jpeg")
        self.assertIn("<scan:InputSource>Feeder</scan:InputSource>", x)
        self.assertIn("<scan:Duplex>true</scan:Duplex>", x)
        self.assertIn("<scan:XResolution>200</scan:XResolution>", x)


class MiscTests(unittest.TestCase):
    def test_pdf(self):
        pdf = test_page_pdf("Upstairs", "HP X", "1.2.3.4")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"(Upstairs", pdf) if b"Printer:  Upstairs" not in pdf else None
        self.assertIn(b"Printer:  Upstairs", pdf)

    def test_oui(self):
        self.assertEqual(oui.vendor_for("b8:27:eb:12:34:56"), "Raspberry Pi")
        self.assertEqual(oui.vendor_for("B8-27-EB-00-00-00"), "Raspberry Pi")
        self.assertIsNone(oui.vendor_for("00:00:00:00:00:00"))
        self.assertIsNone(oui.vendor_for(None))

    def test_oui_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "oui.csv"
            p.write_text('Registry,Assignment,Organization Name,Organization Address\nMA-L,AABBCC,"Widgets, Inc.",somewhere\n')
            self.assertEqual(oui.load_file(p), 1)
            self.assertEqual(oui.vendor_for("aa:bb:cc:00:11:22"), "Widgets")

    def test_config(self):
        with tempfile.TemporaryDirectory() as d:
            c = Config(Path(d) / "config.json")
            self.assertEqual(c.get("port"), 8080)
            c.set("secret", "deco", "password")
            c2 = Config(Path(d) / "config.json")
            self.assertEqual(c2.get("deco", "password"), "secret")
            self.assertEqual(c2.public()["deco"]["password"], "********")
            self.assertEqual(c2.get("network", "sweep_minutes"), 5)

    def test_device_store(self):
        with tempfile.TemporaryDirectory() as d:
            s = DeviceStore(Path(d) / "x.db")
            s.record([{"ip": "10.0.0.2", "mac": "aa:aa:aa:aa:aa:aa", "hostname": "pc", "vendor": "HP"}])
            s.record([])
            devs = s.all_devices()
            self.assertEqual(len(devs), 1)
            self.assertEqual(devs[0]["online"], 0)
            self.assertEqual(len(s.history("aa:aa:aa:aa:aa:aa")), 2)
            s.set_name("aa:aa:aa:aa:aa:aa", "Study PC")
            self.assertEqual(s.all_devices()[0]["name"], "Study PC")


class EndToEndTests(unittest.TestCase):
    """Spin up the fake printer and the real app, talk to both over HTTP."""

    @classmethod
    def setUpClass(cls):
        cls.ipp_srv, cls.web_srv = fake_printer.start()
        cls.ipp_port = cls.ipp_srv.server_address[1]
        cls.web_port = cls.web_srv.server_address[1]
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Path(cls.tmp.name) / "config.json"
        cfg.write_text(json.dumps({"network": {"enabled": False}, "oui_download": False, "printers": []}))
        from homehub.app import create_app
        from homehub.printers import Printer
        cls.app = create_app(cfg)
        pm = cls.app.state.printers
        p = Printer(id="fake", host="127.0.0.1", name="Fake", ipp_uri=f"ipp://127.0.0.1:{cls.ipp_port}/ipp/print",
                    scan_base=f"http://127.0.0.1:{cls.web_port}/eSCL")
        pm.printers["fake"] = p
        # The HP web API client assumes port 80; point it at the fake web port for the test.
        import homehub.printers as printers_mod
        orig = printers_mod.hp.HpWebApi
        class PatchedApi(orig):
            def __init__(self, host, timeout=5.0):
                super().__init__(f"{host}:{cls.web_port}", timeout)
        printers_mod.hp.HpWebApi = PatchedApi
        cls._orig_api = orig

    @classmethod
    def tearDownClass(cls):
        import homehub.printers as printers_mod
        printers_mod.hp.HpWebApi = cls._orig_api
        cls.ipp_srv.shutdown(); cls.web_srv.shutdown()
        cls.tmp.cleanup()

    def client(self):
        import httpx
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://hub")

    def run_async(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_status_wake_print_scan(self):
        async def go():
            async with self.client() as c:
                r = await c.post("/api/printers/fake/refresh")
                self.assertEqual(r.status_code, 200, r.text)
                v = r.json()
                self.assertEqual(v["state"], "attention")  # tri-colour at 8% -> low ink warning
                self.assertEqual(v["model"], "HP OfficeJet Pro 9015 (fake)")
                self.assertEqual([s["level"] for s in v["supplies"]], [42, 8])
                self.assertEqual(v["details"]["serial"], "FAKE12345")
                self.assertEqual(v["details"]["pages"]["total_pages"], 12345)

                fake_printer.STATE["level_cmy"] = 60
                fake_printer.STATE["sleeping"] = True
                v = (await c.post("/api/printers/fake/refresh")).json()
                self.assertEqual(v["state"], "sleeping")
                v = (await c.post("/api/printers/fake/refresh")).json()
                self.assertEqual(v["state"], "ready")

                r = await c.post("/api/printers/fake/testpage")
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(fake_printer.STATE["jobs"][-1]["format"], "application/pdf")

                r = await c.post("/api/printers/fake/print", files={"file": ("photo.jpg", b"\xff\xd8fakejpeg", "image/jpeg")}, data={"copies": "2"})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(fake_printer.STATE["jobs"][-1]["name"], "photo.jpg")
                self.assertEqual(fake_printer.STATE["jobs"][-1]["bytes"], len(b"\xff\xd8fakejpeg"))

                r = await c.post("/api/printers/fake/print", files={"file": ("doc.docx", b"PK..", "application/octet-stream")})
                self.assertEqual(r.status_code, 415)

                r = await c.get("/api/printers/fake/scanner")
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()["status"]["state"], "Idle")
                r = await c.post("/api/printers/fake/scan?source=Platen&color=Grayscale8&resolution=300&format=pdf")
                self.assertEqual(r.status_code, 200, r.text)
                self.assertTrue(r.content.startswith(b"%PDF"))
                self.assertIn('attachment; filename="scan_', r.headers["content-disposition"])
                self.assertIn("Grayscale8", fake_printer.STATE["last_scan_settings"])

                r = await c.patch("/api/printers/fake", json={"name": "Upstairs"})
                self.assertEqual(r.json()["name"], "Upstairs")
                r = await c.get("/api/overview")
                self.assertEqual(r.json()["printers"][0]["name"], "Upstairs")
                r = await c.get("/")
                self.assertIn(b"Home Hub", r.content)
        self.run_async(go())

    def test_offline_printer(self):
        async def go():
            from homehub.printers import Printer
            pm = self.app.state.printers
            pm.printers["dead"] = Printer(id="dead", host="127.0.0.2", name="Dead", ipp_uri="ipp://127.0.0.2:1/ipp/print")
            async with self.client() as c:
                v = (await c.post("/api/printers/dead/refresh")).json()
                self.assertEqual(v["state"], "offline")
                r = await c.post("/api/printers/dead/testpage")
                self.assertEqual(r.status_code, 502)
            pm.printers.pop("dead")
        self.run_async(go())


if __name__ == "__main__":
    unittest.main()
