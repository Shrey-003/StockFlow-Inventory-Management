import getpass
import re
import sys

from sqlalchemy import select

from database import SessionLocal
from models import User
from security import hash_password


def main() -> None:
    print("\n=== StockFlow Initial Admin Setup ===")

    username = input("Admin username: ").strip().lower()

    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", username):
        raise ValueError(
            "Username must contain 3-64 valid characters."
        )

    password = getpass.getpass("Admin password (hidden): ")
    confirmation = getpass.getpass("Confirm password (hidden): ")

    if password != confirmation:
        raise ValueError("Passwords do not match.")

    if not 12 <= len(password) <= 128:
        raise ValueError(
            "Password must contain between 12 and 128 characters."
        )

    password_hash = hash_password(password)

    with SessionLocal.begin() as db:
        existing_admin = db.scalar(
            select(User.id)
            .where(User.role == "admin")
            .limit(1)
        )

        if existing_admin is not None:
            raise RuntimeError(
                "An admin account already exists. "
                "Initial admin creation is disabled."
            )

        existing_username = db.scalar(
            select(User.id).where(User.username == username)
        )

        if existing_username is not None:
            raise RuntimeError("This username is already registered.")

        admin = User(
            username=username,
            password_hash=password_hash,
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.flush()

        print(f"\nAdmin account created successfully: {username}")
        print(f"Admin user ID: {admin.id}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(f"\nSetup failed: {exc}")
        sys.exit(1)
