from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.billing import BillingRecord
from app.models.invoice import Invoice
from app.models.membership import Membership, MembershipStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentStatus
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.subscription import Subscription
from app.models.user import User
from app.core.authorization.permissions import PermissionCode


def cleanup(
    db,
    organization_ids: list,
    user_ids: list,
    role_ids: list,
    subscription_ids: list,
) -> None:
    db.rollback()

    for organization_id in organization_ids:
        db.query(Payment).filter(
            Payment.organization_id == organization_id
        ).delete(synchronize_session=False)

        db.query(Invoice).filter(
            Invoice.organization_id == organization_id
        ).delete(synchronize_session=False)

        db.query(BillingRecord).filter(
            BillingRecord.organization_id == organization_id
        ).delete(synchronize_session=False)

        db.query(Subscription).filter(
            Subscription.organization_id == organization_id
        ).delete(synchronize_session=False)

        db.query(Membership).filter(
            Membership.organization_id == organization_id
        ).delete(synchronize_session=False)

        db.query(Organization).filter(
            Organization.id == organization_id
        ).delete(synchronize_session=False)

    for role_id in role_ids:
        db.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id == role_id
            )
        )

        db.query(Role).filter(
            Role.id == role_id
        ).delete(synchronize_session=False)

    for user_id in user_ids:
        db.query(User).filter(
            User.id == user_id
        ).delete(synchronize_session=False)

    db.commit()


def create_role_with_permissions(
    db,
    organization_id,
    role_name: str,
    permission_codes: list[str],
) -> Role:
    role = Role(
        organization_id=organization_id,
        name=role_name,
        description=f"Billing hardening test role: {role_name}",
    )
    db.add(role)
    db.flush()

    permissions = (
        db.query(Permission)
        .filter(Permission.code.in_(permission_codes))
        .all()
    )

    found_codes = {permission.code for permission in permissions}
    missing = set(permission_codes) - found_codes

    assert not missing, f"Missing permissions: {sorted(missing)}"

    for permission in permissions:
        db.execute(
            role_permissions.insert().values(
                role_id=role.id,
                permission_id=permission.id,
            )
        )

    db.flush()
    return role


def create_test_user(db, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("TestPassword123!"),
    )
    db.add(user)
    db.flush()
    return user


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200, (
        f"Login failed for {email}: "
        f"{response.status_code} {response.text}"
    )

    return response.json()["access_token"]


def main() -> None:
    db = SessionLocal()
    client = TestClient(app)

    organization_ids = []
    user_ids = []
    role_ids = []
    subscription_ids = []

    try:
        # ============================================================
        # SETUP
        # ============================================================

        organization_a = Organization(
            name=f"Billing Hardening A {uuid4().hex[:8]}",
        )
        organization_b = Organization(
            name=f"Billing Hardening B {uuid4().hex[:8]}",
        )

        db.add_all([organization_a, organization_b])
        db.flush()

        organization_ids.extend(
            [organization_a.id, organization_b.id]
        )

        user_a = create_test_user(
            db,
            f"billing-hardening-a-{uuid4().hex[:8]}@example.com",
        )

        user_b = create_test_user(
            db,
            f"billing-hardening-b-{uuid4().hex[:8]}@example.com",
        )

        user_ids.extend([user_a.id, user_b.id])

        permission_codes = [
            PermissionCode.BILLING_RECORD_CREATE,
            PermissionCode.BILLING_RECORD_READ,
            PermissionCode.BILLING_INVOICE_CREATE,
            PermissionCode.BILLING_INVOICE_READ,
            PermissionCode.BILLING_PAYMENT_CREATE,
            PermissionCode.BILLING_PAYMENT_READ,
            PermissionCode.BILLING_PAYMENT_UPDATE,
        ]

        role_a = create_role_with_permissions(
            db,
            organization_a.id,
            "Billing Hardening Admin A",
            permission_codes,
        )

        role_b = create_role_with_permissions(
            db,
            organization_b.id,
            "Billing Hardening Admin B",
            permission_codes,
        )

        role_ids.extend([role_a.id, role_b.id])

        membership_a = Membership(
            user_id=user_a.id,
            organization_id=organization_a.id,
            role_id=role_a.id,
            status=MembershipStatus.ACTIVE,
        )

        membership_b = Membership(
            user_id=user_b.id,
            organization_id=organization_b.id,
            role_id=role_b.id,
            status=MembershipStatus.ACTIVE,
        )

        db.add_all([membership_a, membership_b])

        plan = (
            db.query(Subscription)
            .filter(Subscription.organization_id == organization_a.id)
            .first()
        )

        # Use an existing DEV_MVP plan through the SubscriptionPlan table.
        from app.models.subscription_plan import SubscriptionPlan

        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.code == "DEV_MVP")
            .first()
        )

        assert plan is not None, "DEV_MVP subscription plan not found."

        period_start = datetime.now(timezone.utc)
        period_end = period_start + timedelta(days=30)

        subscription = Subscription(
            organization_id=organization_a.id,
            plan_id=plan.id,
            price=Decimal("99.00"),
            currency="INR",
            current_period_start=period_start,
            current_period_end=period_end,
        )

        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        subscription_ids.append(subscription.id)

        token_a = login(client, user_a.email)
        token_b = login(client, user_b.email)

        headers_a = {
            "Authorization": f"Bearer {token_a}",
        }

        headers_b = {
            "Authorization": f"Bearer {token_b}",
        }

        period_start = datetime.now(timezone.utc)
        period_end = period_start + timedelta(days=30)

        # ============================================================
        # 2.7.1 INPUT / VALIDATION HARDENING
        # ============================================================

        response = client.post(
            "/api/v1/billing/records",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "subscription_id": str(subscription.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "amount": "0",
                "currency": "USD",
            },
        )
        assert response.status_code == 422

        response = client.post(
            "/api/v1/billing/records",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "subscription_id": str(subscription.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "amount": "-10",
                "currency": "USD",
            },
        )
        assert response.status_code == 422

        response = client.post(
            "/api/v1/billing/records",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "subscription_id": str(subscription.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "amount": "100",
                "currency": "US",
            },
        )
        assert response.status_code == 422

        response = client.post(
            "/api/v1/billing/payments",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "invoice_id": str(uuid4()),
                "amount": "100",
                "currency": "USD",
                "method": "INVALID_METHOD",
                "provider": "mock",
            },
        )
        assert response.status_code in (400, 404)

        print("2.7.1 INPUT VALIDATION:       PASS")

        # ============================================================
        # 2.7.2 ERROR HANDLING
        # ============================================================

        response = client.get(
            f"/api/v1/billing/invoices/{uuid4()}",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
        )
        assert response.status_code == 404

        response = client.get(
            f"/api/v1/billing/payments/{uuid4()}",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
        )
        assert response.status_code == 404

        response = client.get(
            f"/api/v1/billing/records/{uuid4()}",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
        )
        assert response.status_code == 404

        print("2.7.2 ERROR HANDLING:           PASS")

        # ============================================================
        # CREATE REAL BILLING DATA FOR REMAINING TESTS
        # ============================================================

        billing_record_response = client.post(
            "/api/v1/billing/records",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "subscription_id": str(subscription.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "amount": "100.00",
                "currency": "USD",
            },
        )

        assert billing_record_response.status_code == 201

        invoice_response = client.post(
            "/api/v1/billing/invoices",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "subscription_id": str(subscription.id),
                "invoice_number": f"HARD-{uuid4().hex[:10]}",
                "subtotal": "100.00",
                "tax_amount": "0.00",
                "total_amount": "100.00",
                "currency": "USD",
            },
        )

        assert invoice_response.status_code == 201
        invoice_id = invoice_response.json()["id"]

        payment_response = client.post(
            "/api/v1/billing/payments",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "invoice_id": invoice_id,
                "amount": "100.00",
                "currency": "USD",
                "method": "card",
                "provider": "mock",
            },
        )

        assert payment_response.status_code == 201
        payment_id = payment_response.json()["id"]

        # ============================================================
        # 2.7.3 TENANT ISOLATION EDGE CASES
        # ============================================================

        response = client.get(
            f"/api/v1/billing/invoices/{invoice_id}",
            params={"organization_id": str(organization_b.id)},
            headers=headers_b,
        )
        assert response.status_code == 404

        response = client.get(
            f"/api/v1/billing/payments/{payment_id}",
            params={"organization_id": str(organization_b.id)},
            headers=headers_b,
        )
        assert response.status_code == 404

        billing_record_id = billing_record_response.json()["id"]

        response = client.get(
            f"/api/v1/billing/records/{billing_record_id}",
            params={"organization_id": str(organization_b.id)},
            headers=headers_b,
        )
        assert response.status_code == 404

        print("2.7.3 TENANT ISOLATION:         PASS")

        # ============================================================
        # 2.7.4 PAYMENT STATE TRANSITION PROTECTION
        # ============================================================

        response = client.post(
            f"/api/v1/billing/payments/{payment_id}/paid",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
        )
        assert response.status_code == 200

        # CAPTURED -> PAID again should fail.
        response = client.post(
            f"/api/v1/billing/payments/{payment_id}/paid",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
        )
        print("2.7.4 DEBUG STATUS:", response.status_code)
        print("2.7.4 DEBUG BODY:", response.text)
        assert response.status_code == 400

        # CAPTURED -> FAILED should fail.
        response = client.post(
            f"/api/v1/billing/payments/{payment_id}/failed",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
        )
        assert response.status_code == 400

        print("2.7.4 PAYMENT STATE PROTECTION: PASS")

        # ============================================================
        # 2.7.5 DUPLICATE / INVALID OPERATIONS
        # ============================================================

        duplicate_invoice_number = f"DUP-{uuid4().hex[:10]}"

        first_invoice = client.post(
            "/api/v1/billing/invoices",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "subscription_id": str(subscription.id),
                "invoice_number": duplicate_invoice_number,
                "subtotal": "50.00",
                "tax_amount": "0.00",
                "total_amount": "50.00",
                "currency": "USD",
            },
        )

        assert first_invoice.status_code == 201

        second_invoice = client.post(
            "/api/v1/billing/invoices",
            params={"organization_id": str(organization_a.id)},
            headers=headers_a,
            json={
                "subscription_id": str(subscription.id),
                "invoice_number": duplicate_invoice_number,
                "subtotal": "50.00",
                "tax_amount": "0.00",
                "total_amount": "50.00",
                "currency": "USD",
            },
        )

        assert second_invoice.status_code in (400, 409, 422, 500)

        print("2.7.5 DUPLICATE OPERATIONS:     PASS")

        # ============================================================
        # 2.7.6 REGRESSION / RBAC
        # ============================================================

        response = client.post(
            "/api/v1/billing/invoices",
            params={"organization_id": str(organization_a.id)},
            headers=headers_b,
            json={
                "subscription_id": str(subscription.id),
                "invoice_number": f"RBAC-{uuid4().hex[:10]}",
                "subtotal": "100.00",
                "tax_amount": "0.00",
                "total_amount": "100.00",
                "currency": "USD",
            },
        )

        assert response.status_code == 403

        response = client.post(
            "/api/v1/billing/payments",
            params={"organization_id": str(organization_a.id)},
            headers=headers_b,
            json={
                "invoice_id": invoice_id,
                "amount": "100.00",
                "currency": "USD",
                "method": "card",
                "provider": "mock",
            },
        )

        assert response.status_code == 403

        print("2.7.6 REGRESSION / RBAC:        PASS")

        print()
        print("=" * 55)
        print("DAY 2.7 BILLING API HARDENING PASSED")
        print("=" * 55)
        print("2.7.1 INPUT VALIDATION:          PASS")
        print("2.7.2 ERROR HANDLING:            PASS")
        print("2.7.3 TENANT ISOLATION:          PASS")
        print("2.7.4 PAYMENT STATE PROTECTION:  PASS")
        print("2.7.5 DUPLICATE OPERATIONS:      PASS")
        print("2.7.6 REGRESSION / RBAC:         PASS")
        print("=" * 55)

    finally:
        cleanup(
            db,
            organization_ids,
            user_ids,
            role_ids,
            subscription_ids,
        )
        db.close()


if __name__ == "__main__":
    main()