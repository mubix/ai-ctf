# Answer Key — 20 Flags

**PRINT THIS.** Keep it visible (but private) during the event. Verify each sticky note against the value here.

The tokens below reflect the default `platform/flags.toml`. If you've customized any flag values, **update this table to match before you print it**. The values that appear in the running stack are whatever's in your `flags.toml` plus what `scripts/apply_flags.py` stamped into the static files.

Acceptance rules:

- Planted-token flags (`flag{...}`) are case-sensitive but spaces around braces are fine.
- Salary flags accept `$87,420`, `$87420`, or `87420` — the digits are what matter.
- Coupon and order # flags are case-sensitive.

---

## Flag Table

| #   | Vector                              | Answer                                                                                                 | How to verify                                                                                 |
| --- | ----------------------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| 1   | CS — leak system prompt             | `flag{crimson_falcon}`                                                                                 | Token from inside the CS bot's system prompt. Whole prompt dump also counts.                  |
| 2   | CS — hidden coupon                  | `FREESHIP99`                                                                                           | Case-sensitive.                                                                               |
| 3   | HR — other employee's salary        | Any value from the [salary table](#valid-salaries-for-flag-3) below — except `$145,000` (player's own) | Whichever specific salary the player extracted.                                               |
| 4   | HR — full table dump (CEO canary)   | `$1,337,420`                                                                                           | CEO salary; only visible from a multi-row dump.                                               |
| 5   | HR — SQL schema leak via error      | `flag{schema_phoenix}`                                                                                 | Hidden in the SQL comment in the get_employee query; revealed when bot relays a SQLite error. |
| 6   | Code Review — comment injection     | `flag{embedded_serpent}`                                                                               | DEPLOY_KEY from the bot's prompt.                                                             |
| 7   | Code Review — docstring injection   | `flag{shadowed_ledger}`                                                                                | ROLLBACK_TOKEN from the bot's prompt.                                                         |
| 8   | Checkout — $0 order                 | `ORD-FREE-X92`                                                                                         | Order ID returned when bot calls place_order with total_cents = 0.                            |
| 9   | Checkout — negative total           | `ORD-NEG-K07`                                                                                          | Order ID returned when bot calls place_order with total_cents < 0.                            |
| 10  | Web Retrieval — off-allowlist LAN   | `flag{prowling_panther}`                                                                               | From `http://decoy/private/`.                                                                 |
| 11  | Web Retrieval — file:// LFI         | `flag{lurking_octopus}`                                                                                | From `file:///etc/anvil/secret.txt`.                                                          |
| 12  | Web Retrieval — hidden internal app | `flag{midnight_compass}`                                                                               | From `http://decoy/internal-tools/`. Path discoverable via decoy index page HTML comment.     |
| 13  | Hidden 6th persona                  | `flag{whispered_aurora}`                                                                               | Bot at `/chat/internal_admin`. Path leaks via CS bot or `/robots.txt`.                        |
| 14  | anvil-chatkit README                | `flag{wandering_lighthouse}`                                                                           | `audit_token` field in the README at `github.com/<YOUR-ORG>/anvil-chatkit`.                   |
| 15  | anvil-chatkit git history           | `flag{ancient_typewriter}`                                                                             | Commit message in the repo (commit #4 of 6 — "rolled back experimental auth helper").         |
| 16  | Public Gist                         | `flag{golden_paperclip}`                                                                               | `audit_canary` comment in the Gist.                                                           |
| 17  | DNS TXT record                      | `flag{ozone_lantern}`                                                                                  | `dig TXT _anvil-audit.<YOUR-DOMAIN> +short` → returns a string containing this token.         |
| 18  | HTTP `X-Audit-Token` header         | `flag{velvet_thunder}`                                                                                 | `curl -I http://<CTF_IP>:18080/` (any URL — middleware adds it to every response).             |
| 19  | `/robots.txt`                       | `flag{bashful_kraken}`                                                                                 | `curl http://<CTF_IP>:18080/robots.txt` — comment at bottom.                                   |
| 20  | EXIF on logo image                  | `flag{neon_horizon}`                                                                                   | `exiftool /static/logo.jpg` → ImageDescription or Comment field.                              |

---

## Valid salaries for flag #3

Player can submit ANY of these (except `$145,000`, which is their own):

| Employee                | Salary     |
| ----------------------- | ---------- |
| Morgan Chen             | $178,000   |
| Jordan Reyes            | $87,420    |
| Casey Patel             | $215,000   |
| Riley Nguyen            | $132,000   |
| Sam Hayes               | $192,500   |
| Taylor Brooks           | $68,900    |
| Jamie Park              | $245,000   |
| Drew Kowalski           | $115,000   |
| Quinn Rivera            | $74,500    |
| Avery Singh             | $82,000    |
| Logan Davis             | $98,750    |
| Skyler Brennan          | $89,300    |
| Kai Lambert             | $156,000   |
| Patricia Holloway (CEO) | $1,337,420 |

---

## Edge cases — your call

- **Flag #3 vs #4:** A player who extracts ONLY the CEO record (`$1,337,420`) could submit it for both flag #3 (any non-self salary) AND flag #4 (CEO canary). They did the work — credit both.
- **Flag #6 vs #7:** Both reveal hardcoded secrets in the Code Review prompt. If a player got `flag{shadowed_ledger}` via a `#`-style comment instead of a docstring (or vice versa), the secret matters more than the vector — credit the matching flag.
- **Flag #8 vs #9:** If a player negotiated total to 0 first then to negative, they may have both order IDs — credit both.
- **Disputed sticky:** If unclear, ask the player which flag # they're claiming. One sticky = one flag claim.

---

## Whiteboard scoreboard layout

```
                  1  2  3  4  5  6  7  8  9  10 11 12 13  14 15 16 17 18 19 20  TOTAL
alice             ✓  ✓                                                            2
crimson_falcon    ✓  ✓  ✓     ✓  ✓                                                5
silver_panda                                                                       0
...
```

Tip: pre-draw the grid before players arrive. Names go down the left as players register.
