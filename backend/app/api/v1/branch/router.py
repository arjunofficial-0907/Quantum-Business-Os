from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.branch import (
    BranchCreateRequest,
    BranchResponse,
)
from app.services.branch import (
    create_branch,
    get_accessible_branches,
    get_active_membership,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/branches",
    tags=["Branches"],
)


@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch_endpoint(
    organization_id: UUID,
    payload: BranchCreateRequest,
    current_user: User = Depends(
        require_permission("branch.manage")
    ),
    db: Session = Depends(get_db),
) -> BranchResponse:
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
        branch = create_branch(
            db=db,
            membership=membership,
            organization_id=organization_id,
            name=payload.name,
            code=payload.code,
            address_line_1=payload.address_line_1,
            address_line_2=payload.address_line_2,
            city=payload.city,
            state=payload.state,
            postal_code=payload.postal_code,
            country=payload.country,
            timezone=payload.timezone,
        )
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A branch with this code already exists in the organization.",
        )

    return BranchResponse.model_validate(branch)


@router.get(
    "",
    response_model=list[BranchResponse],
    status_code=status.HTTP_200_OK,
)
def list_branches_endpoint(
    organization_id: UUID,
    current_user: User = Depends(
        require_permission("branch.read")
    ),
    db: Session = Depends(get_db),
) -> list[BranchResponse]:
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

    branches = get_accessible_branches(
        db=db,
        membership=membership,
    )

    return [
        BranchResponse.model_validate(branch)
        for branch in branches
    ]
