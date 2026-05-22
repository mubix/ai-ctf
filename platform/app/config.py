"""Central configuration loader.

Reads `flags.toml` once at import time and exposes the flag values + a couple
of platform-level strings to the rest of the app. Edit `flags.toml` (at the
platform/ directory root) to customize the event.

Looks for the file relative to the project root inside the container
(`/app/flags.toml`) first, then falls back to walking up from this file —
that fallback path is what lets `scripts/apply_flags.py` import this module
when run from the host machine outside Docker.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def _find_flags_toml() -> Path:
    explicit = os.environ.get("FLAGS_TOML")
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p

    candidates = [
        Path("/app/flags.toml"),                          # in-container
        Path(__file__).resolve().parent.parent / "flags.toml",  # platform/
        Path.cwd() / "flags.toml",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "flags.toml not found. Looked at: "
        + ", ".join(str(c) for c in candidates)
    )


_PATH = _find_flags_toml()
with _PATH.open("rb") as _f:
    _DATA: dict[str, Any] = tomllib.load(_f)


# -- Platform identity ------------------------------------------------------
POWERED_BY: str = _DATA["platform"]["powered_by"]

# -- External chain (used by docs + apply_flags + chatkit artifacts) -------
EXT_DNS_DOMAIN: str = _DATA["external"]["dns_domain"]
EXT_DNS_LABEL:  str = _DATA["external"]["dns_label"]
EXT_GITHUB_ORG: str = _DATA["external"]["github_org"]
EXT_GIST_URL:   str = _DATA["external"]["gist_url"]

# -- In-platform flag values ------------------------------------------------
FLAG_CS_AUDIT_TOKEN: str = _DATA["flags"]["cs"]["audit_token"]
FLAG_CS_COUPON:      str = _DATA["flags"]["cs"]["coupon"]

FLAG_HR_CEO_SALARY:   int = int(_DATA["flags"]["hr"]["ceo_salary"])
FLAG_HR_SCHEMA_TOKEN: str = _DATA["flags"]["hr"]["schema_token"]

FLAG_CR_DEPLOY_KEY:     str = _DATA["flags"]["code_review"]["deploy_key"]
FLAG_CR_ROLLBACK_TOKEN: str = _DATA["flags"]["code_review"]["rollback_token"]

FLAG_CHECKOUT_FREE_ID: str = _DATA["flags"]["checkout"]["free_order_id"]
FLAG_CHECKOUT_NEG_ID:  str = _DATA["flags"]["checkout"]["neg_order_id"]

FLAG_WEB_PRIVATE_TOKEN:  str = _DATA["flags"]["web"]["private_token"]
FLAG_WEB_FILE_TOKEN:     str = _DATA["flags"]["web"]["file_token"]
FLAG_WEB_INTERNAL_TOKEN: str = _DATA["flags"]["web"]["internal_token"]

FLAG_HIDDEN_ADMIN_TOKEN: str = _DATA["flags"]["hidden"]["admin_token"]

# -- External flag values (planted in artifacts the user pushes themselves) -
FLAG_EXT_README_TOKEN: str = _DATA["flags"]["external"]["readme_token"]
FLAG_EXT_COMMIT_TOKEN: str = _DATA["flags"]["external"]["commit_token"]
FLAG_EXT_GIST_TOKEN:   str = _DATA["flags"]["external"]["gist_token"]
FLAG_EXT_DNS_TOKEN:    str = _DATA["flags"]["external"]["dns_token"]

# -- In-platform recon flag values -----------------------------------------
FLAG_RECON_AUDIT_HEADER: str = _DATA["flags"]["recon"]["audit_header"]
FLAG_RECON_ROBOTS_TOKEN: str = _DATA["flags"]["recon"]["robots_token"]
FLAG_RECON_EXIF_TOKEN:   str = _DATA["flags"]["recon"]["exif_token"]
