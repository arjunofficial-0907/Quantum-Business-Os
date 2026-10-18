from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.rbac import (
    PermissionAssignRequest,
    PermissionResponse,
    RoleCreateRequest,
    RoleResponse,
)
from app.services.rbac import (
    assign_permissions_to_role,
    create_role,
    get_active_membership,
    get_organization_roles,
    get_permissions,
    get_role,
    get_role_permissions,
)
from app.core.authorization.dependencies import require_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/roles",
    tags=["RBAC"],
)


@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_role_endpoint(
    organization_id: UUID,
    payload: RoleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoleResponse:
    membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    try:
        role = create_role(
            db=db,
            organization_id=organization_id,
            name=payload.name,
            description=payload.description,
        )
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A role with this name already exists in the organization.",
        )

    return RoleResponse.model_validate(role)


@router.get(
    "",
    response_model=list[RoleResponse],
    status_code=status.HTTP_200_OK,
)
def list_roles_endpoint(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RoleResponse]:
    membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    roles = get_organization_roles(
        db=db,
        organization_id=organization_id,
    )

    return [
        RoleResponse.model_validate(role)
        for role in roles
    ]


@router.get(
    "/permissions/catalog",
    response_model=list[PermissionResponse],
    status_code=status.HTTP_200_OK,
)
def list_permission_catalog_endpoint(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PermissionResponse]:
    membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    permissions = get_permissions(db=db)

    return [
        PermissionResponse.model_validate(permission)
        for permission in permissions
    ]


@router.get(
    "/{role_id}/permissions",
    response_model=list[PermissionResponse],
    status_code=status.HTTP_200_OK,
)
def list_role_permissions_endpoint(
    organization_id: UUID,
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PermissionResponse]:
    membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    role = get_role(
        db=db,
        organization_id=organization_id,
        role_id=role_id,
    )

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found.",
        )

    permissions = get_role_permissions(
        db=db,
        role_id=role.id,
    )

    return [
        PermissionResponse.model_validate(permission)
        for permission in permissions
    ]


@router.post(
    "/{role_id}/permissions",
    response_model=list[PermissionResponse],
    status_code=status.HTTP_200_OK,
)
def assign_role_permissions_endpoint(
    organization_id: UUID,
    role_id: UUID,
    payload: PermissionAssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PermissionResponse]:
    membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    role = get_role(
        db=db,
        organization_id=organization_id,
        role_id=role_id,
    )

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found.",
        )

    permissions = get_permissions(db=db)

    permission_ids = set(payload.permission_ids)
    known_permission_ids = {
        permission.id
        for permission in permissions
    }

    unknown_permission_ids = permission_ids - known_permission_ids

    if unknown_permission_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more permission IDs are invalid.",
        )

    return [
        PermissionResponse.model_validate(permission)
        for permission in assign_permissions_to_role(
            db=db,
            role=role,
            permission_ids=list(permission_ids),
        )
    ]