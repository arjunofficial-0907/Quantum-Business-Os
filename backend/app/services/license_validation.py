from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.signed_license import SignedLicense
from app.services.signed_license import verify_signed_license


class LicenseValidationError(Exception):
    """Raised when a signed license is invalid."""


@dataclass(frozen=True)
class LicenseValidationResult:
    valid: bool
    reason: str


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def validate_signed_license(
    license: SignedLicense,
    *,
    now: datetime | None = None,
    offline: bool = False,
) -> LicenseValidationResult:
    if now is None:
        now = datetime.now(timezone.utc)

    now = _ensure_aware(now)

    payload = license.payload

    if not verify_signed_license(license):
        return LicenseValidationResult(
            valid=False,
            reason="invalid_signature",
        )

    issued_at = _ensure_aware(payload.issued_at)
    expires_at = _ensure_aware(payload.expires_at)
    offline_valid_until = _ensure_aware(
        payload.offline_valid_until
    )

    if issued_at > now:
        return LicenseValidationResult(
            valid=False,
            reason="license_not_yet_valid",
        )

    if expires_at <= now:
        return LicenseValidationResult(
            valid=False,
            reason="license_expired",
        )

    if offline:
        if offline_valid_until <= now:
            return LicenseValidationResult(
                valid=False,
                reason="offline_validity_expired",
            )

    return LicenseValidationResult(
        valid=True,
        reason="valid",
    )