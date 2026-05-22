#!/usr/bin/env python3
"""Write /etc/anvil/secret.txt at container startup from flags.toml.

This is what makes flag #11 (the file:// LFI flag) configurable — the secret
file's contents are rendered from the central flag config instead of being
baked into the Dockerfile.
"""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

FLAGS_TOML = Path(os.environ.get("FLAGS_TOML", "/app/flags.toml"))
SECRET_DIR = Path("/etc/anvil")
SECRET_FILE = SECRET_DIR / "secret.txt"


def main() -> int:
    if not FLAGS_TOML.is_file():
        print(f"flags.toml not found at {FLAGS_TOML}", file=sys.stderr)
        return 1
    with FLAGS_TOML.open("rb") as f:
        data = tomllib.load(f)
    token = data["flags"]["web"]["file_token"]
    SECRET_DIR.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(f"Internal use only.\n{token}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
