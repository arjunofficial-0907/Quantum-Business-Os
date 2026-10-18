from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.services.entitlement import (
    get_active_subscription,
    resolve_effective_entitlements,
)
from app.core.config import get_settings
from app.services.signed_license import create_signed_license
from app.schemas.license import LicensePayload
from app.schemas.signed_license import SignedLicense


class LicenseIssuanceError(Exception):
    """Raised when a license cannot be issued."""


def calculate_offline_valid_until(
    issued_at: datetime,
    subscription: Subscription,
    offline_validity_days: int,
) -> datetime:
    if offline_validity_days <= 0:
        raise LicenseIssuanceError(
            "offline_validity_days must be greater than zero"
        )

    if subscription.current_period_end <= issued_at:
        raise LicenseIssuanceError(
            "Subscription period has already ended"
        )

    entitlement_expiry = (
        issued_at + timedelta(days=offline_validity_days)
    )

    return min(
        entitlement_expiry,
        subscription.current_period_end,
    )


def issue_signed_license(
    db: Session,
    *,
    organization_id: UUID,
    device_id: UUID,
    activation_reference: str,
    device_type: str,
    license_id: UUID,
    issued_at: datetime | None = None,
) -> SignedLicense:
    subscription = get_active_subscription(
        db,
        organization_id,
    )

    if subscription is None:
        raise LicenseIssuanceError(
            "No active subscription found"
        )

    if issued_at is None:
        issued_at = datetime.now(timezone.utc)

    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)

    entitlements = resolve_effective_entitlements(
        db,
        organization_id,
    )

    offline_entitlement = entitlements.get(
        "offline_validity_days"
    )

    if offline_entitlement is None:
        raise LicenseIssuanceError(
            "offline_validity_days entitlement is not configured"
        )

    if not offline_entitlement.enabled:
        raise LicenseIssuanceError(
            "offline_validity_days entitlement is disabled"
        )

    try:
        offline_validity_days = int(
            offline_entitlement.value
        )
    except (TypeError, ValueError):
        raise LicenseIssuanceError(
            "offline_validity_days entitlement must be an integer"
        )

    offline_valid_until = calculate_offline_valid_until(
        issued_at=issued_at,
        subscription=subscription,
        offline_validity_days=offline_validity_days,
    )

    effective_values = {
        code: entitlement.value
        for code, entitlement in entitlements.items()
        if entitlement.enabled
    }

    settings = get_settings()
    
    payload = LicensePayload(
        key_id=settings.license_key_id,
        license_id=license_id,
        organization_id=organization_id,
        device_id=device_id,
        subscription_id=subscription.id,
        activation_reference=activation_reference,
        device_type=device_type,
        issued_at=issued_at,
        expires_at=subscription.current_period_end,
        offline_valid_until=offline_valid_until,
        entitlements=effective_values,
    )

    return create_signed_license(payload)