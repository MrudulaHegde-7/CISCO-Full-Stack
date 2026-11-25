import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.repositories.mysql import SQLAlchemyUserRepository

password_hasher = PasswordHasher()
basic_auth = HTTPBasic(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def get_optional_user(
    credentials: HTTPBasicCredentials | None = Depends(basic_auth),
    session: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    user = SQLAlchemyUserRepository(session).by_username(credentials.username)
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not secrets.compare_digest(user.role, "ADMIN"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user