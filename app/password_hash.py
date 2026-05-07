from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

from .auth import compose_env_escape, generate_password_hash


def update_env_text(text: str, updates: dict[str, str]) -> str:
    remaining = dict(updates)
    lines = text.splitlines()
    output: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)

    if remaining and output and output[-1] != "":
        output.append("")
    for key, value in remaining.items():
        output.append(f"{key}={value}")

    return "\n".join(output) + "\n"


def write_env_file(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(update_env_text(text, updates), encoding="utf-8")


def print_env_updates(updates: dict[str, str]) -> None:
    for key, value in updates.items():
        print(f"{key}={value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ConfigBox login password hash.")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to update with APP_PASSWORD_HASH and SESSION_SECRET. Default: .env",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Only print generated values instead of updating the env file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")

    updates = {
        "APP_PASSWORD": "",
        "APP_PASSWORD_HASH": compose_env_escape(generate_password_hash(password)),
        "SESSION_SECRET": secrets.token_urlsafe(32),
    }

    if args.print_only:
        print_env_updates(updates)
        return

    env_file = Path(args.env_file)
    try:
        write_env_file(env_file, updates)
    except OSError as exc:
        print(f"Failed to update {env_file}: {exc}", file=sys.stderr, flush=True)
        print("Please manually write these lines to your .env file:", file=sys.stderr, flush=True)
        print_env_updates(updates)
        raise SystemExit(1) from exc
    else:
        print(f"Updated {env_file}")


if __name__ == "__main__":
    main()
