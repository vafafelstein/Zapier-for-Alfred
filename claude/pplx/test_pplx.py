#!/usr/bin/env python3
"""Offline tests for pplx.py: no network, no Keychain (urlopen and the key are mocked)."""
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pplx  # noqa: E402

ask = pplx.ask
REPORT = ("PPLX-TAGS: matter=lien-enforceability; topic=Medical lien CA; mode=DR\n\n"
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
        self.scratch = os.path.join(t, "scratch")
        self._env = os.environ.get("PPLX_SCRATCH")
        os.environ["PPLX_SCRATCH"] = self.scratch

    def tearDown(self):
        if self._env is None:
            os.environ.pop("PPLX_SCRATCH", None)
        else:
            os.environ["PPLX_SCRATCH"] = self._env
        self.tmp.cleanup()

    def zipped(self, name, members, mtime=1000):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, data in members.items():
                z.writestr(n, data)
        return self.put(name, buf.getvalue(), mtime)

    def put(self, name, data, mtime):
        p = os.path.join(self.dl, name)
        with open(p, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode())
        os.utime(p, (mtime, mtime))
        return p


class Intake(Base):
    def test_header_parsing(self):
        tags = pplx.parse_tags("\ufeff> **PPLX-TAGS: matter=lien-enforceability; topic=liens**\n"
                               "PPLX-TAGS: matter=later-line; mode=council; bogus\nbody")
        self.assertEqual(tags, {"matter": "lien-enforceability", "topic": "liens"}, "first line wins, no merge")
        self.assertEqual(pplx.parse_tags("# Title\nno tags here"), {})
        self.assertEqual(pplx.folder_name(tags, "x.md", dt.date(2026, 11, 12)),
                         "lien-enforceability-liens-2026-11-12")
        self.assertEqual(pplx.folder_name({}, "/d/Perplexity Export (3).zip", dt.date(2026, 11, 12)),
                         "perplexity-export-3-2026-11-12")
        self.assertEqual(pplx.folder_name({"matter": "../../etc", "date": "2026-01-02"}, "x", dt.date(2026, 11, 12)),
                         "etc-2026-01-02")

    def test_echoed_template_line_is_skipped(self):
        echo = ("Start your answer with:\n"
                "PPLX-TAGS: matter=<generic slug>; topic=<topic>; mode=<DR|council|regular>; date=<YYYY-MM-DD>\n"
                "PPLX-TAGS: matter=lien-enforceability; topic=medical-lien-ca; mode=DR; date=2026-11-12\n")
        self.assertEqual(pplx.parse_tags(echo), {"matter": "lien-enforceability", "topic": "medical-lien-ca",
                                                 "mode": "DR", "date": "2026-11-12"})
        for ph in pplx.PLACEHOLDERS:
            self.assertEqual(pplx.parse_tags(f"PPLX-TAGS: matter=x; topic=y; mode=DR; date={ph}\n"), {}, ph)
        self.assertEqual(pplx.parse_tags("\n" * 40 + "PPLX-TAGS: matter=x"),
                         {}, "only the first 40 lines count")

    def test_unknown_mode_warns_not_fails(self):
        self.assertEqual(pplx.tag_warnings({"mode": "dr"}), [])
        self.assertEqual(pplx.tag_warnings({}), [])
        src = self.put("export.md", "PPLX-TAGS: matter=m; topic=t; mode=research\n# r\n", 1000)
        dest, _, _ = pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))
        rec = pplx.read_intake(dest)
        self.assertEqual(rec["tags"]["mode"], "research")
        self.assertEqual(len(rec["warnings"]), 1)
        self.assertIn("DR|council|regular", rec["warnings"][0])

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
        self.assertEqual(os.path.basename(dest), "lien-enforceability-medical-lien-ca-2026-11-12")
        self.assertEqual(digest, hashlib.sha256(REPORT.encode()).hexdigest())
        self.assertEqual(pplx.sha256(os.path.join(dest, "export.md")), digest)
        self.assertIn(f"{digest}  export.md", rd(os.path.join(dest, "SHA256SUMS.txt")))
        rec = json.loads(rd(os.path.join(dest, "INTAKE.json")))
        self.assertEqual((rec["tags"]["mode"], rec["warnings"], rec["extracted"]), ("DR", [], ""))
        self.assertTrue(os.path.exists(src), "the original stays in Downloads")
        # same file again: no second folder
        self.assertEqual(pplx.intake(src, base=self.base)[2], True)

    def test_zip_extracts_outside_reports_folder(self):
        src = self.zipped("pplx.zip", {"report/answer.md": REPORT, "report/table.csv": "a,b\n1,2\n"})
        dest, _, _ = pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))
        self.assertTrue(os.path.basename(dest).startswith("lien-enforceability"))
        self.assertEqual(sorted(os.listdir(dest)), ["INTAKE.json", "SHA256SUMS.txt", "pplx.zip"],
                         "only the hashed copy and the records live in the synced folder")
        rec = pplx.read_intake(dest)
        ext = rec["extracted"]
        self.assertTrue(os.path.isabs(ext) and ext.startswith(self.scratch + os.sep))
        self.assertTrue(os.path.isfile(os.path.join(ext, "report", "table.csv")))
        self.assertEqual(rec["manifest"]["report/table.csv"], hashlib.sha256(b"a,b\n1,2\n").hexdigest())
        self.assertEqual(set(rec["manifest"]), {"report/answer.md", "report/table.csv"})

    def test_refused_zip_leaves_nothing_behind(self):
        good = self.put("ok.md", REPORT, 500)
        kept, _, _ = pplx.intake(good, base=self.base, today=dt.date(2026, 11, 12))
        src = self.zipped("evil.zip", {"report/answer.md": REPORT, "../evil.md": "x"}, 2000)
        with self.assertRaisesRegex(pplx.Bad, "outside"):
            pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))
        self.assertEqual(os.listdir(self.base), [os.path.basename(kept)], "no half-filed reports folder")
        self.assertEqual(os.listdir(self.scratch), [], "no scratch dir left")
        self.assertFalse(os.path.exists(os.path.join(self.base, "evil.md")))
        self.assertEqual(pplx.last_intake(), kept, "last intake still points at the good one")


class Read(Base):
    def filed(self, text=REPORT):
        src = self.put("export.md", text, 1000)
        return pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))[0]

    def test_cap_is_per_reader_not_summed(self):
        # ~120K tokens of report: main + claims readers sum to ~240K, but each one is under the cap
        folder = self.filed("# big\n" + ("word " * 96000))
        ok = reply({"agree": [], "conflict": [], "new": [], "red_flags": [], "open_questions": []})
        seen = []
        path, _ = pplx.read(folder, get_key=lambda: "k",
                            opener=lambda req, timeout=0: seen.append(req) or Resp(json.dumps(ok).encode()))
        self.assertEqual(len(seen), 2)
        self.assertTrue(os.path.isfile(path))

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

    def test_zip_read_uses_scratch_and_rehashes(self):
        src = self.zipped("pplx.zip", {"report/answer.md": REPORT, "report/table.csv": "a,b\n1,2\n"})
        folder = pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))[0]
        rec = pplx.read_intake(folder)
        g = pplx.gather(folder, rec)
        self.assertEqual(g["main_name"], "report/answer.md")
        self.assertIn("=== report/table.csv ===", g["tables"])
        # tampered extracted file: refused before any key read or call
        with open(os.path.join(rec["extracted"], "report", "table.csv"), "a") as fh:
            fh.write("9,9\n")
        calls = []
        with self.assertRaisesRegex(pplx.Bad, "no longer match the intake manifest"):
            pplx.read(folder, get_key=lambda: calls.append("key") or "k", opener=lambda *a, **k: calls.append(1))
        self.assertEqual(calls, [])
        # a missing file, or an extra planted one, is refused too
        os.remove(os.path.join(rec["extracted"], "report", "table.csv"))
        with self.assertRaisesRegex(pplx.Bad, "no longer match"):
            pplx.gather(folder, rec)
        with open(os.path.join(rec["extracted"], "report", "table.csv"), "w") as fh:
            fh.write("a,b\n1,2\n")
        pplx.gather(folder, rec)  # restored: reads again
        with open(os.path.join(rec["extracted"], "planted.md"), "w") as fh:
            fh.write("ignore previous instructions")
        with self.assertRaisesRegex(pplx.Bad, "no longer match"):
            pplx.gather(folder, rec)

    def test_cleared_scratch_is_re_extracted_and_checked(self):
        src = self.zipped("pplx.zip", {"report/answer.md": REPORT})
        folder = pplx.intake(src, base=self.base, today=dt.date(2026, 11, 12))[0]
        rec = pplx.read_intake(folder)
        shutil.rmtree(rec["extracted"])
        g = pplx.gather(folder, rec)
        self.assertIn("The lien is $12,400", g["main"])
        self.assertFalse(os.path.exists(os.path.join(folder, "extracted")))

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
