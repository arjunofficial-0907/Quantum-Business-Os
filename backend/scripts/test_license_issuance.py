import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.device_activation import DeviceActivation
from app.models.device_activation import DeviceActivationStatus
from app.models.licensed_device import LicensedDevice
from app.models.licensed_device import LicensedDeviceStatus
from app.models.licensed_device import LicensedDeviceType
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import SubscriptionPlan
from app.services.license_issuance import issue_signed_license
from app.services.signed_license import verify_signed_license


def main() -> None:
    db = SessionLocal()

    organization = None
    subscription = None
    device = None
    activation = None

    try:
        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.code == "DEV_MVP")
            .one()
        )

        now = datetime.now(timezone.utc)

        organization = Organization(
            name=f"License Integration Test {uuid4()}",
            legal_name="License Integration Test",
        )
        db.add(organization)
        db.flush()

        subscription = Subscription(
            organization_id=organization.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            provider="internal_test",
            provider_subscription_id=f"test-{uuid4()}",
            price=plan.price,
            currency=plan.currency,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db.add(subscription)
        db.flush()

        device = LicensedDevice(
            organization_id=organization.id,
            branch_id=None,
            device_type=LicensedDeviceType.WINDOWS,
            device_name="Integration Test Windows",
            device_identifier=f"test-device-{uuid4()}",
            status=LicensedDeviceStatus.ACTIVE,
        )
        db.add(device)
        db.flush()

        activation = DeviceActivation(
            device_id=device.id,
            subscription_id=subscription.id,
            status=DeviceActivationStatus.ACTIVE,
            activation_reference=f"test-activation-{uuid4()}",
            activated_at=now,
        )
        db.add(activation)
        db.flush()

        db.commit()

        signed_license = issue_signed_license(
            db,
            organization_id=organization.id,
            device_id=device.id,
            activation_reference=activation.activation_reference,
            device_type=device.device_type.value,
            license_id=uuid4(),
            issued_at=now,
        )

        payload = signed_license.payload

        print("ISSUANCE_SUCCESS=", True)
        print("FORMAT_VERSION=", signed_license.format_version)
        print("KEY_ID=", signed_license.key_id)
        print("ORGANIZATION_MATCH=", payload.organization_id == organization.id)
        print("DEVICE_MATCH=", payload.device_id == device.id)
        print("SUBSCRIPTION_MATCH=", payload.subscription_id == subscription.id)
        print(
            "ACTIVATION_REFERENCE_MATCH=",
            payload.activation_reference == activation.activation_reference,
        )
        print("DEVICE_TYPE=", payload.device_type)
        print("ENTITLEMENTS=", payload.entitlements)
        print(
            "EXPIRY_MATCH=",
            payload.expires_at == subscription.current_period_end,
        )
        print(
            "OFFLINE_WITHIN_SUBSCRIPTION=",
            payload.offline_valid_until <= subscription.current_period_end,
        )
        print(
            "OFFLINE_VALIDITY_DAYS=",
            (payload.offline_valid_until - payload.issued_at).total_seconds()
            / 86400,
        )
        print(
            "SIGNATURE_VALID=",
            verify_signed_license(signed_license),
        )

    finally:
        if activation is not None:
            db.delete(activation)

        if device is not None:
            db.delete(device)

        if subscription is not None:
            db.delete(subscription)

        if organization is not None:
            db.delete(organization)

        db.commit()
        db.close()


if __name__ == "__main__":
    main()
