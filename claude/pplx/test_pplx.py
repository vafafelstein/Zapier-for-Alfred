#!/usr/bin/env python3
"""Offline tests for pplx.py: no network, no Keychain (urlopen and the key are mocked)."""
import datetime as dt
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pplx  # noqa: E402

ask = pplx.ask
REPORT = ("PPLX-TAGS: matter=Smith v. Jones; topic=Lien reduction; mode=research\n\n"
          "# Medi-Cal lien reduction\n\nThe lien is $12,400 (Welf. & Inst. Code 14124.76).\n\n"
          "| item | amount |\n|---|---|\n| lien | 12,400 |\n| fee | 3,000 |\n")


def rd(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def reply(obj):
    return {"model": "claude-opus-5-5", "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "```json\n" + json.dumps(obj) + "\n```"}],
            "usage": {"input_tokens": 2000, "output_tokens": 400}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.dl, self.base = os.path.join(t, "Downloads"), os.path.join(t, "reports")
        os.makedirs(self.dl)
        pplx.STATE, pplx.LAST = os.path.join(t, "state"), os.path.join(t, "state", "last_intake.txt")
        ask.STATE, ask.LOG = os.path.join(t, "ca"), os.path.join(t, "ca", "usage.log")

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, data, mtime):
        p = os.path.join(self.dl, name)
        with open(p, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode())
        os.utime(p, (mtime, mtime))
        return p


class Intake(Base):
    def test_header_parsing(self):
        tags = pplx.parse_tags("\ufeff> **PPLX-TAGS: matter=Smith v. Jones; topic=liens**\nPPLX-TAGS: mode=deep; bogus\nbody")
        self.assertEqual(tags, {"matter": "Smith v. Jones", "topic": "liens", "mode": "deep"})
        self.assertEqual(pplx.parse_tags("# Title\nno tags here"), {})
        self.assertEqual(pplx.folder_name(tags, "x.md", dt.date(2026, 11, 12)), "smith-v-jones-liens-2026-11-12")
        self.assertEqual(pplx.folder_name({}, "/d/Perplexity Export (3).zip", dt.date(2026, 11, 12)),
                         "perplexity-export-3-2026-11-12")
        self.assertEqual(pplx.folder_name({"matter": "../../etc", "date": "2026-01-02"}, "x", dt.date(2026, 11, 12)),
                         "etc-2026-01-02")

    def test_newest_file_pick(self):
        self.put("old.md", "a", 1000)
        self.put("new.pdf", b"%PDF", 3000)
        self.put("newer.docx", "x", 5000)
        self.put(".hidden.md", "x", 6000)
        self.put("mid.zip", b"PK", 2000)
        self.assertTrue(pplx.newest_export(self.dl).endswith("new.pdf"))
        with self.assertRaises(pplx.Bad):
            pplx.newest_export(os.path.join(self.tmp.name, "empty-nope"))

    def test_hash_copy_and_tags(self):
        src = self.put("export.md", REPORT, 1000)
        dest, digest, dup = pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))
        self.assertFalse(dup)
        self.assertEqual(os.path.basename(dest), "smith-v-jones-lien-reduction-2026-11-12")
        self.assertEqual(digest, hashlib.sha256(REPORT.encode()).hexdigest())
        self.assertEqual(pplx.sha256(os.path.join(dest, "export.md")), digest)
        self.assertIn(f"{digest}  export.md", rd(os.path.join(dest, "SHA256SUMS.txt")))
        rec = json.loads(rd(os.path.join(dest, "INTAKE.json")))
        self.assertEqual(rec["tags"]["mode"], "research")
        self.assertTrue(os.path.exists(src), "the original stays in Downloads")
        # same file again: no second folder
        self.assertEqual(pplx.intake(src, base=self.base)[2], True)

    def test_zip_extracts_fresh_and_refuses_traversal(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("report/answer.md", REPORT)
            z.writestr("report/table.csv", "a,b\n1,2\n")
        src = self.put("pplx.zip", buf.getvalue(), 1000)
        dest, _, _ = pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))
        self.assertTrue(os.path.basename(dest).startswith("smith-v-jones"))
        self.assertTrue(os.path.isfile(os.path.join(dest, "extracted", "report", "table.csv")))
        bad = io.BytesIO()
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("../evil.md", "x")
        src2 = self.put("evil.zip", bad.getvalue(), 2000)
        with self.assertRaisesRegex(pplx.Bad, "outside"):
            pplx.intake(src2, base=self.base)
        self.assertFalse(os.path.exists(os.path.join(self.base, "evil.md")))


class Read(Base):
    def filed(self, text=REPORT):
        src = self.put("export.md", text, 1000)
        return pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))[0]

    def test_cap_refusal_sends_nothing(self):
        folder = self.filed(REPORT + ("word " * 200000))
        calls = []
        with self.assertRaisesRegex(pplx.Bad, "refused.*cap 200,000.*Nothing was sent"):
            pplx.read(folder, get_key=lambda: calls.append("key") or "k", opener=lambda *a, **k: calls.append(1))
        self.assertEqual(calls, [])

    def test_report_shape_and_requests(self):
        folder = self.filed()
        seen = []
        answers = [
            reply({"agree": ["lien amount stated twice consistently"], "conflict": [], "new": ["lien $12,400"],
                   "red_flags": ["14124.76 cited without pin"], "open_questions": ["current lien balance?"]}),
            reply({"agree": [], "conflict": ["table has no total"], "new": [], "red_flags": [], "open_questions": []}),
            reply({"agree": [], "conflict": [], "new": [], "red_flags": [], "open_questions": [],
                   "claims": [{"claim": "Lien is $12,400", "where": "L0005", "source": "none", "check": "DHCS letter"}]}),
        ]

        def opener(req, timeout=0):
            seen.append(req)
            return Resp(json.dumps(answers[len(seen) - 1]).encode())

        path, spent = pplx.read(folder, get_key=lambda: "sk-test", opener=opener,
                                now=dt.datetime(2026, 11, 12, 9, tzinfo=dt.timezone.utc))
        self.assertEqual(len(seen), 3)
        body = json.loads(seen[0].data)
        self.assertEqual(body["model"], ask.MODEL)
        self.assertEqual(body["output_config"], {"effort": "high"})
        self.assertEqual(body["fallbacks"], "default")
        self.assertIn("L0005: The lien is $12,400", body["messages"][0]["content"][0]["text"])
        self.assertIn("<tables>", json.loads(seen[1].data)["messages"][0]["content"][0]["text"])
        h = {k.lower(): v for k, v in seen[0].header_items()}
        self.assertEqual((h["x-api-key"], h["anthropic-version"]), ("sk-test", ask.VERSION))
        md = rd(path)
        heads = [l for l in md.splitlines() if l.startswith("## ")]
        self.assertEqual(heads, ["## Agree", "## Conflict", "## New", "## Red flags", "## Open questions",
                                 "## Claims for live check"])
        self.assertIn("- [tables] table has no total", md)
        self.assertIn("- [ ] Lien is $12,400 (L0005) · source: none · check: DHCS letter", md)
        log = rd(ask.LOG).splitlines()
        self.assertEqual(len(log), 3)
        self.assertTrue(all(l.split("\t")[6] == "ultra" for l in log))
        self.assertNotIn("12,400", "\n".join(log))
        self.assertGreater(spent, 0)

    def test_pdf_goes_as_document_block(self):
        pdf = b"%PDF-1.4\n1 0 obj<</Type /Pages>>\n2 0 obj<</Type /Page>>\n3 0 obj<</Type/Page>>\n%%EOF"
        src = self.put("answer.pdf", pdf, 1000)
        folder = pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))[0]
        g = pplx.gather(folder, pplx.read_intake(folder))
        self.assertEqual(pplx.pdf_pages(g["pdf"]), 2)
        self.assertEqual(pplx.est_tokens(g), (4000, 0))
        block = pplx.content_for("main", g)[0]
        self.assertEqual((block["type"], block["source"]["media_type"]), ("document", "application/pdf"))

    def test_tampered_copy_is_refused(self):
        folder = self.filed()
        with open(os.path.join(folder, "export.md"), "a") as fh:
            fh.write("tampered")
        with self.assertRaisesRegex(pplx.Bad, "no longer matches"):
            pplx.read(folder, get_key=lambda: "k", opener=None)

    def test_non_json_reply_is_reported_not_lost(self):
        folder = self.filed("# plain\nno tables\n")
        raw = {"model": "claude-opus-5-5", "stop_reason": "end_turn",
               "content": [{"type": "text", "text": "Sorry, prose."}], "usage": {"input_tokens": 1, "output_tokens": 1}}
        path, _ = pplx.read(folder, get_key=lambda: "k", opener=lambda req, timeout=0: Resp(json.dumps(raw).encode()))
        md = rd(path)
        self.assertIn("## Reader problems", md)
        self.assertNotIn("[tables]", md)  # no tables: that reader is skipped
        self.assertEqual(len(json.loads(rd(os.path.join(folder, "READERS.json")))), 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
