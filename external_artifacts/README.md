# External Artifacts — Setup Checklist

Four of the 20 flags (#14, #15, #16, #17) live OUTSIDE the CTF box on the public
internet. This directory contains everything you need to push to your own GitHub
account + DNS provider so those flags are discoverable.

If you don't want to run the off-platform half of the game, you can skip this
entirely — the platform still ships 16 solvable flags on its own (everything
except #14–17). Adjust your `docs/ANSWER_KEY.md` accordingly.

Total setup time: about 30 minutes once your accounts are ready.

The token values you're planting are configured in `platform/flags.toml`. Run
`python platform/scripts/apply_flags.py` first; it stamps the current values
into all the files in this directory so you don't have to chase strings.

---

## Pre-flight: customize the central config

```bash
# From the repo root
$EDITOR platform/flags.toml
```

At minimum, set these `[external]` keys to values you control:

| Key            | Example                                | Notes                                             |
| -------------- | -------------------------------------- | ------------------------------------------------- |
| `dns_domain`   | `your-domain.example`                  | A domain you can add TXT records to               |
| `dns_label`    | `_anvil-audit`                         | Underscored TXT subdomain                         |
| `github_org`   | `your-github-user` or `your-github-org`| Where you'll push the `anvil-chatkit` repo        |
| `gist_url`     | (fill in after creating the Gist)      | Public Gist URL containing the demo               |

Then refresh the artifact files:

```bash
python platform/scripts/apply_flags.py
```

---

## 1. (Optional) Create a GitHub org

You can host the `anvil-chatkit` repo under either:

- A **GitHub org** you own (e.g. `anvil-industries`) — sharper supply-chain story,
  matches the in-platform fingerprint. Recommended.
- A personal user account — works too; just set `github_org` to your username.

To make a new org: top-right `+` → "New organization" → free plan → name it
whatever you want. Skip member invites.

---

## 2. Push the `anvil-chatkit` repo (carries flags #14 + #15)

```bash
cd external_artifacts/anvil_chatkit

# Initialize a fresh repo (this directory may already contain a .git folder
# from when the artifacts were generated — delete it so you start clean).
rm -rf .git
git init -b main
git config user.name  "Anvil Engineering"
git config user.email "engineering@anvil.example"

bash setup-history.sh    # creates 6 commits, one carrying flag #15

# Create the GitHub repo via the web UI (or `gh repo create` if you have it),
# then push:
git remote add origin git@github.com:YOUR-ORG/anvil-chatkit.git
git push -u origin main
```

`setup-history.sh` makes 6 commits. Commit #4 carries **flag #15** (the
`commit_token` value from `flags.toml`) in its message. The README contains
**flag #14** (`readme_token`).

Verify after push:

- README is rendered on the repo home page with `audit_token` visible.
- `git log --oneline` shows 6 commits, one of which mentions the flag.

---

## 3. Create the public Gist (flag #16)

See `gist_content.md` for the exact content. In short:

1. Go to https://gist.github.com/ (signed in as a personal account).
2. Filename: `anvil_chatkit_demo.py`.
3. Description: `Quick demo: building a 2-persona chat with anvil-chatkit`.
4. Paste the content from `gist_content.md`.
5. Click "Create public gist".
6. **Copy the resulting URL.**

### 3a. Wire the Gist URL back into the package README

```bash
# From the repo root: put the Gist URL into the central config,
# then re-apply so the chatkit README picks it up.
$EDITOR platform/flags.toml      # set [external] gist_url = "https://gist.github.com/..."
python platform/scripts/apply_flags.py

# Add a follow-up commit and push
cd external_artifacts/anvil_chatkit
git add README.md
git commit -m "README: add link to public demo Gist"
git push
```

This 7th commit completes the discovery chain.

---

## 4. Set the DNS TXT record (flag #17)

See `dns_records.txt` for the exact value (auto-stamped from `flags.toml`):

1. Log into your DNS provider for the domain you set as `dns_domain`.
2. Add a TXT record:
   - **Name:** `_anvil-audit` (or whatever you set `dns_label` to)
   - **Value:** `anvil-industries-audit-canary:flag{ozone_lantern}` (use whatever
     `[flags.external] dns_token` is in your config)
   - **TTL:** 300 seconds
3. Save and wait 5 minutes.
4. Verify:
   ```
   dig TXT _anvil-audit.YOUR-DOMAIN.example @8.8.8.8 +short
   ```

Expected output: `"anvil-industries-audit-canary:flag{ozone_lantern}"`

---

## Verification checklist (run before bed Tuesday night)

```bash
# anvil-chatkit repo is public and viewable
curl -s https://api.github.com/repos/YOUR-ORG/anvil-chatkit | jq .visibility

# README renders with flag #14
curl -s https://raw.githubusercontent.com/YOUR-ORG/anvil-chatkit/main/README.md \
  | grep -E 'audit_token:\s*flag'

# Git history has flag #15 (run inside the cloned repo)
git -C external_artifacts/anvil_chatkit log --all --oneline | grep -i 'Audit canary'

# Gist exists and is public (open URL in browser, content visible without login)

# DNS TXT record is live
dig TXT _anvil-audit.YOUR-DOMAIN.example @8.8.8.8 +short
```

If all four return non-empty results, the external pieces are ready.

---

## Discovery chain (for reference)

Players don't need to know any of this — but here's how the four external flags
chain together so you can sanity-check:

```
1. Player fingerprints platform → sees X-Powered-By: anvil-chatkit/0.3.1
                                           and HTML comment <!-- powered by anvil-chatkit -->
2. Player searches GitHub for "anvil-chatkit"
   → finds github.com/YOUR-ORG/anvil-chatkit
3. Reads README.md
   → flag #14 (audit_token field)
   → discovers _anvil-audit.YOUR-DOMAIN.example TXT canary
   → discovers Gist URL
4. Runs dig TXT _anvil-audit.YOUR-DOMAIN.example
   → flag #17
5. Opens Gist URL
   → flag #16
6. Runs git log on the cloned repo
   → flag #15
```
