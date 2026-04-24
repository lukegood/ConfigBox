from __future__ import annotations

import getpass
import secrets

from .auth import generate_password_hash


def main() -> None:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    print(f"APP_PASSWORD_HASH={generate_password_hash(password)}")
    print(f"SESSION_SECRET={secrets.token_urlsafe(32)}")


if __name__ == "__main__":
    main()
