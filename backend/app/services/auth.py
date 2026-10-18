from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models.auth_session import (
    AuthSession,
    AuthSessionStatus,
)
from app.models.user import User


settings = get_settings()


class AuthenticationError(Exception):
    """Raised when authentication credentials are invalid."""


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> User:
        statement = select(User).where(
            User.email == email.lower().strip()
        )

        user = self.db.scalar(statement)

        if user is None:
            raise AuthenticationError("Invalid credentials.")

        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid credentials.")

        return user

    def create_session(
        self,
        user: User,
        *,
        device_name: str | None = None,
        device_type: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        remember_me: bool = False,
    ) -> tuple[str, AuthSession]:
        refresh_token = generate_refresh_token()
        refresh_token_hash = hash_refresh_token(refresh_token)

        now = datetime.now(timezone.utc)

        lifetime_days = (
            settings.refresh_token_expire_days
            if remember_me
            else min(settings.refresh_token_expire_days, 7)
        )

        expires_at = now + timedelta(days=lifetime_days)

        token_family_id = uuid4()

        session = AuthSession(
            user_id=user.id,
            token_family_id=token_family_id,
            refresh_token_hash=refresh_token_hash,
            status=AuthSessionStatus.ACTIVE,
            expires_at=expires_at,
            device_name=device_name,
            device_type=device_type,
            ip_address=ip_address,
            user_agent=user_agent,
            remember_me=remember_me,
        )

        self.db.add(session)
        self.db.flush()

        return refresh_token, session

    def get_session(
        self,
        session_id: UUID,
    ) -> AuthSession | None:
        statement = select(AuthSession).where(
            AuthSession.id == session_id,
        )

        return self.db.scalar(statement)

    def issue_access_token(
        self,
        user: User,
        session: AuthSession
    ) -> str:
        return create_access_token(
            user.id,
            session.id,
        )

    def rotate_refresh_token(
        self,
        refresh_token: str,
    ) -> tuple[User, str, AuthSession]:
        token_hash = hash_refresh_token(refresh_token)

        statement = select(AuthSession).where(
            AuthSession.refresh_token_hash == token_hash
        )

        session = self.db.scalar(statement)

        if session is None:
            raise AuthenticationError("Invalid refresh token.")

        now = datetime.now(timezone.utc)

        if session.status != AuthSessionStatus.ACTIVE:
            if session.status == AuthSessionStatus.REVOKED:
                self._revoke_token_family(
                    session.token_family_id,
                    "refresh_token_reuse_detected",
                )

            raise AuthenticationError("Invalid refresh token.")

        if session.expires_at <= now:
            session.status = AuthSessionStatus.EXPIRED
            self.db.flush()

            raise AuthenticationError("Refresh token expired.")

        user = self.db.get(User, session.user_id)

        if user is None:
            raise AuthenticationError("Invalid refresh token.")

        token_family_id = session.token_family_id

        session.status = AuthSessionStatus.REVOKED
        session.revoked_at = now
        session.revoke_reason = "rotated"
        session.last_used_at = now

        new_refresh_token = generate_refresh_token()

        new_session = AuthSession(
            user_id=user.id,
            token_family_id=token_family_id,
            refresh_token_hash=hash_refresh_token(
                new_refresh_token
            ),
            status=AuthSessionStatus.ACTIVE,
            expires_at=session.expires_at,
            device_name=session.device_name,
            device_type=session.device_type,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            remember_me=session.remember_me,
            last_used_at=now,
        )

        self.db.add(new_session)
        self.db.flush()

        return user, new_refresh_token, new_session

    def _revoke_token_family(
        self,
        token_family_id: UUID,
        reason: str,
    ) -> None:
        statement = select(AuthSession).where(
            AuthSession.token_family_id == token_family_id,
            AuthSession.status == AuthSessionStatus.ACTIVE,
        )

        sessions = list(self.db.scalars(statement))

        now = datetime.now(timezone.utc)

        for session in sessions:
            session.status = AuthSessionStatus.REVOKED
            session.revoked_at = now
            session.revoke_reason = reason

    def revoke_session(
        self,
        session: AuthSession,
        reason: str = "logout",
    ) -> None:
        now = datetime.now(timezone.utc)

        session.status = AuthSessionStatus.REVOKED
        session.revoked_at = now
        session.revoke_reason = reason

    def revoke_all_user_sessions(
        self,
        user_id: UUID,
        reason: str = "security_action",
    ) -> int:
        statement = select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.status == AuthSessionStatus.ACTIVE,
        )

        sessions = list(self.db.scalars(statement))

        now = datetime.now(timezone.utc)

        for session in sessions:
            session.status = AuthSessionStatus.REVOKED
            session.revoked_at = now
            session.revoke_reason = reason

        return len(sessions)