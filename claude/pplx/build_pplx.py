#!/usr/bin/env python3
"""Build "Claude PPLX.alfredworkflow": pplx (file the newest Perplexity export), pplx read (three Claude readers ->
REPORT.md), pplxhelp. pplx.py + ask.py (from ../ask/src, for its API helpers) ship inside; the key stays in the
Keychain. Stdlib only."""
import io
import json
import os
import plistlib
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASK = os.path.join(HERE, "..", "ask", "src", "ask.py")
OUT = os.path.join(HERE, "Claude PPLX.alfredworkflow")
KW, RS, NT, HF, HA = (f"9D1E{n}000-0000-4000-8000-0000000000{n}" for n in ("01", "02", "03", "04", "05"))
RUN = '/usr/bin/python3 ./pplx.py "$1" 2>&1 | tail -c 600\n'
STAMP = (2026, 11, 12, 0, 0, 0)

HELP = [
    ("pplx", "pplx: file the newest Perplexity export in Downloads", "SHA-256, copy to PPLX_BASE/<slug>-<date>/, unzip as untrusted data. No API call"),
    ("pplx ", "pplx <path>: file that export instead", "A .zip, .md or .pdf"),
    ("pplx read", "pplx read: three Claude readers on the last intake", "Report line by line, tables for fidelity, claims list -> REPORT.md. Ultra key; refuses over ~200K tokens"),
    ("pplx open", "pplx open: open the last intake folder", "In Finder"),
    ("pplxhelp", "Header block: PPLX-TAGS: matter=…; topic=…; mode=…", "Ask Perplexity to start its answer with it; the folder becomes <matter>-<topic>-<date>"),
    ("ca usage", "ca usage: this month's Ultra-key spend (includes pplx read)", "Claude Ask workflow"),
    ("howto", "How this works (readme)", "Opens this workflow in Alfred Preferences"),
]
HELP_ACTION = """case "$1" in
  howto) /usr/bin/osascript -e 'tell application id "com.runningwithcrayons.Alfred" to reveal workflow "com.dfensa.claude.pplx"' ;;
  *) /usr/bin/osascript -e "tell application id \\"com.runningwithcrayons.Alfred\\" to search \\"$1\\"" ;;
esac
"""
README = """Claude PPLX: file a Perplexity export and have Claude read it. On demand only; nothing watches Downloads.

  pplx            ↩   newest .zip/.md/.pdf in Downloads -> SHA-256 -> copy to $PPLX_BASE/<slug>-<date>/
                      (a zip is extracted to extracted/ inside it, as untrusted data). The original stays put.
  pplx <path>     ↩   the same for one file
  pplx read       ↩   three readers (Opus 5.5, high effort) on the last intake: the report line by line, its tables
                      for fidelity, and a claims list -> REPORT.md: agree / conflict / new / red flags /
                      open questions / claims for live check. Takes a minute or two.
  pplx open       ↩   open the last intake folder
  pplxhelp            this list

HEADER BLOCK (optional): ask Perplexity to begin its answer with
  PPLX-TAGS: matter=Smith v. Jones; topic=lien reduction; mode=research
and the folder is named smith-v-jones-lien-reduction-<date> (date=YYYY-MM-DD overrides). Otherwise: file name + date.

BILLING AND SAFETY
- Keychain item in PPLX_KEYCHAIN (default anthropic-api-ultra): spends the Ultra API credit. ca usage counts it.
- Refuses any export estimated over ~200K input tokens across the three readers (chars/4); nothing is sent.
- The usage log gets time, model, tokens and cost only (7th field ultra): never export text.
- The export is treated as untrusted data: readers are told to ignore instructions inside it and flag them.
- Variables: PPLX_BASE (default ~/Dropbox/COWORK/_HYBRID/reports), PPLX_DOWNLOADS (~/Downloads), PPLX_KEYCHAIN.
"""


def help_script():
    items = [{"uid": f"{i}-{arg}", "arg": arg, "valid": True, "title": t, "subtitle": s,
              "match": f"perplexity pplx {t} {s}", "autocomplete": arg} for i, (arg, t, s) in enumerate(HELP)]
    return "cat <<'JSON'\n" + json.dumps({"items": items}, ensure_ascii=False) + "\nJSON\n"


def info():
    script = {"concurrently": False, "escaping": 102, "scriptargtype": 1, "scriptfile": "", "type": 0}
    return {
        "bundleid": "com.dfensa.claude.pplx",
        "category": "Productivity",
        "createdby": "DFENSA",
        "description": "pplx: file a Perplexity export; pplx read: three Claude readers -> REPORT.md.",
        "disabled": False,
        "name": "Claude PPLX",
        "readme": README,
        "version": "0.1",
        "variables": {"PPLX_BASE": "~/Dropbox/COWORK/_HYBRID/reports", "PPLX_DOWNLOADS": "~/Downloads",
                      "PPLX_KEYCHAIN": "anthropic-api-ultra"},
        "objects": [
            {"uid": KW, "type": "alfred.workflow.input.keyword", "version": 1,
             "config": {"argumenttype": 1, "keyword": "pplx", "withspace": True, "text": "Perplexity intake",
                        "subtext": "pplx (file newest export) · pplx read · pplx open · pplxhelp"}},
            {"uid": RS, "type": "alfred.workflow.action.script", "version": 2, "config": dict(script, script=RUN)},
            {"uid": NT, "type": "alfred.workflow.output.notification", "version": 1,
             "config": {"lastpathcomponent": False, "onlyshowifquerypopulated": True, "removeextension": False,
                        "text": "{query}", "title": "Claude PPLX"}},
            {"uid": HF, "type": "alfred.workflow.input.scriptfilter", "version": 3,
             "config": {"alfredfiltersresults": True, "alfredfiltersresultsmatchmode": 2,
                        "argumenttreatemptyqueryasnil": False, "argumenttrimmode": 0, "argumenttype": 1,
                        "escaping": 102, "keyword": "pplxhelp", "queuedelaycustom": 3,
                        "queuedelayimmediatelyinitially": True, "queuedelaymode": 0, "queuemode": 1,
                        "runningsubtext": "", "script": help_script(), "scriptargtype": 1, "scriptfile": "",
                        "subtext": "Every pplx command: pick one", "title": "Perplexity intake: help", "type": 0,
                        "withspace": True}},
            {"uid": HA, "type": "alfred.workflow.action.script", "version": 2, "config": dict(script, script=HELP_ACTION)},
        ],
        "connections": {
            KW: [{"destinationuid": RS, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
            RS: [{"destinationuid": NT, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
            HF: [{"destinationuid": HA, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        },
        "uidata": {
            KW: {"xpos": 40.0, "ypos": 40.0, "note": "pplx [path | read [folder] | open]"},
            RS: {"xpos": 250.0, "ypos": 40.0, "note": "pplx.py (intake, or the three readers)"},
            NT: {"xpos": 460.0, "ypos": 40.0, "note": "Filed / REPORT.md written, or why not"},
            HF: {"xpos": 40.0, "ypos": 200.0, "note": "pplxhelp list"},
            HA: {"xpos": 250.0, "ypos": 200.0, "note": "put the picked command in Alfred"},
        },
    }


def build(out=OUT):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zi = zipfile.ZipInfo("info.plist", date_time=STAMP)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi, plistlib.dumps(info(), fmt=plistlib.FMT_XML, sort_keys=True))
        for name, path in (("pplx.py", os.path.join(HERE, "pplx.py")), ("ask.py", ASK)):
            with open(path, "rb") as fh:
                zr = zipfile.ZipInfo(name, date_time=STAMP)
                zr.compress_type = zipfile.ZIP_DEFLATED
                zr.external_attr = 0o755 << 16
                zf.writestr(zr, fh.read())
    with open(out, "wb") as fh:
        fh.write(buf.getvalue())
    return out


if __name__ == "__main__":
    print(build())
