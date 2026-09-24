#!/usr/bin/env python3
"""Capture Discord anti-abuse headers via CDP Network and save NON-SECRET
ones to /tmp/discord_sp.json. The Authorization header is never persisted.

Usage: python3 headers.py [--sp /tmp/discord_sp.json] [--timeout 30]

Run BEFORE the app is used so a reload captures real requests. Requires the
Discord app running with --remote-debugging-port=9222.
"""

import argparse
import base64
import json
import time
import urllib.request
from websockets.sync.client import connect

CDP_HTTP = "http://127.0.0.1:9222"
KEEP = {
    "x-super-properties": "x_super_properties",
    "x-context-properties": "x_context_properties",
    "x-discord-locale": "x_discord_locale",
    "x-discord-timezone": "x_discord_timezone",
    "x-installation-id": "x_installation_id",
    "x-debug-options": "x_debug_options",
}
REDACT = {"authorization", "x-authorization"}


def page_ws_url():
    targets = json.loads(urllib.request.urlopen(f"{CDP_HTTP}/json/list").read())
    pages = [
        t
        for t in targets
        if t.get("type") == "page" and "discord.com" in t.get("url", "")
    ]
    if not pages:
        raise SystemExit("no discord page target")
    return pages[0]["webSocketDebuggerUrl"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sp", default="/tmp/discord_sp.json")
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args()

    ws = connect(page_ws_url(), max_size=30 * 1024 * 1024)
    ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
    ws.send(
        json.dumps({"id": 2, "method": "Page.reload", "params": {"ignoreCache": False}})
    )

    found = {}
    url_path = None
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv(timeout=max(0.5, deadline - time.time())))
        except Exception:
            break
        method = msg.get("method")
        if method == "Network.requestWillBeSent":
            req = msg["params"]["request"]
            url = req.get("url", "")
            if "/api/v9" in url:
                headers = {k.lower(): v for k, v in req.get("headers", {}).items()}
                if "x-super-properties" in headers:
                    for k, key in KEEP.items():
                        if headers.get(k):
                            found[key] = headers[k]
                    url_path = url.split("discord.com", 1)[-1]
                    break  # headers are enough; stop before bodies arrive
    try:
        ws.close()
    except Exception:
        pass

    if not found:
        raise SystemExit("[-] no api request captured; open the app and try again")

    # safety: never store anything that looks like an auth token
    for k in list(found):
        if k.lower() in REDACT:
            del found[k]
    out = {"url_path": url_path, **found}
    with open(args.sp, "w") as f:
        json.dump(out, f, indent=2)
    sp_b64 = out.get("x_super_properties", "")
    try:
        decoded = json.loads(base64.b64decode(sp_b64))
        out["super_properties_decoded"] = decoded
        with open(args.sp, "w") as f:
            json.dump(out, f, indent=2)
    except Exception:
        pass
    print(f"[+] saved non-secret headers to {args.sp}: {sorted(out)}")


if __name__ == "__main__":
    main()
