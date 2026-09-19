# Operating the platform

Use the [quick start](../README.md#quick-start) for a new installation. Run Docker
Compose commands from `platform/`. The default project name is `ai-ctf`; if your
existing installation uses another name, pass `-p YOUR_EXISTING_PROJECT` to every
Compose command below to keep using its containers and model volume.

## Transfer a complete installation

A fresh installation needs the complete source tree, including
`platform/docker-compose.yml`, both Dockerfiles, `platform/requirements.txt`,
`platform/data/init.sql`, and the application, decoy, and helper scripts.
From the repository root, create a source archive of the current commit:

```bash
git archive --format=tar.gz --output=ai-ctf-source.tar.gz HEAD
```

Extract it into your chosen installation directory, then follow the quick start.
The archive excludes untracked files, local configuration, player data, and model
files. Building the images and downloading the model require internet access.

## Back up and update

Schedule updates while players are away. Keep a copy of the currently installed
source and configuration outside the checkout so you can restore it if needed.
Preserve `platform/.env`, customized `platform/flags.toml`, and `platform/data/`.
Do not replace those files with archive defaults or use a transfer option that
deletes files found only on the target.

Before replacing the application, stop web writes and back up the database:

```bash
docker compose stop web
if [ -f data/ctf.db ]; then
  cp data/ctf.db "data/ctf.db.backup-$(date +%Y%m%d-%H%M%S)"
fi
```

Copy the updated source into place, then rebuild and start the web service:

```bash
docker compose up -d --build --no-deps web
docker compose ps
docker compose exec ollama ollama list
```

Restarting alone does not copy application or template changes into the image.
If decoy assets changed, also run `docker compose up -d --build --no-deps decoy`.
If you changed the model, pull it through this project's Ollama service before
starting web. Keep the session secret unchanged so existing logins remain valid.
Lesson tables are created automatically without clearing accounts or chat history.

## Pre-event checks

Use a disposable player account on the hardware and network intended for the event.
Repeat these checks after changing the model or lesson prompts; successful attacks
can vary between responses.

1. Register, save the generated password, sign out, and sign back in. Open
   **Start learning** and confirm saved attempts resume.
2. In each guided lesson, try its normal task before attempting an injection.
   Confirm ordinary answers do not mark the attack objective complete.
3. Try the hints and worked example. Check that a successful attack produces
   completion feedback and a debrief. In the HR and knowledge-article lessons,
   inspect the tool evidence and protected comparison.
4. Start a fresh attempt. Confirm previous conversations and earned progress
   remain available. Check multiline input and navigation on a player's device.
5. If running the original practice labs, check the selected challenges against
   the [answer key](ANSWER_KEY.md). Allow time for the model to refuse a prompt
   and for the player to try another approach.
6. Try simultaneous requests from the intended number of players. Confirm response
   times remain usable before committing to the event's group size.

## Troubleshooting and recovery

| Symptom | Action |
| --- | --- |
| Player cannot connect | Check the host address, firewall, and configured `CTF_WEB_PORT` (default `18080`). |
| Model unavailable | Check `docker compose logs --tail=100 ollama` and `docker compose exec ollama ollama list`. Pull the configured model if missing. If Ollama is still starting, wait briefly and retry. |
| Service error in a lesson | Check `docker compose logs --tail=100 web`. After restoring the service, retry the retained input. |
| Request interrupted by a restart | Allow up to 210 seconds for the running request to become retryable. |
| Assistant refuses the attack | Use the lesson hints and a different framing. A refusal alone is not a service failure. |
| Updated UI is missing | Rebuild the web image; restarting a container does not update its source. |

For an application rollback, restore the previous source and configuration and
rebuild web. Restore the database only if necessary: stop web first, replace
`data/ctf.db` with the backup, then start web. Restoring a database discards player
activity recorded after that backup. Keep backups and logs private.

## Automated checks without a model

From the repository root, in a Python environment with
`platform/requirements.txt` installed:

```bash
python3 -m unittest discover -s platform/tests -v
```

These tests replace inference calls with controlled responses and use temporary
databases. They do not require a model or change event data. They supplement the
pre-event checks; model behavior still needs checking on the event host.
