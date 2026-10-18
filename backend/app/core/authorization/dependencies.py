from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.rbac import has_permission


def require_permission(permission_code: str):
    def permission_dependency(
        organization_id: UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        allowed = has_permission(
            db=db,
            current_user=current_user,
            organization_id=organization_id,
            permission_code=permission_code,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return permission_dependency 