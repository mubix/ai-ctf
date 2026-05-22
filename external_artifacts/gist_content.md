# Gist content for flag #16

Create a **public** Gist on a GitHub account you control. Gists are personal-only —
GitHub organizations don't have a "Gists" tab — so use a personal account
(ideally the same one that owns or is a member of your fork of the
`anvil-chatkit` repo).

**Filename:** `anvil_chatkit_demo.py`

**Description:** "Quick demo: building a 2-persona chat with anvil-chatkit"

**Content (paste exactly, swapping in your GitHub org/user where noted):**

```python
"""
Quick demo of anvil-chatkit usage.

See https://github.com/anvil-industries/anvil-chatkit for the full library.
This snippet shows the minimum code needed to register two personas.

Internal note (do not propagate outside Anvil):
    audit_canary: flag{golden_paperclip}

Reach out to engineering@anvil.example for production deployment guidance.
"""
from anvil_chatkit import ChatKit, Persona

kit = ChatKit(title="Anvil Demo")

kit.register(Persona(
    slug="hello",
    name="Hello Bot",
    system_prompt="You are a friendly demo assistant. Greet the user warmly.",
))

kit.register(Persona(
    slug="time",
    name="Time Bot",
    system_prompt="You are a helpful assistant that answers time-zone questions.",
))

# Mount as ASGI app:
app = kit.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

The GitHub URL above (`anvil-industries/anvil-chatkit`) is the default that
`platform/scripts/apply_flags.py` writes when it stamps this file. If you
push the chatkit repo to a different org/user, set `[external] github_org`
in `platform/flags.toml` and re-run the script — it will update this file
accordingly.

After creating the Gist, **copy its URL** and either:

- Paste it into `platform/flags.toml` (`[external] gist_url`) and run
  `python platform/scripts/apply_flags.py` — this also wires it into the
  chatkit README, OR
- Hand-edit `external_artifacts/anvil_chatkit/README.md` to replace the
  `REPLACE_ME_WITH_YOUR_GIST_URL` placeholder, then commit and push.
