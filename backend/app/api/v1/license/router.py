from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth.router import get_current_user
from app.core.authorization.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.signed_license import SignedLicense
from app.services.device_activation import (
    authorize_device_activation,
    issue_device_activation,
)
from app.services.license_issuance import (
    LicenseIssuanceError,
    issue_signed_license,
)
from app.services.license_validation import (
    LicenseValidationError,
    validate_signed_license,
)
from app.services.license_online_validation import (
    validate_signed_license_online,
)


router = APIRouter(
    prefix="/licenses",
    tags=["Licensing"],
)


class LicenseActivationRequest(BaseModel):
    organization_id: UUID
    device_id: UUID
    activation_reference: str = Field(
        min_length=1,
        max_length=255,
    )


class LicenseActivationResponse(BaseModel):
    license: SignedLicense

class LicenseValidationRequest(BaseModel):
    license: SignedLicense


class LicenseValidationResponse(BaseModel):
    valid: bool
    reason: str | None = None

class OnlineLicenseValidationRequest(BaseModel):
    license: SignedLicense


class OnlineLicenseValidationResponse(BaseModel):
    valid: bool
    reason: str | None = None


@router.post(
    "/activate",
    response_model=LicenseActivationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("license.activate")),
    ],
)
def activate_license(
    request: LicenseActivationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LicenseActivationResponse:
    authorization = authorize_device_activation(
        db,
        request.organization_id,
        request.device_id,
    )

    if not authorization.authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=authorization.reason or "Device activation is not authorized.",
        )

    try:
        activation = issue_device_activation(
            db,
            request.organization_id,
            request.device_id,
            request.activation_reference,
        )

        license = issue_signed_license(
            db,
            organization_id=request.organization_id,
            device_id=request.device_id,
            activation_reference=activation.activation_reference,
            device_type=authorization.device_type or "unknown",
            license_id=UUID(str(activation.id)),
        )

        db.commit()

        return LicenseActivationResponse(
            license=license,
        )

    except LicenseIssuanceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

@router.post(
    "/validate",
    response_model=LicenseValidationResponse,
    status_code=status.HTTP_200_OK,
)
def validate_license(
    request: LicenseValidationRequest,
) -> LicenseValidationResponse:
    try:
        result = validate_signed_license(
            request.license,
        )

        return LicenseValidationResponse(
            valid=result.valid,
            reason=result.reason,
        )

    except LicenseValidationError as exc:
        return LicenseValidationResponse(
            valid=False,
            reason=str(exc),
        )

@router.post(
    "/validate-online",
    response_model=OnlineLicenseValidationResponse,
    status_code=status.HTTP_200_OK,
)
def validate_license_online(
    request: OnlineLicenseValidationRequest,
    db: Session = Depends(get_db),
) -> OnlineLicenseValidationResponse:
    result = validate_signed_license_online(
        db,
        request.license,
    )

    return OnlineLicenseValidationResponse(
        valid=result.valid,
        reason=result.reason,
    )