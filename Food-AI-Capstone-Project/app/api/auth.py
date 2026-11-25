from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.repositories.mysql import SQLAlchemyUserRepository
from app.schemas import SignupRequest, UserResponse
from app.security.auth import get_current_user
from app.services.auth import SignupService

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(data: SignupRequest, session: Session = Depends(get_db)) -> UserResponse:
    user = SignupService(SQLAlchemyUserRepository(session), session).register(
        data.username, data.password
    )
    return UserResponse(username=user.username, role=user.role)


@router.get("/me", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(username=user.username, role=user.role)