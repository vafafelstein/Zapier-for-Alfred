#!/usr/bin/env python3
"""fire.py: fire a Claude Code routine (scheduled task) on JV's seat from Alfred.

    cr <name> [text]     e.g.  cr ping hello

<name> is looked up in routines.json (shipped inside the workflow): its trigger id and the Keychain service
that holds that routine's API token. The token is read from the Keychain at fire time and never printed,
logged or written anywhere. [text] goes to the run as the routine's <routine-fire-payload> (untrusted data).
Quiet by default (a Tink sound, nothing on screen; errors still notify); --open (⌘↩ in Alfred) also opens the run in claude.ai. Stdlib only (/usr/bin/python3).

API (research preview): POST https://api.anthropic.com/v1/claude_code/routines/<trig>/fire
headers anthropic-beta: experimental-cc-routine-2026-04-01, anthropic-version: 2023-06-01. 30 fires/hour per routine.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.anthropic.com/v1/claude_code/routines/{}/fire"
BETA = "experimental-cc-routine-2026-04-01"
TRIG_RE = re.compile(r"trig_[A-Za-z0-9]{10,40}")
SVC_RE = re.compile(r"claude-routine-[a-z0-9-]{1,40}")
MAX_TEXT = 20000


class Bad(Exception):
    pass


def load_routines(path=os.path.join(HERE, "routines.json")):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    for name, r in data.items():
        if not TRIG_RE.fullmatch(r.get("trigger", "")) or not SVC_RE.fullmatch(r.get("keychain", "")):
            raise Bad(f"routines.json entry {name!r} is malformed")
    return data


def parse(query, routines):
    parts = (query or "").strip().split(None, 1)
    if not parts:
        raise Bad("usage: cr <name> [text]  (names: " + ", ".join(sorted(routines)) + ")")
    name, text = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
    if name not in routines:
        raise Bad(f"no routine named {name!r} (names: " + ", ".join(sorted(routines)) + ")")
    if len(text) > MAX_TEXT:
        raise Bad(f"text is {len(text)} characters; the limit here is {MAX_TEXT}")
    return name, text


def token_for(service):
    r = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", service, "-w"],
                       capture_output=True, text=True)
    tok = r.stdout.strip()
    if r.returncode != 0 or not tok:
        why = (r.stderr or "").strip().splitlines()[-1:] or ["empty value"]
        raise Bad(f"could not read Keychain item {service!r} (security exit {r.returncode}: {why[0][:120]}). "
                  f"If it is missing: security add-generic-password -a \"$USER\" -s {service} -w")
    return tok


def build_request(trigger, token, text):
    body = json.dumps({"text": text} if text else {}).encode()
    return urllib.request.Request(API.format(trigger), data=body, method="POST", headers={
        "Authorization": "Bearer " + token, "anthropic-beta": BETA, "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"})


def fire(query, routines=None, get_token=token_for, opener=urllib.request.urlopen):
    routines = routines if routines is not None else load_routines()
    name, text = parse(query, routines)
    r = routines[name]
    req = build_request(r["trigger"], get_token(r["keychain"]), text)
    try:
        with opener(req, timeout=30) as resp:
            out = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        hint = {401: "token rejected: regenerate it on the routine page and save it again",
                429: "rate limited: 30 fires an hour per routine"}.get(exc.code, "")
        raise Bad(f"{name}: HTTP {exc.code} {hint}".strip()) from None
    except urllib.error.URLError as exc:
        raise Bad(f"{name}: network error ({exc.reason})") from None
    url = out.get("claude_code_session_url", "")
    if not url.startswith("https://claude.ai/"):
        raise Bad(f"{name}: fired, but no session link came back")
    return name, url


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    show = bool(a) and a[0] == "--open"
    if show:
        a = a[1:]
    try:
        name, url = fire(" ".join(a))
    except (Bad, OSError, ValueError) as exc:
        print(f"Not fired: {exc}")
        return 1
    if show:
        subprocess.run(["/usr/bin/open", url])
        print(f"Fired {name}: the run is opening in claude.ai")
    else:  # quiet: a short sound, no notification (Alfred shows one only when something is printed)
        subprocess.Popen(["/usr/bin/afplay", "/System/Library/Sounds/Tink.aiff"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
