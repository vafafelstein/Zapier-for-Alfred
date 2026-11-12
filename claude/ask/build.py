#!/usr/bin/env python3
"""Build Claude-Ask.alfredworkflow: keyword `ca` (↩ quick, ⌘↩ deeper) and `cahelp` (pick-a-command list)."""
import json
import os
import plistlib
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Claude-Ask.alfredworkflow")

KS, SP = ("CA000012-0000-4000-8000-000000000012", "CA000013-0000-4000-8000-000000000013")
KC, C1 = ("CA000010-0000-4000-8000-000000000010", "CA000011-0000-4000-8000-000000000011")
KF, F1, F2 = ("CA000007-0000-4000-8000-000000000007", "CA000008-0000-4000-8000-000000000008", "CA000009-0000-4000-8000-000000000009")
K, S1, S2, N, H, HA = ("CA000001-0000-4000-8000-000000000001", "CA000002-0000-4000-8000-000000000002",
                       "CA000003-0000-4000-8000-000000000003", "CA000004-0000-4000-8000-000000000004",
                       "CA000005-0000-4000-8000-000000000005", "CA000006-0000-4000-8000-000000000006")

HELP = [
    ("ca", "ca <question>: quick answer from Claude (↩)", "Opus 5.5, low effort. Answer → clipboard + notification. Spends the Ultra $200 API credit"),
    ("ca", "ca <question> then ⌘↩: deeper answer", "Opus 5.5, high effort. Slower, a few cents more"),
    ("ca test", "ca test: check the Ultra API key works", "Free call (GET /v1/models). 'key OK (HTTP 200)' means good"),
    ("ca usage", "ca usage: this month's estimated spend", "From ~/.config/claude_ca/usage.log (no questions or answers are logged)"),
    ("ca last", "ca last: open the last full answer", "Opens ~/.config/claude_ca/last.md in TextEdit"),
    ("caf", "caf <question>: same, on the FIRM API key", "For firm work. Spends the firm Console balance; caf usage counts it separately"),
    ("cac ", "cac <instruction>: rewrite the copied text (firm key)", "Copy text, then e.g. cac fix grammar / cac firmer for the adjuster / cac Spanish. Result replaces the clipboard"),
    ("cac undo", "cac undo: put the original copied text back", "Restores what was on the clipboard before the last cac"),
    ("spel", "spel: fix spelling + grammar of the copied text", "Same as cac g. Keeps your wording and tone"),
    ("cac ", "cac presets: g · firm · polite · short · bullets · email · es · en · note", "e.g. copy, then cac es (Spanish for the client) or cac email (notes → email)"),
    ("caf test", "caf test: check the firm API key works", "Free call (GET /v1/models)"),
    ("caf usage", "caf usage: this month's firm-key spend", "Same log, firm entries only"),
    ("cr", "cr <name> [text]: fire a Claude routine", "Claude Routines workflow. Bills PLAN usage, not the API credit"),
    ("ghrun", "ghrun: run the GitHub requests Claude sessions queued", "You read each one, then ↩ runs it"),
    ("dockethelp", "dockethelp: the Westlaw docket commands", "Westlaw Docket workflow"),
    ("howto", "How this works (readme)", "Opens this workflow in Alfred Preferences"),
]


def help_script():
    items = [{"uid": f"{i}-{arg}", "arg": arg, "valid": True, "title": t, "subtitle": s,
              "match": f"claude {t} {s}", "autocomplete": arg} for i, (arg, t, s) in enumerate(HELP)]
    return "cat <<'JSON'\n" + json.dumps({"items": items}, ensure_ascii=False) + "\nJSON\n"


HELP_ACTION = """case "$1" in
  howto) /usr/bin/osascript -e 'tell application id "com.runningwithcrayons.Alfred" to reveal workflow "com.dfensa.claude.ask"' ;;
  *) /usr/bin/osascript -e "tell application id \\"com.runningwithcrayons.Alfred\\" to search \\"$1 \\"" ;;
esac
"""

README = """Claude Ask: quick Claude answers from Alfred on your Ultra API key.

  ca what is the CCP 998 acceptance window   ↩   quick answer (Opus 5.5, low effort) → clipboard + notification
                                             ⌘↩  deeper answer (high effort)
  ca test     check the key (free)          ca usage   this month's estimated spend          ca last   open the last answer
  cahelp      every Claude command in one list (ca, cr, ghrun, dockethelp)

BILLING
- Uses the Keychain item anthropic-api-ultra (Ultra org, Default workspace). Spends the $200 monthly API credit,
  which expires each cycle. With auto-reload off it simply stops at zero; nothing is charged to the plan.
- caf <question> does the same on the FIRM key (anthropic-api-firm), billed to the firm Console balance;
  caf usage / ca usage count each key separately. Use caf for firm and client work, ca for your own.
- cac <instruction> rewrites whatever you copied (firm key) and puts the result on the clipboard; cac undo
  restores the original (kept in ~/.config/claude_ca/clip-undo.txt, owner-only, overwritten each time).
- cr (Claude Routines) is different: it bills plan usage.

SAFE BY DESIGN
- The key lives only in the Keychain; nothing secret is in this workflow.
- The log keeps time, model, effort, tokens and estimated cost only: never your question or the answer.
- API traffic falls under Anthropic's Commercial Terms (no training; deleted within 30 days).
- Answers are a starting point: any case or statute it names still needs checking.
"""


def obj(uid, typ, config, version):
    return {"uid": uid, "type": typ, "version": version, "config": config}


def script(cmd):
    return {"concurrently": False, "escaping": 102, "script": cmd, "scriptargtype": 1, "scriptfile": "", "type": 0}


plist = {
    "bundleid": "com.dfensa.claude.ask", "name": "Claude Ask", "createdby": "DFENSA", "version": "0.4",
    "description": "ca <question>: ask Claude on the Ultra API key; caf on the firm key. cahelp lists every Claude command.",
    "disabled": False, "readme": README, "variables": {"CA_KEYCHAIN": "anthropic-api-ultra"},
    "objects": [
        obj(K, "alfred.workflow.input.keyword",
            {"argumenttype": 0, "keyword": "ca", "withspace": True, "text": "Ask Claude",
             "subtext": "ca <question>   ↩ quick · ⌘↩ deeper · ca test · ca usage · ca last · cahelp"}, 1),
        obj(S1, "alfred.workflow.action.script", script('/usr/bin/python3 ./ask.py "$1" 2>&1 | tail -c 600\n'), 2),
        obj(S2, "alfred.workflow.action.script", script('/usr/bin/python3 ./ask.py --deep "$1" 2>&1 | tail -c 600\n'), 2),
        obj(KF, "alfred.workflow.input.keyword",
            {"argumenttype": 0, "keyword": "caf", "withspace": True, "text": "Ask Claude (firm key)",
             "subtext": "caf <question>   ↩ quick · ⌘↩ deeper · caf test · caf usage  (spends the firm Console balance)"}, 1),
        obj(F1, "alfred.workflow.action.script", script('CA_KEYCHAIN=anthropic-api-firm /usr/bin/python3 ./ask.py "$1" 2>&1 | tail -c 600\n'), 2),
        obj(F2, "alfred.workflow.action.script", script('CA_KEYCHAIN=anthropic-api-firm /usr/bin/python3 ./ask.py --deep "$1" 2>&1 | tail -c 600\n'), 2),
        obj(KC, "alfred.workflow.input.keyword",
            {"argumenttype": 0, "keyword": "cac", "withspace": True, "text": "Rewrite the copied text (firm key)",
             "subtext": "cac <what to do>   e.g. fix grammar · firmer · 3 bullets · Spanish   ·   cac undo"}, 1),
        obj(C1, "alfred.workflow.action.script", script('CA_KEYCHAIN=anthropic-api-firm /usr/bin/python3 ./ask.py --clip "$1" 2>&1 | tail -c 400\n'), 2),
        obj(KS, "alfred.workflow.input.keyword",
            {"argumenttype": 2, "keyword": "spel", "withspace": False, "text": "Fix spelling + grammar of the copied text",
             "subtext": "Copy text first. Result replaces the clipboard · cac undo restores it"}, 1),
        obj(SP, "alfred.workflow.action.script", script('CA_KEYCHAIN=anthropic-api-firm /usr/bin/python3 ./ask.py --clip g 2>&1 | tail -c 400\n'), 2),
        obj(N, "alfred.workflow.output.notification",
            {"lastpathcomponent": False, "onlyshowifquerypopulated": True, "removeextension": False,
             "text": "{query}", "title": "Claude"}, 1),
        obj(H, "alfred.workflow.input.scriptfilter",
            {"alfredfiltersresults": True, "alfredfiltersresultsmatchmode": 2, "argumenttreatemptyqueryasnil": False,
             "argumenttrimmode": 0, "argumenttype": 1, "escaping": 102, "keyword": "cahelp", "queuedelaycustom": 3,
             "queuedelayimmediatelyinitially": True, "queuedelaymode": 0, "queuemode": 1, "runningsubtext": "",
             "script": help_script(), "scriptargtype": 1, "scriptfile": "",
             "subtext": "Every Claude command: pick one", "title": "Claude: help", "type": 0, "withspace": True}, 3),
        obj(HA, "alfred.workflow.action.script", script(HELP_ACTION), 2),
    ],
    "connections": {
        K: [{"destinationuid": S1, "modifiers": 0, "modifiersubtext": "", "vitoclose": False},
            {"destinationuid": S2, "modifiers": 1048576, "modifiersubtext": "Deeper answer (high effort)", "vitoclose": False}],
        S1: [{"destinationuid": N, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        S2: [{"destinationuid": N, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        KF: [{"destinationuid": F1, "modifiers": 0, "modifiersubtext": "", "vitoclose": False},
             {"destinationuid": F2, "modifiers": 1048576, "modifiersubtext": "Deeper answer (high effort), firm key", "vitoclose": False}],
        F1: [{"destinationuid": N, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        F2: [{"destinationuid": N, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        KS: [{"destinationuid": SP, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        SP: [{"destinationuid": N, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        KC: [{"destinationuid": C1, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        C1: [{"destinationuid": N, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
        H: [{"destinationuid": HA, "modifiers": 0, "modifiersubtext": "", "vitoclose": False}],
    },
    "uidata": {K: {"xpos": 40, "ypos": 40, "note": "ca <question>"},
               S1: {"xpos": 250, "ypos": 40, "note": "↩ ask.py (effort low)"},
               S2: {"xpos": 250, "ypos": 160, "note": "⌘↩ ask.py --deep (effort high)"},
               N: {"xpos": 460, "ypos": 40, "note": "Answer start, or why not"},
               KF: {"xpos": 40, "ypos": 420, "note": "caf <question> (firm key)"},
               F1: {"xpos": 250, "ypos": 420, "note": "↩ firm key, effort low"},
               F2: {"xpos": 250, "ypos": 540, "note": "⌘↩ firm key, effort high"},
               KS: {"xpos": 40, "ypos": 780, "note": "spel = cac g"},
               SP: {"xpos": 250, "ypos": 780, "note": "ask.py --clip g"},
               KC: {"xpos": 40, "ypos": 660, "note": "cac <instruction> (clipboard rewrite, firm key)"},
               C1: {"xpos": 250, "ypos": 660, "note": "ask.py --clip"},
               H: {"xpos": 40, "ypos": 300, "note": "cahelp list"},
               HA: {"xpos": 250, "ypos": 300, "note": "put the picked command in Alfred"}},
}

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("info.plist", plistlib.dumps(plist))
    z.write(os.path.join(SRC, "ask.py"), "ask.py")
print("built", OUT)
