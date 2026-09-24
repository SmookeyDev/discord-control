# discord-control

> Controle um servidor do Discord de ponta a ponta a partir do SoarCode —
> hook CDP no app desktop, token só em memória, headers anti-abuse autênticos,
> automação de guild/branding/roles e configuração de bots (Dyno + Zira).

[![Formato](https://img.shields.io/badge/manifest-SoarPack-823AFF)](manifest.json)
[![Versão](https://img.shields.io/badge/version-1.0.0-blue)](manifest.json)
[![Plataforma](https://img.shields.io/badge/testado-Fedora%2044%20·%20flatpak-29ABE2)](#requisitos)

Esta branch é o exemplo de staging SoarPack nativo: o `manifest.json` na raiz é
instalado do GitHub como fonte não assinada, sempre desativada e sem update
automático. O mesmo conteúdo pode ser empacotado e publicado por um registry
assinado para release.

Este pacote nasceu de um workflow **validado em produção** (servidor SoarCode,
set/2026): tudo que está aqui foi executado de verdade — criação da guild,
estrutura de canais, onboarding, screening, branding, hierarquia de cargos,
configuração completa do Dyno e menu de button-roles do Zira.

---

## O que este plugin faz

| Componente | Tipo | O que faz |
| --- | --- | --- |
| `discord-control-kit` | Skill | Técnica núcleo: relançar o app com CDP, resolver o token (multi-runtime webpack), capturar headers anti-abuse, helper REST in-page, rate-limit-aware |
| `discord-server-build` | Skill | Guild do zero: categorias/canais, onboarding, screening, branding (ícone/banner/splash), hierarquia de cargos |
| `discord-bots-dyno-zira` | Skill | Configurar Dyno (API do dashboard) e Zira (button roles via API + UI) |
| `discord-setup` | Command | `/discord-setup` — onboarding de máquina nova: pré-requisitos, relaunch com CDP, headers, verificação de estado |
| `discord-agent` | Agent | Worker read-only que audita o estado da guild e reporta evidência |
| `kit/` | Scripts | `cdp.py` (sessão CDP + `api()` com retry de 429), `state.py` (dump read-only), `headers.py` (captura de headers **não-secretos**), `eval.mjs` (eval one-shot) |

**Sem token de bot. Sem credenciais armazenadas. Sem terceiros.**

---

## Como funciona (em 30 segundos)

1. O Discord desktop é relançado com `--remote-debugging-port=9222` (CDP).
2. O token de auth é resolvido **em memória** via módulo webpack dentro da
   própria página do app (nunca impresso, nunca salvo).
3. Headers anti-abuse (X-Super-Properties etc.) são capturados uma vez por
   sessão e os não-secretos ficam em `/tmp/discord_sp.json`.
4. Todas as chamadas REST passam por um helper `fetch()` injetado dentro da
   página — com os headers autênticos, o Discord aceita escritas que o fetch
   cru rejeita (403 code 10008).
5. Rate limits são respeitados dormindo em `retry-after`.

```
┌────────────────────┐   CDP :9222   ┌─────────────────────┐
│   SoarCode agent   │ ────────────► │  Discord desktop    │
│  (scripts python)  │   Runtime.    │  (page discord.com) │
└────────────────────┘   evaluate    └──────────┬──────────┘
                                                │ fetch('/api/v9/...')
                                                ▼
                                     ┌─────────────────────┐
                                     │  Discord REST API   │
                                     └─────────────────────┘
```

---

## Requisitos

- **Discord desktop** (flatpak `com.discordapp.Discord` — testado 1.0.158,
  Electron 42.11.1) logado na conta com acesso à guild alvo
- **Python 3.10+** com `websockets` (`pip install websockets`)
- **bun** ou **node** (para `eval.mjs`)
- `gh`, `magick`, `PIL` são opcionais (publish/branding/imagens)

---

## Instalação

### SoarCode (Settings → Plugins → Install from GitHub)

```
https://github.com/SmookeyDev/discord-control/tree/soarpack
```

1. Settings → Plugins → Add → Install from GitHub
2. Entre a URL da branch `soarpack`, inspecione o manifest e as capabilities
3. O SoarPack entra **desativado por design** — revise o código e ative
4. Skills/commands/agents ficam disponíveis: `/discord-setup`, skills
   `discord-control-kit`, `discord-server-build`, `discord-bots-dyno-zira`

### Uso direto dos scripts (sem instalar)

```bash
git clone https://github.com/SmookeyDev/discord-control
cd discord-control

# 1) app com CDP (porta 9222)
flatpak run com.discordapp.Discord --remote-debugging-port=9222 &

# 2) sanity
bun skills/discord-control-kit/kit/eval.mjs "location.href"

# 3) headers anti-abuse (não-secretos) → /tmp/discord_sp.json
python3 skills/discord-control-kit/kit/headers.py

# 4) dump read-only do estado da guild
python3 skills/discord-control-kit/kit/state.py --guild 1552491121312010331
```

```python
# em qualquer script seu
from cdp import CdpSession
GUILD = "1552491121312010331"

with CdpSession() as cdp:
    guild = cdp.api("GET", f"/guilds/{GUILD}")            # dict {status, body, retry}
    canais = cdp.api("GET", f"/guilds/{GUILD}/channels")
    # escrita (com rate-limit retry):
    cdp.api("PATCH", f"/channels/{id}", {"name": "novo-nome"})
```

---

## Segurança — leia antes de usar

Este plugin controla a **sua própria conta logada**. Isso é poderoso e tem
consequências:

| Regra | Por quê |
| --- | --- |
| **Token nunca é persistido** | Resolvido em memória via CDP; injetado só no helper `window.__api()` dentro da página |
| **Authorization nunca é salvo** | `headers.py` grava em `/tmp/discord_sp.json` **apenas** headers não-secretos (X-Super-Properties, locale, timezone, installation id) |
| **CDP aberto = conta exposta** | Porta 9222 deixa qualquer processo local falar com sua sessão logada. Ao terminar: `pkill -f "remote-debugging-port=9222"` e relance o app normal |
| **Escritas são reais** | Deletes de canais/cargos, bans, PATCHes são irreversíveis — confirme escopo antes |
| **Rate limits** | O kit dorme em `retry-after` (máx. 5 tentativas) e espaça escritas ~1s. Não faça loops de escrita crua |
| **Anti-abuse** | Escritas sensíveis exigem o conjunto de headers capturado; fetch cru → 403 code 10008 |

Nunca coloque token, Authorization, cookies ou SOPS material em commits,
memories, logs ou relatórios.

---

## Estrutura

```
.
├── manifest.json            # manifest SoarPack v1 (autoritativo)
├── skills/
│   ├── discord-control-kit/
│   │   ├── SKILL.md         # técnica núcleo (CDP, token, headers, REST)
│   │   └── kit/
│   │       ├── cdp.py       # CdpSession: eval + api() com retry de 429
│   │       ├── state.py     # dump read-only da guild
│   │       ├── headers.py   # captura headers não-secretos
│   │       └── eval.mjs     # eval one-shot via bun
│   ├── discord-server-build/
│   │   └── SKILL.md         # guild, canais, onboarding, branding, roles
│   └── discord-bots-dyno-zira/
│       └── SKILL.md         # dashboards Dyno + Zira (APIs internas)
├── commands/
│   └── discord-setup.md     # fonte de compatibilidade da template
├── templates/
│   └── discord-setup.md     # template nativa namespaced
├── agents/
│   └── discord-agent.md     # worker read-only
├── .claude-plugin/          # referência do formato da branch main
└── README.md
```

> Os arquivos `.claude-plugin/` e `commands/` foram mantidos para comparação com
> a branch `main`. Nesta branch, o scanner prioriza o `manifest.json` SoarPack e
> instala apenas o layout nativo declarado em `contents`.

---

## Guild de referência (SoarCode)

Tudo foi validado nesta guild:

- **Guild:** `1552491121312010331` · owner `486973412951195662` (Ícaro/SmookeyDev)
- **Estrutura:** 7 categorias, 26 canais; `#bug-reports` e `#feature-requests`
  são fóruns; `#announcements` é announcement (type 5)
- **Onboarding:** mode 0, 3 prompts (idioma obrigatório, notificações, stack)
- **Screening:** TERMS + regras
- **Branding:** ícone/banner/splash aplicados e verificados no CDN
- **Cargos:** 26 cargos; hierarquia `Zira(21) > Dyno(20) > Founder > Admin >
  Moderator > Community Helper > Bot > Server Booster > Muted > Member >
  stacks > idiomas > pings`
- **Bots:** Dyno (moderação, automod com 6 regras, autorole Member, welcome,
  actionlog em #mod-log) e Zira (menu de button roles fixado em #get-roles
  com 12 botões — pings em toggle, idiomas em grupo single-select, stacks)

---

## Roadmap

- [ ] Publicar como SoarPack assinado (registry SoarCode)
- [ ] Suporte a outros bots (Carl-bot, MEE6)
- [ ] Módulo de levels/suggestions
- [ ] Testes de integração mockados (CDP fake)

---

## Licença

MIT © SmookeyDev (Ícaro Sant'Ana)

> ⚠️ **Disclaimer:** Este plugin usa a interface de debug do app desktop do
> Discord para controlar a sua própria conta. Use em servidores que você
> administra. Não é afiliado ao Discord Inc. Use por sua conta e risco.
