---
name: discord-server-build
description: Build and brand a Discord guild end-to-end — creation, categories/channels, onboarding, screening, branding assets, roles hierarchy. Complements discord-control-kit.
---

# Discord Server Build

Assumes the kit (`discord-control-kit`) is already connected: `__api` helper
injected, headers captured. All calls below use `window.__api(method, path,
body)`.

## 1. Guild creation

```js
POST /guilds { name: "SoarCode" }
// returns guild object with its default channels
```

## 2. Categories and channels

```js
POST /guilds/{id}/channels
// category: { name, type: 4 }
// text:     { name, type: 0, parent_id: catId }
// voice:    { name, type: 2, parent_id: catId }
// forum:    { name, type: 15, parent_id: catId }
// announcement: { name, type: 5, parent_id: catId }
```

Reference structure (7 categories, 26 channels):

```
📌 Information: #welcome #rules #announcements(5) #releases #get-roles #faq
💬 Community:   #general #introductions #showcase #off-topic + 2 voice
🛠️ SoarCode Dev: #dev-general #bug-reports(15) #feature-requests(15) #github #bot-commands
🌍 International: #english #português-brasil #español
🎫 Support: #help #suggestions
🔊 Voice: Lounge, Pair Programming, Focus Room
👮 Staff: #mod-log #staff-chat
```

Rename via `PATCH /channels/{id}`. Convert text→announcement with
`{ type: 5 }`; text→forum is NOT supported by PATCH — recreate as type 15 and
delete the original.

## 3. Community, onboarding, screening

```js
// community feature + rules/updates channels (updates must be a TEXT channel)
PATCH /guilds/{id} {
  features: [...features, "COMMUNITY"],
  rules_channel_id: "<text>",
  public_updates_channel_id: "<text>",
  description: "..."
}

// onboarding (mode 0 = default; prompts: type 0 DEFAULT, 1 MULTIPLE)
PUT /guilds/{id}/onboarding {
  enabled: true, mode: 0,
  prompts: [
    { title: "Choose your language", type: 0, required: true, in_onboarding: true,
      options: [ { title: "🇺🇸 EN", emoji_name: "🇺🇸", role_id: "<role>" }, ... ] },
    ...
  ],
  default_channel_ids: ["<welcome>", "<get-roles>"]
}

// screening: TERMS field pointing at a rules message
PATCH /guilds/{id}/member-verification {
  description: "Welcome to SoarCode! Accept the rules to unlock the community.",
  form_fields: [ { field_type: "TERMS", label: "Server Rules", required: true,
                  values: ["<rules_message_id>"] } ],
  version: "<get current version first>"
}
```

Post the rules content in `#rules` first, then reference its message id.

## 4. Branding

Assets prepared with `magick` (or PIL), sent as data URIs:

```js
PATCH /guilds/{id} { icon:   "data:image/png;base64,..." }   // square any size
PATCH /guilds/{id} { features: [...],
  banner: "data:image/jpeg;base64,...",  // 1920x1080
  splash: "data:image/jpeg;base64,..." } // 960x540, needs tier or INVITE_SPLASH feature
```

Rules of thumb:

- icon accepts a square PNG of any size; 512x512 is safe
- banner/splash persist on Nitro tier 2 (guild) or with
  `ANIMATED_BANNER`/`INVITE_SPLASH` features
- verify by `GET /guilds/{id}` → hash changed, and download the CDN URL
  (fetch inside the page, e.g. `fetch(cdnUrl).then(r => r.arrayBuffer())`)
- keep the previous icon file as rollback before replacing

## 5. Roles and hierarchy

```js
POST /guilds/{id}/roles { name, color, hoist, mentionable, permissions }
PATCH /guilds/{id}/roles { roles: [{ id, position }] }  // array body, not wrapped
PUT  /channels/{id}/permissions/{roleId} { allow: "0", deny: "<mask>", type: 0 }
```

Reference palette: Founder `#823AFF` admin; Admin/Moderator/Community Helper
hoisted; `Bot` for shared bot perms; language roles 🇺🇸 EN / 🇧🇷 PT-BR /
🇪🇸 ES; ping roles 📢 Announcements / 🗓️ Events / 🚀 Releases; stacks
Frontend/Backend/Mobile/DevOps/AI-ML; `Muted` role (deny
SEND_MESSAGES/ADD_REACTIONS/CONNECT/SPEAK/…) with a channel overwrite on every
channel (25+ PUT calls, spaced ~1s).

Managed bot roles (Dyno/Zira) sit above all grantable roles:

```
Zira(21) > Dyno(20) > Founder(19) > Admin > Moderator > Community Helper >
Bot > Server Booster > Muted > Member > stacks > langs > pings > @everyone
```

`@everyone` permissions string for the mute mask reference: deny bits
ADD_REACTIONS(1<<6), SEND_MESSAGES(1<<11), SEND_TTS_MESSAGES(1<<12),
CONNECT(1<<20), SPEAK(1<<21), CREATE_PUBLIC_THREADS(1<<35),
CREATE_PRIVATE_THREADS(1<<36), SEND_MESSAGES_IN_THREADS(1<<38),
SEND_VOICE_MESSAGES(1<<40), USE_SOUNDBOARD(1<<42).

## 6. Verification checklist

1. `GET /guilds/{id}` — features, rules/updates channels, icon/banner hashes
2. `GET /guilds/{id}/channels` — all channels with correct parents/types
3. `GET /guilds/{id}/onboarding` — enabled, mode, prompts count
4. `GET /guilds/{id}/member-verification` — TERMS field present
5. `GET /guilds/{id}/roles` — positions strictly ordered, no collisions
6. Channel overwrite check for Muted on every channel