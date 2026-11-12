#!/usr/bin/env python3
"""ask.py: ask Claude from Alfred on the Ultra API key (spends the monthly API credit, not plan usage).

    ca <question>      quick answer (claude-opus-5-5, effort low) -> clipboard + notification
    ca <question> ⌘↩   deeper answer (effort high)
    ca test            check the key works (GET /v1/models; free)
    ca usage           this month's estimated spend, from the local log
    caf ...            the same on the FIRM key (CA_KEYCHAIN=anthropic-api-firm), logged separately
    cac <instruction>  rewrite the text on the clipboard (firm key); result replaces the clipboard
    cac undo           put the original clipboard text back
    cac g|firm|polite|short|bullets|email|es|en|note   presets; spel = cac g
    ca last            open the last full answer

The key is read from the Keychain at run time (service in $CA_KEYCHAIN, default anthropic-api-ultra) and is
never printed, logged or written anywhere. The log (~/.config/claude_ca/usage.log) records time, model, effort,
tokens and an estimated cost: never the question or the answer. Stdlib only (/usr/bin/python3).
"""
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.anthropic.com/v1/messages"
MODELS = "https://api.anthropic.com/v1/models"
VERSION = "2026-10-21"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MODEL = "claude-opus-5-5"
PRICE = {"claude-opus-5-5": (4.00, 20.00)}   # $ per million tokens (input, output); fallback models logged, priced as Opus 5.5
SYSTEM = ("You answer quick questions for a California attorney from a launcher. Be concise and direct: "
          "lead with the answer, then at most a few short lines. Say when you are unsure. "
          "Do not invent citations; if a legal authority matters, say it needs checking.")
MAX_Q = 20000
HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".config", "claude_ca")
LOG = os.path.join(STATE, "usage.log")
LAST = os.path.join(STATE, "last.md")
UNDO = os.path.join(STATE, "clip-undo.txt")
REWRITE = ("You rewrite text for a California law firm. Follow the instruction exactly. Return ONLY the rewritten "
           "text: no preamble, no quotes, no notes. Keep names, numbers, dates and legal terms exactly as given "
           "unless the instruction says to change them. If the instruction is unclear, make the smallest sensible change.")


class Bad(Exception):
    pass


def keysvc():
    return os.environ.get("CA_KEYCHAIN", "anthropic-api-ultra")


def label(svc=None):
    return "firm" if "firm" in (svc or keysvc()) else "ultra"


def key(service=None):
    service = service or keysvc()
    r = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", service, "-w"],
                       capture_output=True, text=True)
    k = r.stdout.strip()
    if r.returncode != 0 or not k:
        raise Bad(f"no Keychain item {service!r}. Save it in the Terminal app: "
                  f"security add-generic-password -U -a \"$USER\" -s {service} -w \"$(pbpaste)\"")
    return k


def headers(k, beta=True):
    h = {"x-api-key": k, "anthropic-version": VERSION, "content-type": "application/json"}
    if beta:
        h["anthropic-beta"] = FALLBACK_BETA
    return h


def api_error(exc):
    try:
        msg = json.loads(exc.read().decode() or "{}").get("error", {}).get("message", "")
    except Exception:
        msg = ""
    hint = {401: "key rejected", 400: "bad request", 429: "rate limited or out of credit", 529: "overloaded"}.get(exc.code, "")
    return Bad(f"HTTP {exc.code} {hint}: {msg[:220]}".strip())


def build(question, effort, system=SYSTEM):
    return {"model": MODEL, "max_tokens": 8000, "system": system,
            "output_config": {"effort": effort}, "fallbacks": "default",
            "messages": [{"role": "user", "content": question}]}


def ask(question, effort="low", get_key=key, opener=urllib.request.urlopen, system=SYSTEM):
    q = (question or "").strip()
    if not q:
        raise Bad("usage: ca <question>   (cahelp lists everything)")
    if len(q) > MAX_Q:
        raise Bad(f"question is {len(q)} characters; the limit here is {MAX_Q}")
    req = urllib.request.Request(API, data=json.dumps(build(q, effort, system)).encode(), method="POST",
                                 headers=headers(get_key()))
    try:
        with opener(req, timeout=180) as resp:
            out = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise api_error(exc) from None
    except urllib.error.URLError as exc:
        raise Bad(f"network error ({exc.reason})") from None
    if out.get("stop_reason") == "refusal":
        cat = (out.get("stop_details") or {}).get("category") or "unspecified"
        raise Bad(f"Claude declined this one (category: {cat})")
    text = "\n".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()
    if not text:
        raise Bad(f"no text came back (stop_reason {out.get('stop_reason')})")
    u = out.get("usage", {})
    return text, out.get("model", MODEL), int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)), out.get("stop_reason")


def cost(model, tin, tout):
    pin, pout = PRICE.get(model, PRICE[MODEL])
    return tin / 1e6 * pin + tout / 1e6 * pout


def log(model, effort, tin, tout, now=None, who=None):
    os.makedirs(STATE, exist_ok=True)
    now = now or dt.datetime.now().astimezone()
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{now.isoformat(timespec='seconds')}\t{model}\t{effort}\t{tin}\t{tout}\t{cost(model, tin, tout):.4f}\t{who or label()}\n")


def usage(path=LOG, today=None, who=None):
    today, who = today or dt.date.today(), who or label()
    month, n, total = today.strftime("%Y-%m"), 0, 0.0
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            tag = f[6] if len(f) >= 7 else "ultra"
            if len(f) >= 6 and f[0].startswith(month) and tag == who:
                n, total = n + 1, total + float(f[5])
    pot = "of the $200 monthly Ultra API credit" if who == "ultra" else "on the firm Console balance"
    return f"{who} key, {month}: {n} asks, about ${total:.2f} {pot} (estimate; Console → Spending is exact)"


def test(get_key=key, opener=urllib.request.urlopen):
    req = urllib.request.Request(MODELS, method="GET", headers=headers(get_key(), beta=False))
    try:
        with opener(req, timeout=30) as resp:
            return f"key OK (HTTP {resp.status})"
    except urllib.error.HTTPError as exc:
        raise api_error(exc) from None
    except urllib.error.URLError as exc:
        raise Bad(f"network error ({exc.reason})") from None


def clip_get():
    return subprocess.run(["/usr/bin/pbpaste"], capture_output=True, text=True).stdout


def clip_set(text):
    subprocess.run(["/usr/bin/pbcopy"], input=text, text=True)


PRESETS = {
    "g": "Fix spelling, grammar and punctuation only. Keep my wording, tone and formatting.",
    "firm": "Make this firmer and more professional, for an insurance adjuster or opposing counsel. Keep every fact.",
    "polite": "Make this polite and professional. Keep it short and keep every fact.",
    "short": "Make this shorter and clearer. Keep every fact, name, number and date.",
    "bullets": "Turn this into 3 to 5 short bullet points.",
    "email": "Turn these notes into a short, professional email body. No subject line, no signature.",
    "es": "Translate into clear, natural Spanish for a client. Keep names, numbers and dates exactly.",
    "en": "Translate into clear English. Keep names, numbers and dates exactly.",
    "note": "Rewrite as a concise, factual case note in the third person. No opinions, nothing added.",
}


def expand(instr):
    return PRESETS.get(instr.strip().lower(), instr)


def rewrite_prompt(instr, text):
    return f"Instruction: {instr}\n\nText to rewrite:\n<text>\n{text}\n</text>"


def clip(instr, get=clip_get, put=clip_set, asker=None):
    instr = (instr or "").strip()
    if instr.lower() == "undo":
        if not os.path.exists(UNDO):
            raise Bad("nothing to undo")
        put(open(UNDO, encoding="utf-8").read())
        return "Clipboard restored to the original text"
    if not instr:
        raise Bad("usage: cac <what to do with the copied text>   e.g. cac fix grammar")
    text = get()
    if not text.strip():
        raise Bad("the clipboard is empty: copy some text first")
    if len(text) > MAX_Q:
        raise Bad(f"clipboard holds {len(text)} characters; the limit here is {MAX_Q}")
    os.makedirs(STATE, exist_ok=True)
    fd = os.open(UNDO, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    out, model, tin, tout, _ = (asker or ask)(rewrite_prompt(expand(instr), text), "low", system=REWRITE)
    log(model, "clip", tin, tout)
    put(out)
    return f"Rewritten ({len(out)} chars): paste it. cac undo restores the original. (${cost(model, tin, tout):.3f})"


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if a and a[0] == "--clip":
        try:
            print(clip(" ".join(a[1:])))
            return 0
        except (Bad, OSError, ValueError) as exc:
            print(f"Not rewritten: {exc}")
            return 1
    deep = bool(a) and a[0] == "--deep"
    if deep:
        a = a[1:]
    q = " ".join(a).strip()
    try:
        if q.lower() == "test":
            print(test())
            return 0
        if q.lower() == "usage":
            print(usage())
            return 0
        if q.lower() == "last":
            if not os.path.exists(LAST):
                raise Bad("no answer saved yet")
            subprocess.run(["/usr/bin/open", "-e", LAST])
            return 0
        effort = "high" if deep else "low"
        text, model, tin, tout, _ = ask(q, effort)
    except (Bad, OSError, ValueError) as exc:
        print(f"Not answered: {exc}")
        return 1
    log(model, effort, tin, tout)
    os.makedirs(STATE, exist_ok=True)
    with open(LAST, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    subprocess.run(["/usr/bin/pbcopy"], input=text, text=True)
    note = "" if model == MODEL else f" [answered by fallback {model}]"
    print((text[:220] + ("…" if len(text) > 220 else "")) + note + f"  (copied · ${cost(model, tin, tout):.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
