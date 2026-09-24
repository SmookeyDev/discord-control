#!/usr/bin/env python3
"""Read-only dump of a Discord guild's state (no writes, no secrets printed).

Usage: python3 state.py [--guild <id>] [--sp /tmp/discord_sp.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cdp import CdpSession  # noqa: E402

TYPE = {0: "text", 2: "voice", 4: "category", 5: "announce", 13: "stage", 15: "forum"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guild", required=True)
    ap.add_argument("--sp", default="/tmp/discord_sp.json")
    args = ap.parse_args()
    g = args.guild

    with CdpSession(sp_file=args.sp) as cdp:
        d = cdp.api("GET", f"/guilds/{g}")
        guild = json.loads(d["body"])
        print("== guild core ==")
        print(
            f"  name={guild.get('name')} icon={guild.get('icon')} "
            f"banner={guild.get('banner')} splash={guild.get('splash')}"
        )
        feats = guild.get("features", [])
        print(
            f"  COMMUNITY={'COMMUNITY' in feats} "
            f"MEMBER_VERIFICATION_GATE={'MEMBER_VERIFICATION_GATE_ENABLED' in feats}"
        )
        print(
            f"  rules={guild.get('rules_channel_id')} "
            f"updates={guild.get('public_updates_channel_id')} "
            f"premium_tier={guild.get('premium_tier')}"
        )

        d = cdp.api("GET", f"/guilds/{g}/channels")
        chans = json.loads(d["body"])
        print(f"\n== channels ({len(chans)}) by category ==")
        cats = [c for c in chans if c["type"] == 4]
        orphan = [c for c in chans if c["type"] != 4 and not c.get("parent_id")]
        for cat in sorted(cats, key=lambda x: x.get("position", 0)):
            kids = sorted(
                [c for c in chans if c.get("parent_id") == cat["id"]],
                key=lambda x: x.get("position", 0),
            )
            print(f"[{cat['name']}]")
            for k in kids:
                print(f"   {TYPE.get(k['type'], k['type'])}: {k['name']} ({k['id']})")
        if orphan:
            print("[no category]")
            for k in sorted(orphan, key=lambda x: x.get("position", 0)):
                print(f"   {TYPE.get(k['type'], k['type'])}: {k['name']} ({k['id']})")

        d = cdp.api("GET", f"/guilds/{g}/roles")
        roles = json.loads(d["body"])
        print(f"\n== roles ({len(roles)}) by position ==")
        for r in sorted(roles, key=lambda x: -x.get("position", 0)):
            flags = []
            if r.get("managed"):
                flags.append("managed")
            if r.get("permissions") and int(r["permissions"]) & 0x8:
                flags.append("ADMIN")
            print(
                f"  pos={r['position']:>3} {r['name']}{' [' + ','.join(flags) + ']' if flags else ''}"
            )

        d = cdp.api("GET", f"/guilds/{g}/onboarding", quiet=True)
        if d.get("status") == 200:
            ob = json.loads(d["body"])
            print(
                f"\n== onboarding == enabled={ob.get('enabled')} mode={ob.get('mode')} "
                f"prompts={len(ob.get('prompts', []))}"
            )
            for p in ob.get("prompts", []):
                print(
                    f"   - {p.get('title')} (required={p.get('required')}, "
                    f"{len(p.get('options', []))} options)"
                )

        d = cdp.api("GET", f"/guilds/{g}/member-verification", quiet=True)
        if d.get("status") == 200:
            print(f"\n== screening == {d['body'][:300]}")


if __name__ == "__main__":
    main()
