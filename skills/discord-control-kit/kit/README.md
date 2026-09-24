# kit/README.md — Discord Control Kit (script library)

Small, dependency-light helpers extracted from the validated SoarLabz
workflow. Everything assumes the Discord desktop app is running with
`--remote-debugging-port=9222`.

## Files

| File | Use |
| --- | --- |
| `eval.mjs` | One-off JS eval in the Discord page via CDP (bun, no deps). |
| `cdp.py` | `CdpSession`: connect, `eval`, token resolution (multi-runtime), rate-limit-aware `api()` calls, header injection. |
| `state.py` | Read-only guild state dump (guild core, channels by category, roles, onboarding, screening, pins). |
| `headers.py` | Capture anti-abuse headers via CDP Network and save **non-secret** ones to `/tmp/discord_sp.json`. |

## Quick start

```bash
# 1) sanity
bun /path/to/kit/eval.mjs "location.href"

# 2) state dump
python3 /path/to/kit/state.py --guild 1552491121312010331

# 3) in your own script
from cdp import CdpSession
with CdpSession() as cdp:
    guild = cdp.api("GET", f"/guilds/{GUILD_ID}")
```

Secrets policy: token and Authorization headers live in memory only.
`/tmp/discord_sp.json` stores non-secret headers (X-Super-Properties, locale,
timezone, installation id, debug options) and nothing else.

See `../SKILL.md` for the full technique and REST quirks table.