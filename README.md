# ai-ctf

A local **AI Capture-the-Flag** with guided lessons for technologists
new to prompt injection. Players can also explore six AI personas (one hidden) that protect
20 flags via prompt-injection, tool-call abuse, business-logic manipulation,
supply-chain fingerprinting, web recon, and OSINT.

The guided path covers direct injection, tool authorization, and injection through an
editable knowledge article. It provides hints, saved attempts, tool evidence, completion
feedback, and protected tool comparisons. The original practice labs retain manual
event scoring. Model inference runs locally through Ollama; after the build and
model download, the core platform needs no internet connection.

**Email Joe in Product Sales** adds a simulated inbox and Windows-style desktop.
Write an email that Joe's assistant will read, then watch the actual model summary
and recorded actions. Three objectives cover a misleading sales brief, disclosure
of a fictional internal file, and an unauthorized discount. No mail server, Windows,
Wine, or additional model is required.

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
    ├── ANSWER_KEY.md          ← guided solutions + original 20-flag answers
    ├── CHEAT_SHEET.md         ← working solutions + tiered hints (GM only)
    ├── OPERATIONS.md          ← updates, backups, and troubleshooting
    ├── SETUP_RUNBOOK.md       ← week-of, step-by-step
    └── EVENT_DAY_NOTES.md     ← briefing script + troubleshooting
```

Use the quick start below for the guided path. The [operations guide](docs/OPERATIONS.md)
covers updates, backups, recovery, and pre-event checks.
The answer key, cheat sheet, setup runbook, and event notes describe the optional original CTF format.

---

## Requirements

- Docker + Docker Compose (Compose v2).
- Enough RAM for the configured model, application, operating system, and other workloads.
  The default model download is about 4.7 GB; that is not its total runtime memory requirement.
  Capacity depends on the hardware and model; check with the intended number of players before an event.
- Python 3.11+ on the host (only used for the `apply_flags.py` and
  `dump_chats.py` helper scripts — the app itself runs inside Docker).
- `exiftool` (only needed if you change the EXIF flag and want
  `apply_flags.py` to re-stamp the logo).
- Internet access during build (for `pip install` and the Ollama model pull).
  After that the core local stack runs offline. The optional external OSINT chain needs internet access.

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
open http://localhost:18080/    # or your-machine-ip:18080 on another laptop
```

Register a username; the platform generates a 12-character password and shows
it once. Save it for later. You are signed in automatically and can select
**Start learning**. Returning players can log in to resume saved progress.

The Compose project is named `ai-ctf` and has its own network and model volume.
Only the web UI publishes a host port: `18080` by default. Set `CTF_WEB_PORT`
in `platform/.env` to choose another port. Ollama and the decoy have no published
host ports; the app connects to its own Ollama container. No GPU passthrough is
configured. CPU and memory are still shared with other workloads on the host.

If upgrading a stack created under a different Compose project name, keep that
name with `docker compose -p YOUR_EXISTING_PROJECT ...` to reuse its containers
and model volume. Changing project names creates a separate stack.

The guided Customer Service lesson uses a fresh audit token per attempt rather
than the fixed event token. It recognizes plain-text disclosures and distinguishes
viewing the worked example from solving without it. Fresh attempts preserve
previous conversations and earned progress. Its beginner profile deliberately trusts a
claimed support-operator role; the original Customer Service practice bot stays separate.
Existing guided attempts retain their earlier profile until the player starts fresh.

Two more guided lessons use isolated fictional fixtures: HR tool access, then an editable
knowledge article that can redirect a simulated reply. They execute schema-validated model action requests against those fixture tools,
record the tool calls, and validate their results. Players can replay the same arguments through a permission check
and inspect a legitimate-use control. This comparison checks the tool boundary, not a
second model run. Nothing is emailed and no real HR service is connected. The original
personas remain self-directed practice labs with their original answers and manual scoring.

The email scenario is available from **All lessons → Email Joe**. Its File Explorer
uses familiar paths such as `C:\Users\Joe\Documents\Sales`; these identify in-memory
fixtures and never access the host filesystem. Each email gets fresh fictional files,
an outbox, and a sales record. Story events are labeled separately from observed model
and tool activity. File-disclosure and record-change objectives require executed actions,
not a claim in the summary. Enable **Enforce Joe's tool permissions** to rerun either
tool objective with application checks, then send a clean example to check normal use.
Attempts, hints, worked-example use, and progress are saved.

For an existing installation, application/template changes require rebuilding
the web image; restarting alone does not copy updated code:

```bash
cd platform
docker compose up -d --build web
```

Lesson tables are created on startup without deleting existing accounts or chat history.
Follow the [operations guide](docs/OPERATIONS.md) to back up an existing installation
before updating and check that players can resume their lessons afterward.

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
python3 scripts/apply_flags.py        # stamps values into static files
docker compose up -d --build web decoy # copies updated assets into the images
```

`apply_flags.py` updates the files that aren't loaded by Python at runtime:

- `data/init.sql` (CEO salary, flag #4)
- `decoy/html/private/index.html` and `decoy/html/internal-tools/index.html`
- `app/static/logo.jpg` EXIF metadata (flag #20 — needs `exiftool` on PATH)
- `external_artifacts/` files (chatkit README, gist content, DNS record,
  setup-history.sh commit message)

After changing any flag values, **also update `docs/ANSWER_KEY.md`** so your
verifier sheet matches.

Rebuilding does not update employee rows already in the SQLite database: the seed uses
`INSERT OR IGNORE`. Changing the CEO salary in an existing event still requires a targeted
fixture migration. Do not delete the player database to apply that change.

If you want to add or remove flags entirely (change which personas exist, drop
the external chain, add a new tool), edit `platform/app/personas/__init__.py`
and `platform/app/tools.py` directly. There's no DSL — the personas ARE the
game.

---

## Difficulty knobs

- **Loosen the persona prompts** (`platform/app/personas/__init__.py`) — fewer
  guardrail clauses, fewer "NEVER" lines, fewer explicit refusal examples.
  Players' first-attempt success rate goes up.
- **Change the model** — edit `OLLAMA_MODEL` in `docker-compose.yml`, pull that model,
  and run `docker compose up -d web` to apply the configuration. Model size alone does
  not establish difficulty. Recheck normal tasks, worked examples, native tool calls,
  and structured action responses using the [pre-event checks](docs/OPERATIONS.md#pre-event-checks).

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

The original attack catalog and historical example prompts are in `docs/CHEAT_SHEET.md`.

---

## Operating the event

`docs/SETUP_RUNBOOK.md` is the week-of checklist (build → external artifacts →
dry run → event day). `docs/EVENT_DAY_NOTES.md` has the player-briefing script,
the tiered hint catalog, and a troubleshooting table.

For event-day forensics — "who actually solved what?" — run
`platform/scripts/dump_chats.py` against the bind-mounted SQLite DB to produce
a self-contained HTML report with per-message flag-detection chips. These are substring
matches, not proof that an assistant disclosed a secret or executed a tool. The guided
lessons keep their own validated completion records.

The default `ctf_log.html` export, runtime data, local environment files, and release
archives are ignored by Git. Keep custom-named exports and deployment backups outside
the checkout or in the ignored `platform/data/` directory. Player records, credentials,
and chat exports should stay private.

---

## License

MIT. See `LICENSE`.

---

## Acknowledgments

Created by [Rob Fuller (mubix)](https://github.com/mubix) for hands-on AI security
training. Code largely AI-generated; design decisions and content owned by a human.
