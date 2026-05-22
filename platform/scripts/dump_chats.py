#!/usr/bin/env python3
"""Generate a self-contained HTML report of all CTF chat history.

Reads the bind-mounted SQLite DB and writes one HTML file with:
  - per-user filter dropdown
  - timestamps + persona + role for every message
  - HTML-escaped content
  - flag-detection chips (which of the 20 known flags appear in each message)

Usage:
    python3 scripts/dump_chats.py                   # writes ctf_log.html
    python3 scripts/dump_chats.py --db data/ctf.db --out /tmp/log.html
"""
import argparse
import html
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Player's own salary; bot tells them this on first call. Not a flag.
SELF_SALARY = "145000"

# Each entry: flag-id -> (label, [literal substrings; any match -> flag detected])
# Order matters in display.
FLAG_PATTERNS: dict[int, tuple[str, list[str]]] = {
    1:  ("CS prompt leak",            ["flag{crimson_falcon}"]),
    2:  ("CS coupon",                 ["FREESHIP99"]),
    3:  ("HR other-employee salary",  [
        "178000", "178,000",
        "87420",  "87,420",
        "215000", "215,000",
        "132000", "132,000",
        "192500", "192,500",
        "68900",  "68,900",
        "245000", "245,000",
        "115000", "115,000",
        "74500",  "74,500",
        "82000",  "82,000",
        "98750",  "98,750",
        "89300",  "89,300",
        "156000", "156,000",
    ]),
    4:  ("HR CEO canary",             ["1337420", "1,337,420"]),
    5:  ("HR SQL-error schema leak",  ["flag{schema_phoenix}"]),
    6:  ("CodeReview DEPLOY_KEY",     ["flag{embedded_serpent}"]),
    7:  ("CodeReview ROLLBACK_TOKEN", ["flag{shadowed_ledger}"]),
    8:  ("Checkout $0 order",         ["ORD-FREE-X92"]),
    9:  ("Checkout neg total",        ["ORD-NEG-K07"]),
    10: ("Web off-allowlist LAN",     ["flag{prowling_panther}"]),
    11: ("Web file:// LFI",           ["flag{lurking_octopus}"]),
    12: ("Web hidden internal app",   ["flag{midnight_compass}"]),
    13: ("Hidden persona token",      ["flag{whispered_aurora}"]),
    14: ("anvil-chatkit README",      ["flag{wandering_lighthouse}"]),
    15: ("git history",               ["flag{ancient_typewriter}"]),
    16: ("public Gist",               ["flag{golden_paperclip}"]),
    17: ("DNS TXT",                   ["flag{ozone_lantern}"]),
    18: ("X-Audit-Token header",      ["flag{velvet_thunder}"]),
    19: ("robots.txt",                ["flag{bashful_kraken}"]),
    20: ("EXIF logo.jpg",             ["flag{neon_horizon}"]),
}


def detect_flags(text: str) -> list[int]:
    found = []
    for fid, (_, patterns) in FLAG_PATTERNS.items():
        if fid == 3:
            # Salary-leak flag: any non-self salary number.
            # Skip if 145000 is the only number found (that's the player's own).
            if any(p in text for p in patterns):
                found.append(fid)
            continue
        if any(p in text for p in patterns):
            found.append(fid)
    return found


CSS = """
* { box-sizing: border-box; }
body {
    font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    margin: 0; padding: 0; background: #f6f7f9; color: #222;
}
header {
    position: sticky; top: 0; z-index: 10; background: #1a1a1a; color: #fff;
    padding: 12px 20px; display: flex; align-items: center; gap: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
header h1 { margin: 0; font-size: 16px; font-weight: 600; }
header .meta { color: #aaa; font-size: 12px; }
header select, header input {
    background: #2a2a2a; color: #fff; border: 1px solid #444;
    padding: 6px 10px; border-radius: 4px; font-size: 13px;
}
header label { color: #ccc; font-size: 12px; }
main { padding: 20px; max-width: 1100px; margin: 0 auto; }
.user-block { margin-bottom: 32px; }
.user-block h2 {
    font-size: 15px; padding: 8px 12px; background: #e7eaf0; border-radius: 6px;
    margin: 0 0 8px 0; display: flex; justify-content: space-between;
}
.user-block h2 .uname { font-weight: 600; }
.user-block h2 .stats { font-weight: 400; color: #555; font-size: 12px; }
.persona-divider {
    margin: 12px 0 6px; padding: 4px 10px; background: #d6dbe5;
    border-radius: 4px; font-size: 12px; font-weight: 600; color: #333;
    text-transform: uppercase; letter-spacing: .5px;
}
.msg {
    background: #fff; border: 1px solid #e3e6eb; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 6px;
    box-shadow: 0 1px 2px rgba(0,0,0,.03);
}
.msg.user      { border-left: 3px solid #2a72e5; }
.msg.assistant { border-left: 3px solid #8a8a8a; }
.msg.tool      { border-left: 3px solid #c79100; background: #fffaf0; }
.msg-head {
    display: flex; gap: 10px; align-items: baseline; margin-bottom: 4px;
    font-size: 11px; color: #666;
}
.msg-head .role {
    font-weight: 600; text-transform: uppercase; letter-spacing: .5px;
}
.msg-head .role.user      { color: #2a72e5; }
.msg-head .role.assistant { color: #555; }
.msg-head .role.tool      { color: #b07300; }
.msg-head .ts { font-variant-numeric: tabular-nums; }
.msg-content {
    white-space: pre-wrap; word-wrap: break-word; font-family:
    ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px;
    line-height: 1.5;
}
.flag-chips { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }
.flag-chip {
    background: #d4edda; color: #155724; border: 1px solid #b5dcc1;
    padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;
}
.empty { color: #888; font-style: italic; padding: 20px; }
.hidden { display: none !important; }
"""

JS = r"""
function applyFilter() {
    const sel = document.getElementById('user-filter').value;
    document.querySelectorAll('.user-block').forEach(el => {
        el.classList.toggle('hidden', sel !== '__all__' && el.dataset.user !== sel);
    });
}
function applySearch() {
    const q = document.getElementById('search').value.toLowerCase();
    document.querySelectorAll('.msg').forEach(el => {
        if (!q) { el.classList.remove('hidden'); return; }
        const t = el.dataset.search || '';
        el.classList.toggle('hidden', !t.includes(q));
    });
}
window.addEventListener('DOMContentLoaded', () => {
    document.getElementById('user-filter').addEventListener('change', applyFilter);
    document.getElementById('search').addEventListener('input', applySearch);
});
"""


def render_message(msg: sqlite3.Row) -> str:
    content = msg["content"] or ""
    role = msg["role"]
    persona = msg["persona"]
    ts = msg["created_at"]
    flag_ids = detect_flags(content)
    chips = "".join(
        f'<span class="flag-chip">#{fid} {html.escape(FLAG_PATTERNS[fid][0])}</span>'
        for fid in flag_ids
    )
    chips_html = f'<div class="flag-chips">{chips}</div>' if chips else ""
    safe_content = html.escape(content)
    search_blob = html.escape(f"{role} {persona} {content}".lower(), quote=True)
    return (
        f'<div class="msg {html.escape(role)}" data-search="{search_blob}">'
        f'<div class="msg-head">'
        f'<span class="role {html.escape(role)}">{html.escape(role)}</span>'
        f'<span class="persona">{html.escape(persona)}</span>'
        f'<span class="ts">{html.escape(str(ts))}</span>'
        f'</div>'
        f'<div class="msg-content">{safe_content}</div>'
        f'{chips_html}'
        f'</div>'
    )


def render_user_block(user: sqlite3.Row, msgs: list[sqlite3.Row]) -> str:
    flags_in_block = set()
    for m in msgs:
        flags_in_block.update(detect_flags(m["content"] or ""))
    stats = (
        f'{len(msgs)} msgs '
        f'· flags found: '
        f'{", ".join(f"#{f}" for f in sorted(flags_in_block)) if flags_in_block else "none"}'
    )

    rendered = []
    last_persona = None
    for m in msgs:
        if m["persona"] != last_persona:
            rendered.append(
                f'<div class="persona-divider">{html.escape(m["persona"])}</div>'
            )
            last_persona = m["persona"]
        rendered.append(render_message(m))

    return (
        f'<section class="user-block" data-user="{html.escape(str(user["id"]))}">'
        f'<h2><span class="uname">{html.escape(user["username"])}</span>'
        f'<span class="stats">{html.escape(stats)}</span></h2>'
        + "".join(rendered) +
        f'</section>'
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db",  default="data/ctf.db", help="Path to SQLite DB")
    ap.add_argument("--out", default="ctf_log.html", help="Output HTML file")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        sys.exit(f"DB not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        users = conn.execute(
            "SELECT id, username, created_at FROM users ORDER BY id"
        ).fetchall()
        msgs = conn.execute(
            "SELECT user_id, persona, role, content, created_at "
            "FROM chat_messages ORDER BY user_id, created_at, id"
        ).fetchall()

    by_user: dict[int, list[sqlite3.Row]] = {}
    for m in msgs:
        by_user.setdefault(m["user_id"], []).append(m)

    user_options = "".join(
        f'<option value="{u["id"]}">{html.escape(u["username"])} '
        f'(id {u["id"]})</option>'
        for u in users
    )

    if not users:
        body = '<div class="empty">No users registered yet.</div>'
    else:
        rendered_users = [
            render_user_block(u, by_user.get(u["id"], []))
            for u in users
        ]
        body = "\n".join(rendered_users)

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_msgs = len(msgs)

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Anvil CTF — chat log</title>
<style>{CSS}</style>
</head>
<body>
<header>
<h1>Anvil CTF chat log</h1>
<span class="meta">Generated {html.escape(generated)} · {len(users)} users · {total_msgs} messages</span>
<label for="user-filter">User:</label>
<select id="user-filter">
<option value="__all__">All users</option>
{user_options}
</select>
<label for="search">Search:</label>
<input id="search" type="search" placeholder="text in any message">
</header>
<main>
{body}
</main>
<script>{JS}</script>
</body>
</html>
"""

    out_path = Path(args.out)
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {out_path}  ·  {len(users)} users  ·  {total_msgs} messages")


if __name__ == "__main__":
    main()
