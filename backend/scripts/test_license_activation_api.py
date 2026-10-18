from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.device_activation import DeviceActivation
from app.models.licensed_device import (
    LicensedDevice,
    LicensedDeviceStatus,
)
from app.models.membership import Membership, MembershipStatus
from app.models.organization import Organization
from app.models.permission import Permission
from app.models.role import Role, role_permissions

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User, UserStatus
from app.services.signed_license import verify_signed_license


client = TestClient(app)


def cleanup(db, organization_id, user_id, device_id):
    db.query(DeviceActivation).filter(
        DeviceActivation.device_id == device_id
    ).delete(synchronize_session=False)

    db.query(LicensedDevice).filter(
        LicensedDevice.id == device_id
    ).delete(synchronize_session=False)

    db.query(Subscription).filter(
        Subscription.organization_id == organization_id
    ).delete(synchronize_session=False)

    db.query(Membership).filter(
        Membership.organization_id == organization_id
    ).delete(synchronize_session=False)

    db.query(Role).filter(
        Role.organization_id == organization_id
    ).delete(synchronize_session=False)

    db.query(Organization).filter(
        Organization.id == organization_id
    ).delete(synchronize_session=False)

    db.query(User).filter(
        User.id == user_id
    ).delete(synchronize_session=False)

    db.commit()


def main():

    db = SessionLocal()

    organization_id = uuid4()
    user_id = uuid4()
    device_id = uuid4()

    email = f"license-api-{uuid4().hex}@example.com"
    password = "LicenseApiTest123!"

    try:
        # ---------------------------------------------------------
        # 1. Create organization
        # ---------------------------------------------------------
        organization = Organization(
            id=organization_id,
            name="License API Test Organization",
        )
        db.add(organization)

        # ---------------------------------------------------------
        # 2. Create user
        # ---------------------------------------------------------
        user = User(
            id=user_id,
            email=email,
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE,
        )
        db.add(user)

        db.flush()

        # ---------------------------------------------------------
        # 3. Find existing license.activate permission
        # ---------------------------------------------------------
        permission = db.scalar(
            select(Permission).where(
                Permission.code == "license.activate"
            )
        )

        if permission is None:
            raise RuntimeError(
                "Permission 'license.activate' does not exist. "
                "Create/seed the permission before running this test."
            )

        # ---------------------------------------------------------
        # 4. Create organization role
        # ---------------------------------------------------------
        role = Role(
            id=uuid4(),
            organization_id=organization_id,
            name="License API Test Role",
        )
        db.add(role)

        db.flush()

        # ---------------------------------------------------------
        # 5. Attach permission to role
        # ---------------------------------------------------------
        db.execute(
            role_permissions.insert().values(
                role_id=role.id,
                permission_id=permission.id,
            )
        )

        # ---------------------------------------------------------
        # 6. Create active membership
        # ---------------------------------------------------------
        membership = Membership(
            id=uuid4(),
            user_id=user_id,
            organization_id=organization_id,
            role_id=role.id,
            status=MembershipStatus.ACTIVE,
        )
        db.add(membership)

        # ---------------------------------------------------------
        # 7. Find MVP plan
        # ---------------------------------------------------------
        plan = db.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.code == "DEV_MVP"
            )
        )

        if plan is None:
            raise RuntimeError(
                "DEV_MVP plan does not exist. "
                "Run scripts/seed_mvp_plan.py first."
            )

        # ---------------------------------------------------------
        # 8. Create active subscription
        # ---------------------------------------------------------
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)

        subscription = Subscription(
            id=uuid4(),
            organization_id=organization_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            provider="test",
            provider_subscription_id=f"test-{uuid4()}",
            price=0,
            currency="INR",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db.add(subscription)

        # ---------------------------------------------------------
        # 9. Create licensed device
        # ---------------------------------------------------------
        device = LicensedDevice(
            id=device_id,
            organization_id=organization_id,
            device_type="android",
            device_identifier=f"test-device-{uuid4().hex}",
            status=LicensedDeviceStatus.ACTIVE,
        )
        db.add(device)

        db.commit()

        # ---------------------------------------------------------
        # 10. Login and obtain JWT
        # ---------------------------------------------------------
        token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": email,
                "password": password,
            },
        )

        assert token_response.status_code == 200, (
            f"Login failed: "
            f"{token_response.status_code} "
            f"{token_response.text}"
        )

        access_token = token_response.json()["access_token"]

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        # ---------------------------------------------------------
        # 11. Activate license through HTTP API
        # ---------------------------------------------------------
        activation_reference = f"api-test-{uuid4()}"

        activation_response = client.post(
            "/api/v1/licenses/activate",
            params={
                "organization_id": str(organization_id),
            },
            json={
                "organization_id": str(organization_id),
                "device_id": str(device_id),
                "activation_reference": activation_reference,
            },
            headers=headers,
        )

        assert activation_response.status_code == 201, (
            f"Activation failed: "
            f"{activation_response.status_code} "
            f"{activation_response.text}"
        )

        body = activation_response.json()

        assert "license" in body

        signed_license = body["license"]

        # ---------------------------------------------------------
        # 12. Verify signed license structure
        # ---------------------------------------------------------
        assert signed_license["format_version"] == 1
        assert signed_license["payload"]["organization_id"] == str(
            organization_id
        )
        assert signed_license["payload"]["device_id"] == str(
            device_id
        )
        assert (
            signed_license["payload"]["activation_reference"]
            == activation_reference
        )

        # ---------------------------------------------------------
        # 13. Verify cryptographic signature
        # ---------------------------------------------------------
        from app.schemas.signed_license import SignedLicense

        parsed_license = SignedLicense.model_validate(
            signed_license
        )

        assert verify_signed_license(parsed_license) is True

        # ---------------------------------------------------------
        # 14. Validate signed license through offline HTTP API
        # ---------------------------------------------------------
        validation_response = client.post(
            "/api/v1/licenses/validate",
            json={
                "license": signed_license,
            },
        )

        assert validation_response.status_code == 200, (
            f"Offline validation API failed: "
            f"{validation_response.status_code} "
            f"{validation_response.text}"
        )

        validation_body = validation_response.json()

        assert validation_body["valid"] is True, (
            f"Valid license was rejected offline: "
            f"{validation_body}"
        )

        # ---------------------------------------------------------
        # 15. Validate signed license through online HTTP API
        # ---------------------------------------------------------
        online_validation_response = client.post(
            "/api/v1/licenses/validate-online",
            json={
                "license": signed_license,
            },
        )

        assert online_validation_response.status_code == 200, (
            f"Online validation API failed: "
            f"{online_validation_response.status_code} "
            f"{online_validation_response.text}"
        )

        online_validation_body = (
            online_validation_response.json()
        )

        assert online_validation_body["valid"] is True, (
            f"Valid license was rejected online: "
            f"{online_validation_body}"
        )

        # ---------------------------------------------------------
        # 16. Tampered license must be rejected
        # ---------------------------------------------------------
        tampered_license = dict(signed_license)
        tampered_license["payload"] = dict(
            signed_license["payload"]
        )

        tampered_license["payload"]["device_id"] = str(uuid4())

        tampered_response = client.post(
            "/api/v1/licenses/validate",
            json={
                "license": tampered_license,
            },
        )

        assert tampered_response.status_code == 200, (
            f"Tampered validation API failed: "
            f"{tampered_response.status_code} "
            f"{tampered_response.text}"
        )

        tampered_body = tampered_response.json()

        assert tampered_body["valid"] is False, (
            f"Tampered license was accepted: "
            f"{tampered_body}"
        )

        # ---------------------------------------------------------
        # 17. Malformed license must be rejected
        # ---------------------------------------------------------
        malformed_response = client.post(
            "/api/v1/licenses/validate",
            json={
                "license": {
                    "format_version": 1,
                },
            },
        )

        assert malformed_response.status_code == 422, (
            f"Malformed license unexpectedly accepted: "
            f"{malformed_response.status_code} "
            f"{malformed_response.text}"
        )

        # ---------------------------------------------------------
        # 18. Revoke device and verify online rejection
        # ---------------------------------------------------------
        device.status = LicensedDeviceStatus.REVOKED

        db.commit()

        revoked_device_response = client.post(
            "/api/v1/licenses/validate-online",
            json={
                "license": signed_license,
            },
        )

        assert revoked_device_response.status_code == 200, (
            f"Revoked-device validation API failed: "
            f"{revoked_device_response.status_code} "
            f"{revoked_device_response.text}"
        )

        revoked_device_body = (
            revoked_device_response.json()
        )

        assert revoked_device_body["valid"] is False, (
            f"Revoked device was accepted online: "
            f"{revoked_device_body}"
        )

        assert (
            revoked_device_body["reason"]
            == "device_not_active"
        ), (
            "Unexpected revoked-device rejection reason: "
            f"{revoked_device_body}"
        )

        # ---------------------------------------------------------
        # 19. Verify activation persisted
        # ---------------------------------------------------------
        db.expire_all()

        activation = db.scalar(
            select(DeviceActivation).where(
                DeviceActivation.device_id == device_id,
                DeviceActivation.activation_reference
                == activation_reference,
            )
        )

        assert activation is not None
        assert activation.device_id == device_id

        print()
        print("================================================")
        print("16I.6 LICENSING API INTEGRATION TEST PASSED")
        print("================================================")
        print(f"USER:                    {email}")
        print(f"ORGANIZATION:            {organization_id}")
        print(f"DEVICE:                  {device_id}")
        print(f"ACTIVATION:              {activation.id}")
        print("JWT AUTH:                PASS")
        print("RBAC:                    license.activate PASS")
        print("ACTIVATION HTTP:         201")
        print("SIGNED LICENSE:          PASS")
        print("SIGNATURE:               VALID")
        print("OFFLINE VALIDATION:      PASS")
        print("ONLINE VALIDATION:       PASS")
        print("TAMPER DETECTION:        PASS")
        print("MALFORMED INPUT:         PASS")
        print("REVOKED DEVICE:          PASS")
        print("DB PERSISTENCE:          PASS")
        print("================================================")

    finally:
        try:
            cleanup(
                db,
                organization_id,
                user_id,
                device_id,
            )
        finally:
            db.close()


if __name__ == "__main__":
    main()
