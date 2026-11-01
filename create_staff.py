import getpass
import re
import sys

from sqlalchemy import select

from database import SessionLocal
from models import User
from security import hash_password


def main():
    print("\n=== StockFlow Staff Account Setup ===")

    username = input("Staff username: ").strip().lower()

    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", username):
        raise ValueError("Invalid username.")

    password = getpass.getpass("Staff password (hidden): ")
    confirmation = getpass.getpass("Confirm password (hidden): ")

    if password != confirmation:
        raise ValueError("Passwords do not match.")

    if not 12 <= len(password) <= 128:
        raise ValueError("Password must contain 12-128 characters.")

    password_hash = hash_password(password)

    with SessionLocal.begin() as db:
        admin_exists = db.scalar(
            select(User.id)
            .where(
                User.role == "admin",
                User.is_active.is_(True),
            )
            .limit(1)
        )

        if admin_exists is None:
            raise RuntimeError("An active admin account must exist first.")

        existing = db.scalar(
            select(User.id).where(User.username == username)
        )

        if existing is not None:
            raise RuntimeError("Username already exists.")

        user = User(
            username=username,
            password_hash=password_hash,
            role="staff",
            is_active=True,
        )

        db.add(user)
        db.flush()

        print(f"\nStaff account created: {username}")
        print(f"User ID: {user.id}")
        print("Role: staff")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(f"\nSetup failed: {exc}")
        sys.exit(1)
