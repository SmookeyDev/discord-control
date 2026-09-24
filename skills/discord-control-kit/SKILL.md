---
name: discord-control-kit
description: Core technique to control a Discord server from SoarCode — CDP hook on the desktop app, in-memory token, authentic anti-abuse headers, REST calls from inside the page. Use before any Discord automation.
---

# Discord Control Kit

Validated on Fedora 44 + flatpak `com.discordapp.Discord` 1.0.158
(Electron 42.11.1). All credentials stay in memory. The technique has three
pillars: **CDP hook**, **in-memory token**, **authentic headers**.

## 0. Hard rules (non-negotiable)

- Never persist the token: no files, logs, memories, commits, tool output.
- Never persist `Authorization` headers. `/tmp/discord_sp.json` stores only
  non-secret headers (X-Super-Properties, locale, timezone, installation id,
  debug options).
- CDP on 9222 exposes the logged-in account to any local process. At the end:
  `flatpak run com.discordapp.Discord` (no flag) and tell the user.
- Writes are irreversible (deletes, bans, role edits). Confirm scope first.
- Writes need the captured header set; plain fetch → 403 code 10008.

## 1. Launch with CDP

```bash
# check
pgrep -af discord | grep -v grep | head -5
ss -tlnp | grep 9222

# relaunch with CDP (kills first)
pkill -f "com.discordapp.Discord"; sleep 2
flatpak run com.discordapp.Discord --remote-debugging-port=9222 >/dev/null 2>&1 &

# list targets — you need type=page with url containing discord.com
curl -s http://127.0.0.1:9222/json | python3 -c "
import json,sys
for t in json.load(sys.stdin):
    print(t.get('type'), '|', (t.get('title') or '')[:40], '|', (t.get('url') or '')[:60])"
```

## 2. Eval helper (bun, no deps)

A ready helper ships with this skill at `kit/eval.mjs` (copy to /tmp and use):

```js
// /tmp/discord-kit/eval.mjs — usage: bun eval.mjs "<js expression>"
const expr = process.argv[2];
const targets = await (await fetch('http://127.0.0.1:9222/json')).json();
const page = targets.find(t => t.type === 'page' && t.url.includes('discord.com'));
if (!page) { console.error('no discord page target'); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
const id = Math.floor(Math.random() * 1e9);
const result = await new Promise((res) => {
  const handler = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id === id) { ws.removeEventListener('message', handler); res(msg); }
  };
  ws.addEventListener('message', handler);
  ws.send(JSON.stringify({ id, method: 'Runtime.evaluate',
    params: { expression: expr, returnByValue: true, awaitPromise: true } }));
});
ws.close();
if (result.result?.exceptionDetails) { console.error(JSON.stringify(result.result.exceptionDetails)); process.exit(2); }
console.log(JSON.stringify(result.result?.result?.value ?? null));
```

## 3. Token in memory — multiple webpack runtimes

The token module id changes between builds (`247775` → `280450` as of
Sep/2026). Two traps:

1. There are **multiple webpack runtimes** sharing the same
   `webpackChunkdiscord_app` array; a single `push` collects only the last
   runtime.
2. Never print the token; only check its length.

```js
// collect ALL runtimes
window.__mods = [];
window.webpackChunkdiscord_app.push([[Math.random()], {}, (e) => window.__mods.push(e)]);
// pick the runtime that owns the auth module
const rt = window.__mods.find(r => r.m && '280450' in r.m);
const token = rt('280450').default.getToken();
// sanity only:
token ? `ok len=${token.length}` : 'no token'
```

If `'280450' in r.m` fails, discover the current id by scanning factories:

```js
// find module ids whose source references getToken
const hits = [];
for (const id in rt.m) {
  try { if (rt.m[id].toString().includes('getToken')) { hits.push(id); if (hits.length > 15) break; } } catch {}
}
// then find the one whose exports expose getToken on exports/default
for (const id in rt.c) {
  const ex = rt.c[id]?.exports;
  for (const k of Object.keys(ex ?? {})) {
    if (typeof ex[k]?.getToken === 'function') return id + '.' + k;
  }
}
```

## 4. Capture anti-abuse headers (once per session)

Enable CDP Network, reload the page once, read request headers, save only the
non-secret ones to `/tmp/discord_sp.json`:

```json
{
  "url_path": "/api/v9/...",
  "x_super_properties": "<base64 ~1100 chars>",
  "x_context_properties": "<base64>",
  "x_discord_locale": "en-US",
  "x_discord_timezone": "America/Sao_Paulo",
  "x_installation_id": "<id>",
  "x_debug_options": "bugReporterEnabled"
}
```

Keep the raw capture in memory only. If the file already exists from a recent
session, reuse it.

## 5. In-page REST helper

Inject once per CDP session (token via JSON.stringify is fine — it lives in
the page, not on disk):

```js
window.__api = (method, path, body) => fetch('/api/v9' + path, {
  method,
  headers: {
    Authorization: TOKEN,
    'Content-Type': 'application/json',
    'X-Super-Properties': SP,
    'X-Context-Properties': CP,
    'X-Discord-Locale': LOCALE,
    'X-Discord-Timezone': TZ,
    'X-Installation-ID': INSTID,
    'X-Debug-Options': XDEBUG,
    'Accept-Language': 'en-US,en;q=0.9'
  },
  body: body === undefined ? undefined : JSON.stringify(body)
}).then(r => r.text().then(t => ({ status: r.status, body: t,
  retry: r.headers.get('retry-after') })));
```

Then drive everything through `__api` from Python:

```python
def cdp_eval(ws, expr, msg_id, timeout=60, await_promise=True):
    ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True, "awaitPromise": await_promise}}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = json.loads(ws.recv(timeout=deadline - time.time()))
        if msg.get("id") == msg_id:
            return msg.get("result", {}).get("result", {}).get("value")
    return None
```

Rate-limit pattern used everywhere (sleep on retry-after, cap 25–30s, max 5
retries, ~1s between writes).

## 6. REST quirks learned on the target guild

| Topic | Rule |
| --- | --- |
| Guild PATCH | Must include `features` when sending `public_updates_channel_id`; `icon` accepts a data URI (any square size) |
| Channels | PATCH `type` only accepts `(0, 5)`; text→forum requires recreate (create type 15 + delete) |
| public_updates_channel | Must be a text channel (announcement type 5 rejected) |
| Onboarding | `PUT /guilds/{id}/onboarding`: `mode=0` int; prompt `type` 0=DEFAULT / 1=MULTIPLE int |
| Screening | `PATCH /guilds/{id}/member-verification` with `"field_type":"TERMS"` (string) + `values=[rules_message_id]` |
| Roles | Managed bot roles cannot be moved by the user account; plan hierarchy around them |

## 7. Guild reference (SoarCode)

- id `1552491121312010331`, owner `486973412951195662`
- 7 categories / 26 channels; `#bug-reports`, `#feature-requests` are forums;
  `#announcements` is type 5
- roles: Zira 21 > Dyno 20 > Founder(#823AFF admin) > Admin > Moderator >
  Community Helper > Bot > Server Booster > Muted(13, deny in all channels) >
  Member > stacks/langs/pings
- onboarding: mode 0, 3 prompts (language required, notifications, stack);
  screening: TERMS + rules message
- bots: Dyno `155149108183695360`, Zira `275813801792634880`

## 8. Cleanup checklist (always tell the user)

1. `pkill -f "remote-debugging-port=9222"` then relaunch the app normally.
2. Delete scripts containing captured headers if they are no longer needed.
3. Never commit anything under /tmp used here.