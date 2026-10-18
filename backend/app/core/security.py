import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User, UserStatus

from app.models.auth_session import (
    AuthSession,
    AuthSessionStatus,
)

settings = get_settings()

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    password: str,
    password_hash_value: str,
) -> bool:
    return password_hash.verify(
        password,
        password_hash_value,
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(
        refresh_token.encode("utf-8")
    ).hexdigest()


def create_access_token(
    subject: UUID,
    session_id: UUID,
) -> str:
    now = datetime.now(timezone.utc)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "session_id": str(session_id),
        "type": "access",
        "iat": now,
        "exp": now
        + timedelta(minutes=settings.access_token_expire_minutes),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={
            "require": [
                "sub",
                "session_id",
                "type",
                "iat",
                "exp",
            ]
        },
    )


def get_current_auth_session(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AuthSession:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    try:
        payload = decode_access_token(token)

        if payload.get("type") != "access":
            raise credentials_exception

        session_id = payload.get("session_id")

        if session_id is None:
            raise credentials_exception

        session_uuid = UUID(str(session_id))

    except (
        jwt.PyJWTError,
        ValueError,
        TypeError,
    ):
        raise credentials_exception

    auth_session = db.get(
        AuthSession,
        session_uuid,
    )

    if auth_session is None:
        raise credentials_exception

    if auth_session.status != AuthSessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session is no longer active.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if auth_session.expires_at <= datetime.now(timezone.utc):
        auth_session.status = AuthSessionStatus.EXPIRED
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session has expired.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return auth_session

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    try:
        payload = decode_access_token(token)

        if payload.get("type") != "access":
            raise credentials_exception

        user_id = payload.get("sub")
        session_id = payload.get("session_id")

        if user_id is None or session_id is None:
            raise credentials_exception

        user_uuid = UUID(str(user_id))
        session_uuid = UUID(str(session_id))

    except (
        jwt.PyJWTError,
        ValueError,
        TypeError,
    ):
        raise credentials_exception

    user = db.get(User, user_uuid)

    if user is None:
        raise credentials_exception

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    auth_session = db.get(
        AuthSession,
        session_uuid,
    )

    if auth_session is None:
        raise credentials_exception

    if auth_session.user_id != user.id:
        raise credentials_exception

    if auth_session.status != AuthSessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session is no longer active.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if auth_session.expires_at <= datetime.now(timezone.utc):
        auth_session.status = AuthSessionStatus.EXPIRED
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session has expired.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return user