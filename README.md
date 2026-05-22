# ai-ctf

A self-contained, four-hour **AI Capture-the-Flag** for mixed-skill security
practitioners. Players talk to six AI personas (one hidden) that protect
20 flags via prompt-injection, tool-call abuse, business-logic manipulation,
supply-chain fingerprinting, web recon, and OSINT.

Originally built to be run on a single Mini-PC at an in-person event — no GPU,
no internet, no admin UI. Players use sticky notes; flags are scored on a
whiteboard. The platform itself is small enough that you can stand it up on a
laptop in 30 minutes.

This code was largely AI-generated. The point is not to read the source for
craftsmanship lessons — it's to run the event and learn the attack
techniques first-hand. Bring your own opinions to the prompt design.

---

## What's in the box

```
ai-ctf/
├── README.md                  ← you are here
├── LICENSE                    ← MIT
├── platform/                  ← everything that runs in Docker
│   ├── flags.toml             ← central config: edit this to customize flag values
│   ├── docker-compose.yml     ← three services: web, ollama, decoy
│   ├── Dockerfile             ← the web app image
│   ├── app/                   ← FastAPI source (config, personas, tools, chat)
│   ├── data/init.sql          ← SQLite schema + fake-employee seed data
│   ├── decoy/                 ← tiny nginx with two flag pages
│   └── scripts/
│       ├── apply_flags.py     ← stamps flags.toml values into static files
│       ├── render_secret.py   ← runs at container startup
│       └── dump_chats.py      ← exports the chat log as HTML (event-day tool)
├── external_artifacts/        ← what you push to GitHub / Gist / DNS
│   ├── README.md              ← setup checklist
│   ├── anvil_chatkit/         ← the fake supply-chain package
│   ├── gist_content.md        ← paste this into a public Gist
│   └── dns_records.txt        ← TXT record to add to your domain
└── docs/                      ← run-the-event paperwork
    ├── ANSWER_KEY.md          ← print this; verify sticky notes against it
    ├── CHEAT_SHEET.md         ← working solutions + tiered hints (GM only)
    ├── SETUP_RUNBOOK.md       ← week-of, step-by-step
    └── EVENT_DAY_NOTES.md     ← briefing script + troubleshooting
```

The four docs under `docs/` are the most useful files in this repo. Read them
in the order above before running the event.

---

## Requirements

- Docker + Docker Compose (Compose v2).
- ~32 GB RAM on the host machine (the default Qwen 2.5 7B Q4 model loads to
  ~6 GB; the rest is headroom for concurrent inference under a 20-player load).
  An 8 GB RAM laptop running a single tester also works fine.
- Python 3.11+ on the host (only used for the `apply_flags.py` and
  `dump_chats.py` helper scripts — the app itself runs inside Docker).
- `exiftool` (only needed if you change the EXIF flag and want
  `apply_flags.py` to re-stamp the logo).
- Internet access during build (for `pip install` and the Ollama model pull).
  After that the stack runs fully offline.

---

## Quick start

```bash
git clone https://github.com/mubix/ai-ctf.git
cd ai-ctf/platform

# 1. Session secret
echo "SESSION_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" > .env

# 2. (Optional) Customize flag values — see "Customizing the flags" below.
#    Default values work fine for a smoke test.

# 3. Build and start
docker compose build
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M
docker compose up -d

# 4. Open the platform
open http://localhost:8000/    # or your-machine-ip:8000 on another laptop
```

Register a username; the platform generates a 12-character password and shows
it once. Log in and start playing.

The platform self-contains 16 of the 20 flags. The remaining 4 (#14–17) require
external infrastructure that you push yourself — see
`external_artifacts/README.md`. Skip that step if you only want the in-platform
half.

---

## Customizing the flags

All 20 flag values live in **one file**: `platform/flags.toml`. Edit values
there to give your event its own flavor (different `flag{adjective_noun}`
tokens, different coupon code, different CEO salary, etc.).

After editing:

```bash
cd platform
python scripts/apply_flags.py    # stamps values into static files
docker compose restart web decoy # picks up the new TOML
```

`apply_flags.py` updates the files that aren't loaded by Python at runtime:

- `data/init.sql` (CEO salary, flag #4)
- `decoy/html/private/index.html` and `decoy/html/internal-tools/index.html`
- `app/static/logo.jpg` EXIF metadata (flag #20 — needs `exiftool` on PATH)
- `external_artifacts/` files (chatkit README, gist content, DNS record,
  setup-history.sh commit message)

After changing any flag values, **also update `docs/ANSWER_KEY.md`** so your
verifier sheet matches.

If you want to add or remove flags entirely (change which personas exist, drop
the external chain, add a new tool), edit `platform/app/personas/__init__.py`
and `platform/app/tools.py` directly. There's no DSL — the personas ARE the
game.

---

## Difficulty knobs

- **Loosen the persona prompts** (`platform/app/personas/__init__.py`) — fewer
  guardrail clauses, fewer "NEVER" lines, fewer explicit refusal examples.
  Players' first-attempt success rate goes up.
- **Swap to a smaller model** — `qwen2.5:3b-instruct-q4_K_M` jailbreaks more
  easily. Edit `OLLAMA_MODEL` in `docker-compose.yml`, pull the new model,
  restart `web`.
- **Swap to a stronger model** — pick a larger Qwen / Llama / Mistral build
  if your hardware can run it. Tool-calling support varies by model; the chat
  loop is in `platform/app/chat.py`.

---

## What players actually do

- **Customer Service bot** — extract the system prompt; find a hidden manager
  coupon.
- **HR bot** — pull other employees' salaries; coax a SQL error that leaks
  schema info.
- **Code Review bot** — embed prompt-injection in code comments and docstrings
  to extract production secrets.
- **Checkout bot** — convince it to place a $0 order, then a negative-total
  order.
- **Web Retrieval bot** — escape the URL allowlist; reach an internal LAN host;
  trigger a `file://` LFI via the LLM.
- **Hidden 6th persona** — discover it through clues from other bots / recon.
- **Web recon** — HTTP headers, robots.txt, EXIF metadata.
- **Supply-chain OSINT** — fingerprint the platform from headers, find the
  GitHub repo, dig through commit history, follow links to a public Gist,
  query DNS.

The full attack catalog with working prompts (verified against Qwen 2.5 7B) is
in `docs/CHEAT_SHEET.md`.

---

## Operating the event

`docs/SETUP_RUNBOOK.md` is the week-of checklist (build → external artifacts →
dry run → event day). `docs/EVENT_DAY_NOTES.md` has the player-briefing script,
the tiered hint catalog, and a troubleshooting table.

For event-day forensics — "who actually solved what?" — run
`platform/scripts/dump_chats.py` against the bind-mounted SQLite DB to produce
a self-contained HTML report with per-message flag-detection chips.

---

## License

MIT. See `LICENSE`.

---

## Acknowledgments

Built for [Rob Fuller (mubix)](https://github.com/mubix)'s in-house team CTF
night, then opened up because the rest of the security community might find it
useful too. Code largely AI-generated; design decisions and content owned by a
human.
