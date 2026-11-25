from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError
from app.models import User
from app.repositories.protocols import UserRepository
from app.security.auth import hash_password


class SignupService:
    def __init__(self, users: UserRepository, session: Session) -> None:
        self.users = users
        self.session = session

    def register(self, username: str, password: str) -> User:
        normalized_username = username.strip().lower()
        if self.users.by_username(normalized_username) is not None:
            raise ConflictError("That username is already registered")

        user = User(
            username=normalized_username,
            password_hash=hash_password(password),
            role="USER",
        )
        try:
            return self.users.add(user)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("That username is already registered") from exc