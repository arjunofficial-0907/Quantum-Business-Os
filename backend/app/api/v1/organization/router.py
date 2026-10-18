from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization.dependencies import require_permission
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
)
from app.services.organization import (
    create_organization,
    get_organization,
    get_user_organizations,
    update_organization,
)

router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"],
)


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_endpoint(
    payload: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    organization = create_organization(
        db=db,
        current_user=current_user,
        name=payload.name,
        legal_name=payload.legal_name,
    )

    return OrganizationResponse.model_validate(organization)


@router.get(
    "",
    response_model=list[OrganizationResponse],
    status_code=status.HTTP_200_OK,
)
def list_organizations_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrganizationResponse]:
    organizations = get_user_organizations(
        db=db,
        current_user=current_user,
    )

    return [
        OrganizationResponse.model_validate(organization)
        for organization in organizations
    ]

@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
)
def get_organization_endpoint(
    organization_id: UUID,
    current_user: User = Depends(
        require_permission("organization.read")
    ),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    organization = get_organization(
        db=db,
        organization_id=organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    return OrganizationResponse.model_validate(organization)

@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
)
def update_organization_endpoint(
    organization_id: UUID,
    payload: OrganizationUpdateRequest,
    current_user: User = Depends(
        require_permission("organization.manage")
    ),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    organization = get_organization(
        db=db,
        organization_id=organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    organization = update_organization(
        db=db,
        organization=organization,
        name=payload.name,
        legal_name=payload.legal_name,
    )

    return OrganizationResponse.model_validate(organization)