---
name: discord-bots-dyno-zira
description: Install and configure Dyno (moderation/automod/logs) and Zira (button roles) on a Discord guild via their web dashboard APIs. Complements discord-control-kit.
---

# Discord Bots: Dyno + Zira

Both dashboards block `webfetch` (Cloudflare). Use the SoarBridge browser
(plugin__soar-browser__*) with the user's real session, then drive the
dashboard's own JSON API via `plugin__soar-browser__evaluate`. That is the
reliable path — no clicking through forms, no scraping UI state.

## 0. Hierarchy first (before configuring)

Bot roles must outrank every grantable role:

```
Zira > Dyno > Founder > Admin > Moderator > ... > Muted > Member > ...
```

Create `Muted` before the bots' configuration if it does not exist. See
`discord-server-build` for the role creation snippet.

## 1. Dyno

Bot app id `155149108183695360`. Dashboard: `https://dyno.gg/manage/{guildId}`.

Internal API (call from the dyno.gg page origin, credentials included):

```js
// toggle module
fetch(`/api/server/${G}/toggleModule`, { method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({ module: 'Moderation', enabled: true }) })

// save settings
fetch(`/api/server/${G}/updateModuleSetting`, { method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({ module: 'moderation', settings: { modRoles: ['<id>'] } }) })

// read module state
fetch(`/api/modules/${G}/automod`, { credentials: 'include' }).then(r => r.json())
```

Module names in API: `moderation`, `automod`, `autoroles`, `welcome`,
`actionlog`. Endpoints:

```js
POST /api/server/{G}/automod/create       // rule below
POST /api/server/{G}/automod/edit
POST /api/server/{G}/automod/delete
POST /api/server/{G}/autoroles/create
POST /api/server/{G}/autoroles/delete
```

Automod rule body:

```js
{
  name: 'Anti-spam (ratelimit)', type: 'ratelimit', enabled: true,
  actions: ['delete'], actionAfter: 3, actionDuration: 60,
  roles: { required: false, ignored: false },
  channels: { required: false, ignored: false },
  filter: '', data: { count: 5, interval: 5 }
}
```

Actions: `warn`, `delete`, `automute`, `autoban`, `instantmute`,
`instantban`. Trigger types (`filterDefs`): `ratelimit`, `emojis`, `newline`,
`massmentions`, `duplicates`, `phishinglinks`, `caps`, `charcount`,
`attachments`, `links`, `invites`, `linkcooldown`, `spammentions`, `stickers`,
`stickerscooldown`, `spoilers`, `maskedlinks`, `zalgo`, `words`, `selfbots`.
Free tier: 1 rule per filter type. Valid `data` fields per type come from
`rulesConfig` on `GET /api/modules/{G}/automod`.

Config applied to the reference guild:

| Setting | Value |
| --- | --- |
| modules on | Moderation, AutoMod, Autoroles, Welcome, ActionLog |
| moderation | modRoles: Moderator, Admin |
| autoroles | `{ type: 'add', role: Member }` |
| welcome | channel #welcome, message pointing at #rules and #get-roles |
| actionlog | `updateModuleSetting { module: 'actionlog', settings: { channel: #mod-log, events: {...} } }` |
| automod | 6 rules (ratelimit 5/5s, emojis 8, newline 8, massmentions 6 → delete+automute after 3, duplicates 10, phishinglinks delete+warn) |

## 2. Zira

Bot app id `275813801792634880`. Dashboard: `https://dash.zira.bot/dashboard/{guildId}`.

Login is OAuth via Discord — open the signin page in the browser; the
user's logged-in Discord session authorizes it.

API (from dash.zira.bot origin):

```js
GET  /api/dashboard/{G}/buttons              // full state
POST /api/dashboard/{G}/buttons/template-roles // { roles: [{ name, color }] }
POST /api/dashboard/{G}/buttons/batch        // { surface, intents }
```

Batch intents (from dashboard bundle, validated live):

```js
{ op: 'add_group',    tempId: 'g1', name: 'Language', maxSelections: 1 }
{ op: 'update_group', id, name, maxSelections }
{ op: 'add_button',   tempId, label, emoji, description, color, rowIndex, position,
  requiredRoles: [], requiredMode: 'all', blacklistRoles: [], cooldownMs: null,
  groupRef: 'temp:g1' }
{ op: 'update_button', id, label, emoji, groupRef }
{ op: 'set_actions',  buttonRef: '<id>' or 'temp:<key>',
  actions: [{ type: 'toggle', roleID, durationMs: null, conditions: null }] }
{ op: 'delete_button', id }
{ op: 'set_display',  mode: 'buttons' | 'select', placeholder }
```

Surface payload for existing menus: `{ id, channelID, messageID }` (from
`GET /buttons` → `messages[]`). Response: `{ ok, renderError, renderCode,
surfaceID, tempGroupIDs, tempButtonIDs }`.

Free tier: 10 messages, 15 buttons each, 8 actions per button, 10 groups,
single-select groups only, timed roles ≤ 14 days.

UI flow (when driving the builder manually):
`/dashboard/{G}/embed-builder?register=buttons&channel=<id>` → fill
`#eb-content`, select radio `eb-wireup=buttons` → **Enviar e continuar** →
lands in Button Roles with the message selected → template "Menções de
notificação" → **Aplicar modelo** (creates missing ping roles, stages
buttons) → add remaining buttons via "+ Adicionar botão" (label input
`placeholder="Texto do botão"`, emoji `placeholder="🎉 ou :tada:"`, action
type select, role select) → **Salvar alterações**.

Reference menu (pinned in #get-roles, surface 9687, message
`1552510330188464182`, 12 buttons, custom_id `abtn:{triggerID}`):

- Pings (toggle): 📢 Announcements, 📅 Events, 🎉 Giveaways, 🛠️ Updates
- Language (group `Language` max 1, toggle): 🇺🇸 EN, 🇧🇷 PT-BR, 🇪🇸 ES
- Stacks (add): Frontend, Backend, Mobile, DevOps, AI/ML

Gotchas:

- `POST /buttons/batch` without the full surface object returns
  `{"error":"bad_surface"}` — include channelID + messageID.
- The old text panel (e.g. one mentioning "Carl-bot") should be deleted and
  the Zira menu pinned in its place.
- When applying templates, roles with the same name are reused; newly created
  duplicates (e.g. `EN` without emoji alongside `🇺🇸 EN`) can be deleted
  afterwards from Discord directly.

## 3. Verification

```js
// Discord side
GET /guilds/{G}/members/<botId>       // bot present, roles
GET /channels/<get-roles>/messages    // buttons with custom_id abtn:*
GET /guilds/{G}/roles                 // hierarchy

// dashboard side
GET /api/dashboard/{G}/buttons        // 12 triggers, actions with roleIDs
```