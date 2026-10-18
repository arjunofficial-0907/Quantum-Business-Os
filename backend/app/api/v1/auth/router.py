from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.models.auth_session import (
    AuthSession,
    AuthSessionStatus,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_current_auth_session,
    get_current_user,
    hash_password,
    hash_refresh_token,
)
from app.db.session import get_db
from app.models.user import User, UserStatus
from app.schemas.auth import (
    AuthResponse,
    AuthSessionResponse,
    AuthTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth import (
    AuthService,
    AuthenticationError,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

settings = get_settings()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthResponse:
    email = payload.email.lower().strip()

    existing_user = db.query(User).filter(
        User.email == email
    ).first()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create account with these credentials.",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        status=UserStatus.ACTIVE,
    )

    db.add(user)

    try:
        db.flush()

        auth_service = AuthService(db)

        refresh_token, _session = auth_service.create_session(
            user,
            device_type="unknown",
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            user_agent=request.headers.get("user-agent"),
            remember_me=False,
        )

        access_token = auth_service.issue_access_token(
            user,
            _session,
        )

        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create account with these credentials.",
        )

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        ),
    )

@router.post(
    "/token",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
)
def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    auth_service = AuthService(db)

    try:
        user = auth_service.authenticate_user(
            email=form_data.username,
            password=form_data.password,
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    refresh_token, session = auth_service.create_session(
        user,
        remember_me=False,
    )

    access_token = auth_service.issue_access_token(
        user,
        session,
    )

    db.commit()

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )

@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    auth_service = AuthService(db)

    try:
        user = auth_service.authenticate_user(
            email=payload.email,
            password=payload.password,
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    refresh_token, _session = auth_service.create_session(
        user,
        remember_me=False,
    )

    access_token = auth_service.issue_access_token(
        user,
        _session,
    )

    db.commit()

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        ),
    )

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)

@router.get(
    "/sessions",
    response_model=list[AuthSessionResponse],
    status_code=status.HTTP_200_OK,
)
def get_active_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuthSessionResponse]:
    statement = (
        select(AuthSession)
        .where(
            AuthSession.user_id == current_user.id,
            AuthSession.status == AuthSessionStatus.ACTIVE,
        )
        .order_by(AuthSession.created_at.desc())
    )

    sessions = list(db.scalars(statement))

    return [
        AuthSessionResponse.model_validate(session)
        for session in sessions
    ]

@router.post(
    "/refresh",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
)
def refresh_access_token(
    payload: dict,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    refresh_token = payload.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required.",
        )

    refresh_token_hash = hash_refresh_token(refresh_token)

    statement = select(AuthSession).where(
        AuthSession.refresh_token_hash == refresh_token_hash,
        AuthSession.status == AuthSessionStatus.ACTIVE,
    )

    session = db.scalar(statement)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    if session.expires_at <= datetime.now(timezone.utc):
        session.status = AuthSessionStatus.EXPIRED
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
        )

    user = db.get(User, session.user_id)

    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active.",
        )

    # Rotate refresh token
    new_refresh_token = generate_refresh_token()
    new_refresh_token_hash = hash_refresh_token(
        new_refresh_token
    )

    session.refresh_token_hash = new_refresh_token_hash

    access_token = create_access_token(
        user.id,
        session.id,
        )

    db.commit()

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    current_session: AuthSession = Depends(
        get_current_auth_session
    ),
    db: Session = Depends(get_db),
) -> None:
    auth_service = AuthService(db)

    auth_service.revoke_session(
        current_session,
        reason="logout",
    )

    db.commit()

@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    statement = (
        select(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == current_user.id,
            AuthSession.status == AuthSessionStatus.ACTIVE,
        )
    )

    session = db.scalar(statement)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session.status = AuthSessionStatus.REVOKED
    session.revoked_at = datetime.now(timezone.utc)
    session.revoke_reason = "user_revoked"

    db.commit()