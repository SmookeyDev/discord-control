---
description: Check prerequisites, relaunch Discord with CDP, capture headers, verify guild state
---
Fresh-machine setup for Discord control. Work step by step and stop at the
first failure with a concrete fix.

## Arguments

$ARGUMENTS

If no guild id is given, use the SoarCode reference guild `1552491121312010331`.

## Steps

1. **Check app and CDP**
   ```bash
   pgrep -af "com.discordapp.Discord" | grep -v grep | head -5
   ss -tlnp | grep 9222
   ```
   If the port is closed, ask the user before relaunching:
   `pkill -f "com.discordapp.Discord"; sleep 2; flatpak run com.discordapp.Discord --remote-debugging-port=9222 &`
   (relaunching closes their session — this is a user-visible action).

2. **List CDP targets** and confirm a `type: page` with `discord.com` in the URL:
   `curl -s http://127.0.0.1:9222/json`

3. **Token sanity** (length only, never print it):
   ```bash
   bun .claude-plugin/skills/discord-control-kit/kit/eval.mjs \
     "(() => { window.__mods = []; window.webpackChunkdiscord_app.push([[Math.random()],{},e => window.__mods.push(e)]); const rt = window.__mods.find(r => r.m && '280450' in r.m); const t = rt && rt('280450').default.getToken(); return t ? 'token ok len=' + t.length : 'NO TOKEN'; })()"
   ```
   If NO TOKEN, scan for the current module id per `discord-control-kit` §3.

4. **Headers**: if `/tmp/discord_sp.json` exists and is recent, reuse it.
   Otherwise run `python3 .claude-plugin/skills/discord-control-kit/kit/headers.py`
   (this reloads the app's page — expect a brief UI refresh). Confirm the file
   contains NO Authorization entry.

5. **State check**:
   ```bash
   python3 .claude-plugin/skills/discord-control-kit/kit/state.py --guild <GUILD_ID>
   ```

6. **Report**: summarize what works and what needs attention. Remind the user
   that CDP is open and should be closed (relaunch without the flag) when the
   work is done.

Never persist the token or Authorization headers anywhere. Never run a write
call as part of this setup command.