from getpass import getpass

from sqlalchemy import select

from app.config import settings
from app.db import build_engine, build_session_factory
from app.models import User
from app.security.auth import hash_password


def main() -> int:
    password = getpass("New admin password (at least 12 characters): ")
    confirmation = getpass("Confirm new admin password: ")
    if len(password) < 12:
        print("Password must be at least 12 characters.")
        return 1
    if password != confirmation:
        print("Passwords do not match.")
        return 1

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    try:
        with session_factory() as session:
            user = session.scalar(
                select(User).where(
                    User.username == settings.demo_admin_username,
                    User.role == "ADMIN",
                )
            )
            if user is None:
                print("Configured admin account was not found in the database.")
                return 1
            user.password_hash = hash_password(password)
            session.commit()
        print("Admin password updated. Sign in with the new password.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())