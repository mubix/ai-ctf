# Setup Runbook — Week-Of Checklist

Pick your own dates. A possible timeline working backward from event day (T-0):

- **T-5 to T-3 (weekend before):** Build the Docker stack and pull the model
  on the host that will run the platform.
- **T-2 (Tuesday):** Stand up the off-platform artifacts (GitHub repo, Gist,
  DNS record). DNS needs propagation time.
- **T-1 (Wednesday):** Dry run on the actual hardware at the venue.
- **T-0 (Thursday):** Event day.

---

## T-5 to T-3: Build the Docker images on the host

Do this **while the host still has internet** (the build pulls Python deps,
htmx, Ollama base image). Complete the model download and smoke checks before disconnecting.

```bash
# 1. Get the project onto the host
#    (any method works — git clone, scp, USB stick)
cd /opt
# (transfer the ai-ctf/ tree here, or wherever you prefer)
cd /opt/ai-ctf/platform

# 2. (Optional) Customize flags
#    Edit platform/flags.toml to give your event its own flavor.
$EDITOR flags.toml
python scripts/apply_flags.py    # stamps values into static files

# 3. Set the session secret (one time, persisted in .env)
echo "SESSION_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" > .env

# 4. Build the images
docker compose build

# 5. Pull the Ollama model (this takes ~10 minutes and ~4 GB)
docker compose up -d ollama
sleep 5
docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M
docker compose exec ollama ollama list   # confirm model is present

# 6. Bring up the rest of the stack
docker compose up -d

# 7. Smoke test
curl -sS -D - -o /dev/null http://localhost:18080/
# should return 200 OK with X-Powered-By: anvil-chatkit/0.3.1 and an X-Audit-Token header

curl http://localhost:18080/robots.txt
# should include the recon token in the trailing comment
```

After step 7, the stack runs offline. You can disconnect from the internet at this point.

---

## T-2: Stand up the off-platform artifacts

See `external_artifacts/README.md` for full instructions. Summary:

1. Set `[external] dns_domain`, `[external] github_org`, and (if not yet known)
   leave `[external] gist_url` for the moment — in `platform/flags.toml`.
2. Run `python platform/scripts/apply_flags.py` to stamp those values into the
   artifact files.
3. Create your GitHub org (or pick a user) and push the `anvil-chatkit` repo
   using the included `setup-history.sh` script.
4. Create the public Gist with the demo content; paste its URL into
   `flags.toml`, re-run `apply_flags.py`, and push the README update.
5. Set the TXT record at `<dns_label>.<dns_domain>` per `dns_records.txt`.
6. Run the verification commands at the bottom of
   `external_artifacts/README.md` to confirm all four external pieces are live.

If you don't want to run the external flag chain (flags #14–17), skip this
whole step and adjust `docs/ANSWER_KEY.md` to drop those flags.

---

## T-1: Dry run on the host hardware at the venue

Bring: the host machine, power, an Ethernet cable to the venue's switch (or a
small dedicated wifi AP if no wired LAN). The CTF box should be air-gapped from
the internet — players use their own devices for that.

### Network setup

- Plug the host into the venue switch (or set up a dedicated AP).
- Note its IP — `ip addr` will show something like `192.168.x.y` (write it on
  the whiteboard).
- Players connect their laptops to the same LAN.
- Players' internet is whatever the venue offers separately (laptop wifi).

### Smoke test from a separate machine on the LAN

```bash
CTF=<the-ip-from-ip-addr>

# Web up
curl -sS -D - -o /dev/null http://$CTF:18080/

# Robots flag
curl -s http://$CTF:18080/robots.txt | grep flag

# Logo + EXIF flag
curl -s http://$CTF:18080/static/logo.jpg -o /tmp/logo.jpg
exiftool /tmp/logo.jpg | grep -i flag
```

### Flag-by-flag walkthrough

For each of the 20 flags, take the role of a player and confirm you can retrieve it. Use `ANSWER_KEY.md` to verify. Time-box this at 90 minutes — if a flag takes you more than 5–8 minutes, the model may be too aligned for the event; consider:

- Shrinking the relevant guardrail clause in the system prompt
- Switching to a smaller / less-aligned model (e.g. `qwen2.5:3b-instruct-q4_K_M`)

Common dry-run gotchas:

- **Ollama hasn't pulled the model** — `docker compose exec ollama ollama list`. Pull again if missing.
- **Tool-call loop fails** — check `docker compose logs web`. The original chat loop caps tool rounds at six and returns a service-error message when it cannot finish. Guided lessons retain the input for recovery.
- **DB locked** — restart the web container only: `docker compose restart web`.
- **Player can't reach the box** — confirm same LAN, no wifi isolation, port 18080 not blocked.

---

## T-0: Event day

### Before players arrive (1 hour before)

1. Host powered on, plugged into LAN, `docker compose ps` shows all services healthy.
2. Whiteboard prepped with the scoreboard grid (see ANSWER_KEY.md).
3. Sticky notes + pens on each table.
4. Printed ANSWER_KEY.md kept private (your reference only).
5. The host's IP written on the whiteboard for everyone to see.

### Player briefing (5 minutes)

See `EVENT_DAY_NOTES.md` for the script.

### During the event

- Players hand you stickies; you verify against the answer key and update the whiteboard.
- Don't volunteer hints unless someone is genuinely stuck for 30+ minutes — let them struggle a bit.
- If multiple players are stuck on the same flag, broadcast a small hint to the whole room.
- Watch `docker stats` occasionally; if Ollama is pegging CPU and the queue looks bad, it'll self-recover but you may want to gently slow the room.

### Wrap-up (last 15 min)

- Final flag count.
- Announce top 3.
- Quick debrief — ask people what surprised them. (This is where the learning lands.)
