# Claude for Alfred

JV's additions to this fork (Zapier's own workflow above is untouched). Nothing secret lives here:
tokens and keys stay in the macOS Keychain.

## `routines/`: fire a Claude Code routine on the seat

`cr <name> [text]` in Alfred fires that routine (claude.ai scheduled task with an API trigger).
↩ is quiet (a Tink sound; errors still notify), ⌘↩ also opens the run in claude.ai.

- `routines.json`: name → trigger id + Keychain service name. No secrets.
- `fire.py`: reads the token from the Keychain, `POST https://api.anthropic.com/v1/claude_code/routines/<trig>/fire`
  (research preview, `anthropic-beta: experimental-cc-routine-2026-04-01`). 30 fires/hour per routine.
- Your text reaches the run as an untrusted `<routine-fire-payload>`; each routine has one fixed job.

Add a routine: create it at claude.ai/code/routines, Trigger + API, Generate token (shown once). Copy it, then
in the Terminal app (Claude's `!` prompt can't take a pasted password and saves a blank):

    security add-generic-password -a "$USER" -s claude-routine-<name> -w "$(pbpaste)"; pbcopy </dev/null

Add the name to `routines.json`, then `python3 build_claude_routines.py` and open the built workflow.
Tests: `/usr/bin/python3 test_fire.py`. Leaked token: Regenerate it on the routine page (immediate).

## `ask/`: `ca`, `caf`, `cac`, `spel`, `cahelp` (direct Anthropic API, no agent)

Built and live-tested by JV on the Mac (v0.4). Pay per use on an API key read from the Keychain at run time; never
printed, logged or written anywhere. Bills the API key, not plan usage (unlike `cr`).

| Keyword | Does | Key (Keychain service) |
|---|---|---|
| `ca <question>` | quick answer (Opus 5.5, effort low) to the clipboard + a notification; ⌘↩ = effort high | `anthropic-api-ultra` |
| `ca test` / `ca usage` / `ca last` | check the key (free `GET /v1/models`) / this month's estimated spend / open the last answer | `anthropic-api-ultra` |
| `caf <question>` | the same on the firm key, logged separately; `caf usage`, `caf test` | `anthropic-api-firm` |
| `cac <instruction or preset>` | rewrites the text on the clipboard; result replaces it. `cac undo` restores the original | `anthropic-api-firm` |
| `spel` | `cac g`: fix spelling and grammar only | `anthropic-api-firm` |
| `cahelp` | pick-a-command list of every Claude keyword | none |

`cac` presets: `g`, `firm`, `polite`, `short`, `bullets`, `email`, `es`, `en`, `note`.

Usage log `~/.config/claude_ca/usage.log`, one tab-separated line per call: time, model, effort, input tokens,
output tokens, estimated cost, and `ultra|firm` (7th field). It holds no prompt or answer text. `cac undo` keeps the
pre-rewrite clipboard in `~/.config/claude_ca/clip-undo.txt` (mode 600, overwritten each time).

Save a key (in the Terminal app, not Claude's `!` prompt):

    security add-generic-password -U -a "$USER" -s anthropic-api-ultra -w "$(pbpaste)"; pbcopy </dev/null

Layout: `src/ask.py` (ships in the workflow), `build.py` (writes `Claude-Ask.alfredworkflow`), `test_ask.py`, and
`SHA256SUMS.txt` as delivered (it lists bare file names; `ask.py` sits in `src/`):

    cd claude/ask && sha256sum -c --ignore-missing SHA256SUMS.txt && (cd src && sha256sum -c --ignore-missing ../SHA256SUMS.txt)
    /usr/bin/python3 test_ask.py        # 10 offline tests
    /usr/bin/python3 build.py           # rebuild Claude-Ask.alfredworkflow

These three files are byte-identical to JV's v0.4 (sha256 in `SHA256SUMS.txt`); change them on the Mac and
re-issue the sums rather than editing here.

## `pplx/`: Perplexity intake (WO-3, option A)

On demand only; nothing watches Downloads.

- `pplx` takes the newest `.zip`/`.md`/`.pdf` in `~/Downloads` (or `pplx <path>`), SHA-256 hashes it, copies it to
  `$PPLX_BASE/<slug>-<date>/` (workflow variable, default `~/Dropbox/COWORK/_HYBRID/reports`), and writes
  `SHA256SUMS.txt` + `INTAKE.json` there. A zip is extracted as untrusted data (no absolute paths, no `..`, no
  symlinks, bounded size) into a fresh owner-only scratch dir **outside Dropbox** (`$PPLX_SCRATCH`, default
  `~/Library/Caches/pplx/`, else `$TMPDIR/pplx/`); `INTAKE.json` records that path and a SHA-256 manifest of every
  extracted file. The reports folder holds only the hashed original, `SHA256SUMS.txt`, `INTAKE.json` and later
  `REPORT.md`/`READERS.json`. A refused or failed intake removes its half-filed reports folder and scratch dir. The
  original stays in Downloads; filing the same file twice in a row is a no-op.
- Header block (optional): the **first** `PPLX-TAGS:` line in the first 40 lines, e.g.
  `PPLX-TAGS: matter=lien-enforceability; topic=medical-lien-ca; mode=DR; date=2026-11-12`, names the folder
  `lien-enforceability-medical-lien-ca-2026-11-12` (`date=YYYY-MM-DD` overrides today). A line that still holds a
  template placeholder (`<generic slug>`, `<topic>`, `<DR|council|regular>`, `<YYYY-MM-DD>`) is Perplexity echoing
  the prompt and is skipped. `mode` is `DR`, `council` or `regular`; anything else is filed with a warning. Without a
  usable line: file name + date.
- `pplx read [folder]` re-checks the copy's SHA-256 and re-hashes the extracted files against the manifest (refusing
  on any changed, missing or extra file; re-extracting from the hashed copy if the scratch dir was cleared), then
  runs three readers on the Messages API with ask.py's model,
  API version, headers and fallback (effort high, Keychain `anthropic-api-ultra`): (1) the main report line by line,
  (2) its tables/CSVs for fidelity (skipped when there are none), (3) a claims list for a later live check. It writes
  `REPORT.md` (Agree / Conflict / New / Red flags / Open questions / Claims for live check) and `READERS.json` (raw
  replies) next to the hashed copy. PDFs go as a base64 `document` block.
- Cost cap: refuses any single reader input over ~200K tokens (chars/4; a PDF counts ~2,000 tokens a page) before
  any Keychain read or API call. Each reader logs one line to the same usage log (7th field `ultra`), so `ca usage` includes it.
- `pplx open` opens the last intake folder; `pplxhelp` lists the commands.

`pplx.py` imports `ask.py` (from `../ask/src`, or next to it inside the workflow) rather than copying its helpers.

    cd claude/pplx && /usr/bin/python3 test_pplx.py     # 15 offline tests (urlopen and the key mocked)
    /usr/bin/python3 build_pplx.py                      # rebuild "Claude PPLX.alfredworkflow"

Installing either workflow is JV's click (double-click the `.alfredworkflow`).
