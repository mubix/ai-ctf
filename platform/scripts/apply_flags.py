#!/usr/bin/env python3
"""Apply flag values from flags.toml to the static files that hold them.

Most flag values are read from `flags.toml` at runtime by the Python app, so
editing the TOML + restarting the web container is enough for them. But a few
flags live in static files that aren't loaded by Python:

  - data/init.sql               — CEO salary (flag #4)
  - decoy/html/private/...      — flag #10 token
  - decoy/html/internal-tools/  — flag #12 token
  - app/static/logo.jpg         — EXIF Image Description + Comment (flag #20)
  - external_artifacts/         — chatkit README, gist content, dns_records,
                                  setup-history.sh (flags #14–17)

Run this script from the platform/ directory after editing `flags.toml`:

    python scripts/apply_flags.py

It is idempotent — running it twice produces the same result. EXIF stamping
requires `exiftool` on PATH; the script warns and continues without it if
exiftool is missing.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
FLAGS_TOML = ROOT / "flags.toml"


def load_flags() -> dict:
    if not FLAGS_TOML.is_file():
        sys.exit(f"flags.toml not found at {FLAGS_TOML}")
    with FLAGS_TOML.open("rb") as f:
        return tomllib.load(f)


def replace_with_pattern(path: Path, pattern: str, replacement: str) -> bool:
    """Regex-substitute in `path`; return True if the file changed."""
    if not path.is_file():
        print(f"  skipped (missing): {path}")
        return False
    text = path.read_text()
    new = re.sub(pattern, replacement, text)
    if new == text:
        return False
    path.write_text(new)
    return True


# -----------------------------------------------------------------------------
# init.sql (flag #4 — CEO salary)
# -----------------------------------------------------------------------------
def apply_init_sql(flags: dict) -> None:
    print("[init.sql]")
    salary = int(flags["flags"]["hr"]["ceo_salary"])
    path = ROOT / "data" / "init.sql"
    # The CEO row: id=99, Patricia Holloway, ..., <salary>, ...
    pattern = r"(\(99,\s*'Patricia Holloway','CEO',\s*'Executive',\s*)\d+"
    changed = replace_with_pattern(path, pattern, rf"\g<1>{salary}")
    print(f"  {'updated' if changed else 'no change'}: {path}")


# -----------------------------------------------------------------------------
# decoy HTML (flags #10 and #12)
# -----------------------------------------------------------------------------
def apply_decoy_html(flags: dict) -> None:
    print("[decoy html]")
    private = flags["flags"]["web"]["private_token"]
    internal = flags["flags"]["web"]["internal_token"]
    for path, token in [
        (ROOT / "decoy" / "html" / "private" / "index.html", private),
        (ROOT / "decoy" / "html" / "internal-tools" / "index.html", internal),
    ]:
        # Replace any existing `<code>flag{...}</code>` block with the new token.
        changed = replace_with_pattern(
            path,
            r"<code>flag\{[^}]+\}</code>",
            f"<code>{token}</code>",
        )
        print(f"  {'updated' if changed else 'no change'}: {path}")


# -----------------------------------------------------------------------------
# EXIF on logo.jpg (flag #20)
# -----------------------------------------------------------------------------
def apply_logo_exif(flags: dict) -> None:
    print("[logo exif]")
    token = flags["flags"]["recon"]["exif_token"]
    path = ROOT / "app" / "static" / "logo.jpg"
    if not path.is_file():
        print(f"  skipped (missing): {path}")
        return
    if not shutil.which("exiftool"):
        print("  WARNING: exiftool not on PATH; logo EXIF unchanged.")
        print(
            "  Install exiftool (apt install libimage-exiftool-perl, "
            "brew install exiftool) and re-run, or stamp manually:"
        )
        print(
            f'    exiftool -overwrite_original -ImageDescription="{token}" '
            f'-Comment="{token}" {path}'
        )
        return
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            f"-ImageDescription={token}",
            f"-Comment={token}",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print(f"  stamped: {path}")


# -----------------------------------------------------------------------------
# External artifacts (flags #14, #15, #16, #17 + planted Gist URL / domain)
# -----------------------------------------------------------------------------
def apply_external_artifacts(flags: dict) -> None:
    print("[external_artifacts]")
    ext_dir = REPO_ROOT / "external_artifacts"
    if not ext_dir.is_dir():
        print(f"  skipped (missing): {ext_dir}")
        return

    domain = flags["external"]["dns_domain"]
    label  = flags["external"]["dns_label"]
    fqdn   = f"{label}.{domain}"
    org    = flags["external"]["github_org"]
    gist_url = flags["external"]["gist_url"]

    readme_token = flags["flags"]["external"]["readme_token"]
    commit_token = flags["flags"]["external"]["commit_token"]
    gist_token   = flags["flags"]["external"]["gist_token"]
    dns_token    = flags["flags"]["external"]["dns_token"]

    # chatkit README: replace audit_token, domain_audit_canary FQDN, demo Gist link
    chatkit_readme = ext_dir / "anvil_chatkit" / "README.md"
    if chatkit_readme.is_file():
        text = chatkit_readme.read_text()
        text = re.sub(r"audit_token:\s*flag\{[^}]+\}", f"audit_token: {readme_token}", text)
        text = re.sub(
            r"domain_audit_canary:\s*\S+",
            f"domain_audit_canary: {fqdn}",
            text,
        )
        text = re.sub(
            r"dig TXT \S+",
            f"dig TXT {fqdn}",
            text,
        )
        text = re.sub(
            r"\(https://gist\.github\.com/[^)]+\)",
            f"({gist_url})",
            text,
        )
        chatkit_readme.write_text(text)
        print(f"  updated: {chatkit_readme}")

    # setup-history.sh: commit message with flag #15
    history = ext_dir / "anvil_chatkit" / "setup-history.sh"
    if history.is_file():
        changed = replace_with_pattern(
            history,
            r'Audit canary: flag\{[^}]+\}',
            f'Audit canary: {commit_token}',
        )
        print(f"  {'updated' if changed else 'no change'}: {history}")

    # gist_content.md: flag #16 token and the chatkit org URL
    gist_md = ext_dir / "gist_content.md"
    if gist_md.is_file():
        text = gist_md.read_text()
        text = re.sub(r"audit_canary:\s*flag\{[^}]+\}", f"audit_canary: {gist_token}", text)
        text = re.sub(
            r"https://github\.com/[\w-]+/anvil-chatkit",
            f"https://github.com/{org}/anvil-chatkit",
            text,
        )
        gist_md.write_text(text)
        print(f"  updated: {gist_md}")

    # dns_records.txt: TXT label + value
    dns = ext_dir / "dns_records.txt"
    if dns.is_file():
        text = dns.read_text()
        text = re.sub(
            r"anvil-industries-audit-canary:flag\{[^}]+\}",
            f"anvil-industries-audit-canary:{dns_token}",
            text,
        )
        text = re.sub(
            r"_anvil-audit\.[A-Za-z0-9.-]+",
            fqdn,
            text,
        )
        text = re.sub(
            r"DNS records to set on \S+",
            f"DNS records to set on {domain}",
            text,
        )
        dns.write_text(text)
        print(f"  updated: {dns}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-external",
        action="store_true",
        help="don't touch external_artifacts/ (useful if you've customized them by hand)",
    )
    args = parser.parse_args()

    flags = load_flags()
    apply_init_sql(flags)
    apply_decoy_html(flags)
    apply_logo_exif(flags)
    if not args.skip_external:
        apply_external_artifacts(flags)
    print("\nDone. Restart the stack to pick up changes:")
    print("  docker compose restart web decoy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
