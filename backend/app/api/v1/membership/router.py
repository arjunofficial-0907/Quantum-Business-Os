from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization.dependencies import require_permission
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.membership import Membership

from app.schemas.rbac import (
    MembershipBranchScopeRequest,
    MembershipBranchScopeResponse,
    MembershipInviteRequest,
    MembershipResponse,
    MembershipRoleAssignRequest,
    MembershipRoleAssignResponse,
)
from app.services.branch import (
    get_accessible_branches,
    set_membership_branch_scope,
)
from app.services.rbac import (
    assign_role_to_membership,
    get_active_membership,
)

from app.services.membership import (
    accept_membership,
    create_invited_membership,
    get_membership_for_user,
    get_organization_memberships,
    get_user_by_email,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/memberships",
    tags=["Memberships"],
)


@router.get(
    "",
    response_model=list[MembershipResponse],
    status_code=status.HTTP_200_OK,
)
def list_memberships_endpoint(
    organization_id: UUID,
    current_user: User = Depends(
        require_permission("membership.manage")
    ),
    db: Session = Depends(get_db),
) -> list[MembershipResponse]:
    admin_membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if admin_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    memberships = get_organization_memberships(
        db=db,
        organization_id=organization_id,
    )

    return [
        MembershipResponse.model_validate(membership)
        for membership in memberships
    ]

@router.post(
    "/{membership_id}/role",
    response_model=MembershipRoleAssignResponse,
    status_code=status.HTTP_200_OK,
)
def assign_membership_role_endpoint(
    organization_id: UUID,
    membership_id: UUID,
    payload: MembershipRoleAssignRequest,
    current_user: User = Depends(
        require_permission("membership.manage")
    ),
    db: Session = Depends(get_db),
) -> MembershipRoleAssignResponse:
    admin_membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if admin_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    assigned_membership = assign_role_to_membership(
        db=db,
        organization_id=organization_id,
        membership_id=membership_id,
        role_id=payload.role_id,
    )

    if assigned_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership or role not found.",
        )

    return MembershipRoleAssignResponse.model_validate(
        assigned_membership
    )

@router.put(
    "/{membership_id}/branches",
    response_model=MembershipBranchScopeResponse,
    status_code=status.HTTP_200_OK,
)
def set_membership_branch_scope_endpoint(
    organization_id: UUID,
    membership_id: UUID,
    payload: MembershipBranchScopeRequest,
    current_user: User = Depends(
        require_permission("membership.manage")
    ),
    db: Session = Depends(get_db),
) -> MembershipBranchScopeResponse:
    admin_membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if admin_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    target_membership = db.get(
        Membership,
        membership_id,
    )

    if target_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    if target_membership.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    try:
        updated_membership = set_membership_branch_scope(
            db=db,
            membership=target_membership,
            organization_id=organization_id,
            all_branches=payload.all_branches,
            branch_ids=payload.branch_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    branches = get_accessible_branches(
        db=db,
        membership=updated_membership,
    )

    return MembershipBranchScopeResponse(
        membership_id=updated_membership.id,
        organization_id=updated_membership.organization_id,
        all_branches=updated_membership.all_branches,
        branch_ids=[branch.id for branch in branches],
    )

@router.post(
    "/{membership_id}/accept",
    response_model=MembershipResponse,
    status_code=status.HTTP_200_OK,
)
def accept_membership_endpoint(
    organization_id: UUID,
    membership_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    membership = db.get(
        Membership,
        membership_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    if membership.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    if membership.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot accept this membership.",
        )

    try:
        membership = accept_membership(
            db=db,
            membership=membership,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return MembershipResponse.model_validate(
        membership
    )


@router.post(
    "",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_membership_endpoint(
    organization_id: UUID,
    payload: MembershipInviteRequest,
    current_user: User = Depends(
        require_permission("membership.manage")
    ),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    admin_membership = get_active_membership(
        db=db,
        current_user=current_user,
        organization_id=organization_id,
    )

    if admin_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    user = get_user_by_email(
        db=db,
        email=payload.email,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    existing_membership = get_membership_for_user(
        db=db,
        organization_id=organization_id,
        user_id=user.id,
    )

    if existing_membership is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a membership in this organization.",
        )

    membership = create_invited_membership(
        db=db,
        user=user,
        organization_id=organization_id,
    )

    return MembershipResponse.model_validate(membership)