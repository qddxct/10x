"""Create an admin user interactively or via args.

Usage:
    python -m app.cli.create_admin --phone 13800000000 --name root --password Abcd1234

If flags are omitted, the script will prompt.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import re
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")


def _validate_password(password: str) -> None:
    if len(password) < 8 or len(password) > 64:
        raise ValueError("password must be 8-64 characters")
    if not any(c.isalpha() for c in password):
        raise ValueError("password must contain letters")
    if not any(c.isdigit() for c in password):
        raise ValueError("password must contain digits")


def _validate_phone(phone: str) -> None:
    if not PHONE_REGEX.match(phone):
        raise ValueError(f"invalid phone: {phone}")


def create_admin(db: Session, *, phone: str, name: str, password: str) -> User:
    _validate_phone(phone)
    _validate_password(password)
    if not name or not name.strip():
        raise ValueError("name is required")

    exists = db.query(User).filter(User.phone == phone).one_or_none()
    if exists is not None:
        raise ValueError(f"user with phone {phone} already exists")

    user = User(
        phone=phone,
        name=name.strip(),
        role="admin",
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("created admin id=%s phone=%s", user.id, user.phone)
    return user


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--phone", help="admin phone")
    parser.add_argument("--name", help="admin display name")
    parser.add_argument("--password", help="admin password")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = _parse_args(argv)

    phone = args.phone or input("phone: ").strip()
    name = args.name or input("name: ").strip()
    password = args.password or getpass.getpass("password: ")

    try:
        with SessionLocal() as db:
            user = create_admin(db, phone=phone, name=name, password=password)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    print(f"created admin id={user.id} phone={user.phone}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
