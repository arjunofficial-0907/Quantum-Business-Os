import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.device_activation import (
    DeviceActivation,
    DeviceActivationStatus,
)
from app.models.licensed_device import (
    LicensedDevice,
    LicensedDeviceStatus,
    LicensedDeviceType,
)
from app.models.organization import (
    Organization,
    OrganizationStatus,
)
from app.models.subscription import (
    Subscription,
    SubscriptionStatus,
)
from app.models.subscription_plan import SubscriptionPlan
from app.services.license_issuance import issue_signed_license
from app.services.license_online_validation import (
    validate_signed_license_online,
)


def main() -> None:
    db = SessionLocal()

    organization = None
    subscription = None
    device = None
    activation = None
    second_device = None
    second_activation = None

    try:
        now = datetime.now(timezone.utc)

        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.code == "DEV_MVP")
            .one()
        )

        organization = Organization(
            name=f"Online Validation Test {uuid4()}",
            legal_name="Online Validation Test",
            status=OrganizationStatus.ACTIVE,
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
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=30),
        )
        db.add(subscription)
        db.flush()

        device = LicensedDevice(
            organization_id=organization.id,
            branch_id=None,
            device_type=LicensedDeviceType.WINDOWS,
            device_name="Online Validation Test Device",
            device_identifier=f"online-test-{uuid4()}",
            status=LicensedDeviceStatus.ACTIVE,
        )
        db.add(device)
        db.flush()

        activation = DeviceActivation(
            device_id=device.id,
            subscription_id=subscription.id,
            status=DeviceActivationStatus.ACTIVE,
            activation_reference=f"online-test-{uuid4()}",
            activated_at=now,
            expires_at=subscription.current_period_end,
        )
        db.add(activation)
        db.flush()

        license = issue_signed_license(
            db,
            organization_id=organization.id,
            device_id=device.id,
            activation_reference=activation.activation_reference,
            device_type=device.device_type.value,
            license_id=uuid4(),
        )

        db.commit()

        validation_now = (
            license.payload.issued_at
            + timedelta(seconds=1)
        )

        # ---------------------------------------------------------
        # Active license
        # ---------------------------------------------------------

        valid = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print("ACTIVE_VALID=", valid.valid)
        print("ACTIVE_REASON=", valid.reason)

        # ---------------------------------------------------------
        # Revoked device
        # ---------------------------------------------------------

        device.status = LicensedDeviceStatus.REVOKED
        db.commit()

        revoked_device = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "REVOKED_DEVICE_VALID=",
            revoked_device.valid,
        )
        print(
            "REVOKED_DEVICE_REASON=",
            revoked_device.reason,
        )

        # Restore device
        device.status = LicensedDeviceStatus.ACTIVE
        db.commit()

        # ---------------------------------------------------------
        # Revoked activation
        # ---------------------------------------------------------

        activation.status = DeviceActivationStatus.REVOKED
        db.commit()

        revoked_activation = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "REVOKED_ACTIVATION_VALID=",
            revoked_activation.valid,
        )
        print(
            "REVOKED_ACTIVATION_REASON=",
            revoked_activation.reason,
        )

        # Restore activation
        activation.status = DeviceActivationStatus.ACTIVE
        db.commit()

        # ---------------------------------------------------------
        # Suspended organization
        # ---------------------------------------------------------

        organization.status = OrganizationStatus.SUSPENDED
        db.commit()

        suspended_org = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "SUSPENDED_ORG_VALID=",
            suspended_org.valid,
        )
        print(
            "SUSPENDED_ORG_REASON=",
            suspended_org.reason,
        )

        # Restore organization
        organization.status = OrganizationStatus.ACTIVE
        db.commit()

        # ---------------------------------------------------------
        # Cancelled subscription
        # ---------------------------------------------------------

        subscription.status = SubscriptionStatus.CANCELLED
        db.commit()

        cancelled_subscription = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "CANCELLED_SUBSCRIPTION_VALID=",
            cancelled_subscription.valid,
        )
        print(
            "CANCELLED_SUBSCRIPTION_REASON=",
            cancelled_subscription.reason,
        )

        # Restore subscription
        subscription.status = SubscriptionStatus.ACTIVE
        db.commit()

        # ---------------------------------------------------------
        # Expired subscription
        # ---------------------------------------------------------

        original_subscription_end = subscription.current_period_end

        subscription.current_period_end = (
            validation_now - timedelta(seconds=1)
        )
        db.commit()

        expired_subscription = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "EXPIRED_SUBSCRIPTION_VALID=",
            expired_subscription.valid,
        )
        print(
            "EXPIRED_SUBSCRIPTION_REASON=",
            expired_subscription.reason,
        )

        # Restore subscription
        subscription.current_period_end = original_subscription_end
        db.commit()

        # ---------------------------------------------------------
        # Expired activation
        # ---------------------------------------------------------

        original_activation_expiry = activation.expires_at

        activation.expires_at = (
            validation_now - timedelta(seconds=1)
        )
        db.commit()

        expired_activation = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "EXPIRED_ACTIVATION_VALID=",
            expired_activation.valid,
        )
        print(
            "EXPIRED_ACTIVATION_REASON=",
            expired_activation.reason,
        )

        # Restore activation
        activation.expires_at = original_activation_expiry
        db.commit()

        # ---------------------------------------------------------
        # Suspended device
        # ---------------------------------------------------------

        device.status = LicensedDeviceStatus.SUSPENDED
        db.commit()

        suspended_device = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "SUSPENDED_DEVICE_VALID=",
            suspended_device.valid,
        )
        print(
            "SUSPENDED_DEVICE_REASON=",
            suspended_device.reason,
        )

        # Restore device
        device.status = LicensedDeviceStatus.ACTIVE
        db.commit()

        # ---------------------------------------------------------
        # Paused subscription
        # ---------------------------------------------------------

        subscription.status = SubscriptionStatus.PAUSED
        db.commit()

        paused_subscription = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "PAUSED_SUBSCRIPTION_VALID=",
            paused_subscription.valid,
        )
        print(
            "PAUSED_SUBSCRIPTION_REASON=",
            paused_subscription.reason,
        )

        # Restore subscription
        subscription.status = SubscriptionStatus.ACTIVE
        db.commit()

        # ---------------------------------------------------------
        # Tampered signed payload
        # ---------------------------------------------------------

        original_max_devices = license.payload.entitlements[
            "max_devices"
        ]

        license.payload.entitlements["max_devices"] = 999

        tampered_license = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "TAMPERED_LICENSE_VALID=",
            tampered_license.valid,
        )
        print(
            "TAMPERED_LICENSE_REASON=",
            tampered_license.reason,
        )

        # Restore in-memory payload
        license.payload.entitlements[
            "max_devices"
        ] = original_max_devices

        # ---------------------------------------------------------
        # Identity binding
        # ---------------------------------------------------------

        # Create a second device belonging to the same organization.
        second_device = LicensedDevice(
            organization_id=organization.id,
            branch_id=None,
            device_type=LicensedDeviceType.WINDOWS,
            device_name="Identity Binding Test Device",
            device_identifier=f"identity-test-{uuid4()}",
            status=LicensedDeviceStatus.ACTIVE,
        )
        db.add(second_device)
        db.flush()

        second_activation = DeviceActivation(
            device_id=second_device.id,
            subscription_id=subscription.id,
            status=DeviceActivationStatus.ACTIVE,
            activation_reference=f"identity-test-{uuid4()}",
            activated_at=validation_now,
            expires_at=subscription.current_period_end,
        )
        db.add(second_activation)
        db.commit()

        # Original license must remain valid for its original device.
        original_identity_result = validate_signed_license_online(
            db,
            license,
            now=validation_now,
        )

        print(
            "ORIGINAL_IDENTITY_VALID=",
            original_identity_result.valid,
        )
        print(
            "ORIGINAL_IDENTITY_REASON=",
            original_identity_result.reason,
        )

        # A license referencing the second device but using the
        # original activation reference must not cross-bind.
        cross_bound_license = issue_signed_license(
            db,
            organization_id=organization.id,
            device_id=second_device.id,
            activation_reference=activation.activation_reference,
            device_type=second_device.device_type.value,
            license_id=uuid4(),
            issued_at=validation_now,
        )

        cross_bound_result = validate_signed_license_online(
            db,
            cross_bound_license,
            now=validation_now,
        )

        print(
            "CROSS_BOUND_VALID=",
            cross_bound_result.valid,
        )
        print(
            "CROSS_BOUND_REASON=",
            cross_bound_result.reason,
        )

        # A license for the second device with its correct activation
        # must validate successfully.
        second_license = issue_signed_license(
            db,
            organization_id=organization.id,
            device_id=second_device.id,
            activation_reference=second_activation.activation_reference,
            device_type=second_device.device_type.value,
            license_id=uuid4(),
            issued_at=validation_now,
        )

        second_valid_result = validate_signed_license_online(
            db,
            second_license,
            now=validation_now,
        )

        print(
            "SECOND_DEVICE_VALID=",
            second_valid_result.valid,
        )
        print(
            "SECOND_DEVICE_REASON=",
            second_valid_result.reason,
        )


    finally:
        db.rollback()

        # Delete test data from the bottom of the dependency tree.
        if activation is not None:
            existing = db.get(
                DeviceActivation,
                activation.id,
            )
            if existing is not None:
                db.delete(existing)

        if second_activation is not None:
            existing = db.get(
                DeviceActivation,
                second_activation.id,
            )
            if existing is not None:
                db.delete(existing)

        if device is not None:
            existing = db.get(
                LicensedDevice,
                device.id,
            )
            if existing is not None:
                db.delete(existing)

        if second_device is not None:
            existing = db.get(
                LicensedDevice,
                second_device.id,
            )
            if existing is not None:
                db.delete(existing)

        if organization is not None:
            existing = db.get(
                Organization,
                organization.id,
            )
            if existing is not None:
                db.delete(existing)

        db.commit()
        db.close()


if __name__ == "__main__":
    main()