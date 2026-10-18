import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.license import LicensePayload
from app.services.license_validation import validate_signed_license
from app.services.signed_license import create_signed_license


def make_license(
    *,
    issued_at: datetime,
    expires_at: datetime,
    offline_valid_until: datetime,
):
    payload = LicensePayload(
        key_id="quantum-license-v1",
        license_id=uuid4(),
        organization_id=uuid4(),
        device_id=uuid4(),
        subscription_id=uuid4(),
        activation_reference="validation-test",
        device_type="windows",
        issued_at=issued_at,
        expires_at=expires_at,
        offline_valid_until=offline_valid_until,
        entitlements={
            "max_devices": 10,
            "offline_validity_days": 7,
            "windows_client": True,
            "android_client": True,
        },
    )

    return create_signed_license(payload)


def main() -> None:
    now = datetime(
        2026,
        9,
        1,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )

    valid_license = make_license(
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=30),
        offline_valid_until=now + timedelta(days=7),
    )

    result = validate_signed_license(
        valid_license,
        now=now,
    )

    print("VALID_LICENSE=", result.valid)
    print("VALID_REASON=", result.reason)

    offline_result = validate_signed_license(
        valid_license,
        now=now,
        offline=True,
    )

    print("VALID_OFFLINE=", offline_result.valid)
    print("VALID_OFFLINE_REASON=", offline_result.reason)

    expired_license = make_license(
        issued_at=now - timedelta(days=30),
        expires_at=now - timedelta(seconds=1),
        offline_valid_until=now - timedelta(seconds=1),
    )

    expired_result = validate_signed_license(
        expired_license,
        now=now,
    )

    print("EXPIRED_LICENSE=", expired_result.valid)
    print("EXPIRED_REASON=", expired_result.reason)

    offline_expired_license = make_license(
        issued_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=30),
        offline_valid_until=now - timedelta(seconds=1),
    )

    offline_expired_result = validate_signed_license(
        offline_expired_license,
        now=now,
        offline=True,
    )

    print(
        "OFFLINE_EXPIRED_LICENSE=",
        offline_expired_result.valid,
    )
    print(
        "OFFLINE_EXPIRED_REASON=",
        offline_expired_result.reason,
    )

    future_license = make_license(
        issued_at=now + timedelta(hours=1),
        expires_at=now + timedelta(days=30),
        offline_valid_until=now + timedelta(days=7),
    )

    future_result = validate_signed_license(
        future_license,
        now=now,
    )

    print("FUTURE_LICENSE=", future_result.valid)
    print("FUTURE_REASON=", future_result.reason)

    tampered_license = make_license(
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=30),
        offline_valid_until=now + timedelta(days=7),
    )

    tampered_license.payload.entitlements["max_devices"] = 999

    tampered_result = validate_signed_license(
        tampered_license,
        now=now,
    )

    print("TAMPERED_LICENSE=", tampered_result.valid)
    print("TAMPERED_REASON=", tampered_result.reason)


if __name__ == "__main__":
    main()