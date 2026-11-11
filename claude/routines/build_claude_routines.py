#!/usr/bin/env python3
"""Build "Claude Routines.alfredworkflow": keyword cr <name> [text] fires that Claude Code routine on JV's seat
(fire.py + routines.json ship inside the workflow; tokens stay in the Keychain). Stdlib only."""
import io
import os
import plistlib
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Claude Routines.alfredworkflow")
KW, RS, NT, RO = (f"7C21{n}000-0000-4000-8000-0000000000{n}" for n in ("01", "02", "03", "04"))
RUN = '/usr/bin/python3 ./fire.py "$1" 2>&1 | tail -c 400\n'
RUN_OPEN = '/usr/bin/python3 ./fire.py --open "$1" 2>&1 | tail -c 400\n'
README = """Claude Routines: fire a Claude Code routine (scheduled task) on your seat from Alfred.

  cr ping hello  ↩     fires the "ping" routine with the text "hello", quietly (a Tink sound; errors still notify)
                 ⌘↩    same, and opens the run in claude.ai

ADD A ROUTINE
1. claude.ai/code/routines: create it, Trigger + API, Generate token (shown once).
2. Copy the token, then in the Terminal app (not Claude's ! prompt, which saves a blank):
   security add-generic-password -a "$USER" -s claude-routine-<name> -w "$(pbpaste)"; pbcopy </dev/null
3. Add <name> to routines.json (trigger id + keychain name; no secrets) and rebuild.

SAFE BY DESIGN
- Tokens live only in the Keychain; nothing secret is in this workflow or in git.
- Your text reaches the routine as untrusted data; each routine has one fixed job in its own instructions.
- Lost or leaked token: Regenerate (or Delete token) on the routine's page; it takes effect at once.
"""


def info():
    return {
        "bundleid": "com.dfensa.claude.routines",
        "category": "Productivity",
        "createdby": "DFENSA",
        "description": "cr <name> [text]: fire a Claude Code routine on your seat.",
        "disabled": False,
        "name": "Claude Routines",
        "readme": README,
        "version": "0.3",
        "variables": {},
        "objects": [
            {"uid": KW, "type": "alfred.workflow.input.keyword", "version": 1,
             "config": {"argumenttype": 0, "keyword": "cr", "subtext": "cr <name> [text]   ↩ quiet · ⌘↩ open the run",
                        "text": "Fire a Claude routine", "withspace": True}},
            {"uid": RS, "type": "alfred.workflow.action.script", "version": 2,
             "config": {"concurrently": False, "escaping": 102, "script": RUN, "scriptargtype": 1,
                        "scriptfile": "", "type": 0}},
            {"uid": RO, "type": "alfred.workflow.action.script", "version": 2,
             "config": {"concurrently": False, "escaping": 102, "script": RUN_OPEN, "scriptargtype": 1,
                        "scriptfile": "", "type": 0}},
            {"uid": NT, "type": "alfred.workflow.output.notification", "version": 1,
             "config": {"lastpathcomponent": False, "onlyshowifquerypopulated": True, "removeextension": False,
                        "text": "{query}", "title": "Claude Routines"}},
        ],
        "connections": {
            KW: [{"destinationuid": RS, "modifiers": 0, "modifiersubtext": "", "vitoclose": False},
                 {"destinationuid": RO, "modifiers": 1048576, "modifiersubtext": "Fire and open the run in claude.ai",
                  "vitoclose": False}],
            RS: [{"destinationuid": NT, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
            RO: [{"destinationuid": NT, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        },
        "uidata": {
            KW: {"xpos": 40.0, "ypos": 40.0, "note": "cr <name> [text]"},
            RS: {"xpos": 250.0, "ypos": 40.0, "note": "↩: fire.py quietly (token from Keychain, POST /fire)"},
            RO: {"xpos": 250.0, "ypos": 160.0, "note": "⌘↩: fire.py --open (also opens the run)"},
            NT: {"xpos": 460.0, "ypos": 40.0, "note": "Fired, or why not"},
        },
    }


def build(out=OUT):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zi = zipfile.ZipInfo("info.plist", date_time=(2026, 11, 10, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi, plistlib.dumps(info(), fmt=plistlib.FMT_XML, sort_keys=True))
        for name, mode in (("fire.py", 0o755), ("routines.json", 0o644)):
            with open(os.path.join(HERE, name), "rb") as fh:
                zr = zipfile.ZipInfo(name, date_time=(2026, 11, 10, 0, 0, 0))
                zr.compress_type = zipfile.ZIP_DEFLATED
                zr.external_attr = mode << 16
                zf.writestr(zr, fh.read())
    with open(out, "wb") as fh:
        fh.write(buf.getvalue())
    return out


if __name__ == "__main__":
    print(build())
