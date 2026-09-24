"""CDP bridge for the Discord desktop app (validated on flatpak 1.0.158).

Secrets policy: the token is fetched in-memory via CDP and injected only into
the in-page __api helper. Nothing about Authorization is written to disk.
"""

import json
import time
import urllib.request
from websockets.sync.client import connect

CDP_HTTP = "http://127.0.0.1:9222"
SP_FILE = "/tmp/discord_sp.json"

GET_TOKEN = r"""
(() => {
  let tok = null;
  window.webpackChunkdiscord_app.push([[Math.random()], {}, (req) => {
    try {
      const e = req("280450");
      for (const obj of [e, e && e.default]) {
        if (obj && typeof obj.getToken === "function") {
          const t = obj.getToken();
          if (typeof t === "string" && t.length > 20) { tok = t; break; }
        }
      }
    } catch {}
  }]);
  return tok || "";
})()
"""


def _page_ws_url():
    targets = json.loads(urllib.request.urlopen(f"{CDP_HTTP}/json/list").read())
    pages = [
        t
        for t in targets
        if t.get("type") == "page" and "discord.com" in t.get("url", "")
    ]
    if not pages:
        raise SystemExit(
            "no discord page target — is the app running with --remote-debugging-port=9222?"
        )
    return pages[0]["webSocketDebuggerUrl"]


def cdp_eval(ws, expr, msg_id, timeout=60, await_promise=True):
    params = {"expression": expr, "returnByValue": True, "awaitPromise": await_promise}
    ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": params}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = json.loads(ws.recv(timeout=deadline - time.time()))
        if msg.get("id") == msg_id:
            return msg.get("result", {}).get("result", {}).get("value")
    return None


def load_sp():
    with open(SP_FILE) as f:
        return json.load(f)


class CdpSession:
    """Usage:
    with CdpSession() as cdp:
        cdp.api("GET", f"/guilds/{GUILD_ID}")
    """

    def __init__(self, sp_file=SP_FILE, ws_url=None):
        self._sp_file = sp_file
        self._ws_url = ws_url
        self._ws = None
        self._token = None
        self.step = 10

    # typing helper for the analyzer: _ws is a websocket connection once opened
    def _close_ws(self):
        if self._ws is not None:
            self._ws.close()

    def __enter__(self):
        url = self._ws_url or _page_ws_url()
        self._ws = connect(url, max_size=30 * 1024 * 1024)
        self.token = cdp_eval(self._ws, GET_TOKEN, 1)
        if not self.token:
            raise SystemExit("[-] no token via module 280450")
        print("[+] token OK (in memory only)")
        with open(self._sp_file) as f:
            sp = json.load(f)
        helper = (
            """
        window.__api = (method, path, body) => fetch('/api/v9' + path, {
          method,
          headers: {
            Authorization: %TOK%,
            'Content-Type': 'application/json',
            'X-Super-Properties': %SP%,
            'X-Context-Properties': %CP%,
            'X-Discord-Locale': %LOCALE%,
            'X-Discord-Timezone': %TZ%,
            'X-Installation-ID': %INSTID%,
            'X-Debug-Options': %XDEBUG%,
            'Accept-Language': 'en-US,en;q=0.9'
          },
          body: body === undefined ? undefined : JSON.stringify(body)
        }).then(r => r.text().then(t => ({ status: r.status, body: t,
          retry: r.headers.get('retry-after') })));
        """.replace("%TOK%", json.dumps(self.token))
            .replace("%SP%", json.dumps(sp["x_super_properties"]))
            .replace("%CP%", json.dumps(sp.get("x_context_properties", "e30=")))
            .replace("%LOCALE%", json.dumps(sp.get("x_discord_locale", "en-US")))
            .replace(
                "%TZ%", json.dumps(sp.get("x_discord_timezone", "America/Sao_Paulo"))
            )
            .replace("%INSTID%", json.dumps(sp["x_installation_id"]))
            .replace("%XDEBUG%", json.dumps(sp.get("x_debug_options", "")))
        )
        cdp_eval(self._ws, helper, 2)
        return self

    def __exit__(self, *exc):
        try:
            self._close_ws()
        except Exception:
            pass

    def eval(self, expr, timeout=60, await_promise=True):
        self.step += 1
        return cdp_eval(
            self._ws, expr, self.step, timeout=timeout, await_promise=await_promise
        )

    def api(self, method, path, body=None, quiet=False, max_retries=5):
        self.step += 1
        expr = "window.__api(%s, %s, %s).then(x => JSON.stringify(x))" % (
            json.dumps(method),
            json.dumps(path),
            "undefined" if body is None else json.dumps(body),
        )
        res = cdp_eval(self._ws, expr, self.step, timeout=120)
        data = json.loads(res) if res else {"status": None, "body": "no response"}
        for _ in range(max_retries):
            if data.get("status") == 429:
                wait = min(float(data.get("retry") or 1.5) + 0.5, 30)
                print(f"    [rate] waiting {wait:.1f}s ({path})")
                time.sleep(wait)
                self.step += 1
                res = cdp_eval(self._ws, expr, self.step, timeout=120)
                data = json.loads(res) if res else data
            else:
                break
        time.sleep(0.8)
        if not quiet and data.get("status") not in (200, 201, 204):
            print(
                f"  [{method} {path}] {data.get('status')}: {str(data.get('body'))[:200]}"
            )
        return data
