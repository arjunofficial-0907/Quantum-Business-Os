from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device_activation import (
    DeviceActivation,
    DeviceActivationStatus,
)
from app.models.licensed_device import (
    LicensedDevice,
    LicensedDeviceStatus,
)
from app.models.organization import (
    Organization,
    OrganizationStatus,
)
from app.models.subscription import (
    Subscription,
    SubscriptionStatus,
)
from app.schemas.signed_license import SignedLicense
from app.services.license_validation import validate_signed_license


@dataclass(frozen=True)
class OnlineLicenseValidationResult:
    valid: bool
    reason: str


def validate_signed_license_online(
    db: Session,
    license: SignedLicense,
    *,
    now: datetime | None = None,
) -> OnlineLicenseValidationResult:
    if now is None:
        now = datetime.now(timezone.utc)

    artifact_result = validate_signed_license(
        license,
        now=now,
        offline=False,
    )

    if not artifact_result.valid:
        return OnlineLicenseValidationResult(
            valid=False,
            reason=artifact_result.reason,
        )

    payload = license.payload

    organization = db.scalar(
        select(Organization).where(
            Organization.id == payload.organization_id
        )
    )

    if organization is None:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="organization_not_found",
        )

    if organization.status != OrganizationStatus.ACTIVE:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="organization_not_active",
        )

    subscription = db.scalar(
        select(Subscription).where(
            Subscription.id == payload.subscription_id,
            Subscription.organization_id
            == payload.organization_id,
        )
    )

    if subscription is None:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="subscription_not_found",
        )

    if subscription.status not in {
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.ACTIVE,
    }:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="subscription_not_active",
        )

    if subscription.current_period_end <= now:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="subscription_expired",
        )

    device = db.scalar(
        select(LicensedDevice).where(
            LicensedDevice.id == payload.device_id,
            LicensedDevice.organization_id
            == payload.organization_id,
        )
    )

    if device is None:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="device_not_found",
        )

    if device.status != LicensedDeviceStatus.ACTIVE:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="device_not_active",
        )

    activation = db.scalar(
        select(DeviceActivation).where(
            DeviceActivation.device_id == payload.device_id,
            DeviceActivation.subscription_id
            == payload.subscription_id,
            DeviceActivation.activation_reference
            == payload.activation_reference,
        )
    )

    if activation is None:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="activation_not_found",
        )

    if activation.status != DeviceActivationStatus.ACTIVE:
        return OnlineLicenseValidationResult(
            valid=False,
            reason="activation_not_active",
        )

    if (
        activation.expires_at is not None
        and activation.expires_at <= now
    ):
        return OnlineLicenseValidationResult(
            valid=False,
            reason="activation_expired",
        )

    return OnlineLicenseValidationResult(
        valid=True,
        reason="valid",
    )