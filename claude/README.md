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

## Planned

`ca <text>`: a direct Anthropic API call (pay per use, key in the Keychain) for quick answers, no agent.
