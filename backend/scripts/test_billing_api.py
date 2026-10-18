from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.billing import BillingRecord
from app.models.invoice import Invoice
from app.models.membership import Membership, MembershipStatus
from app.models.organization import Organization
from app.models.payment import Payment
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User, UserStatus


client = TestClient(app)


BILLING_PERMISSIONS = [
    "billing.record.create",
    "billing.record.read",
    "billing.invoice.create",
    "billing.invoice.read",
    "billing.payment.create",
    "billing.payment.read",
    "billing.payment.update",
]


def cleanup(
    db,
    organization_id,
    user_id,
):
    db.query(BillingRecord).filter(
        BillingRecord.organization_id == organization_id
    ).delete(synchronize_session=False)

    db.query(Payment).filter(
        Payment.organization_id == organization_id
    ).delete(synchronize_session=False)
    
    db.query(Invoice).filter(
        Invoice.organization_id == organization_id
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
    other_organization_id = uuid4()
    user_id = uuid4()
    other_user_id = uuid4()

    email = f"billing-api-{uuid4().hex}@example.com"
    other_email = f"billing-api-other-{uuid4().hex}@example.com"
    password = "BillingApiTest123!"

    try:
        # ---------------------------------------------------------
        # 1. Create organizations
        # ---------------------------------------------------------
        organization = Organization(
            id=organization_id,
            name="Billing API Test Organization",
        )

        other_organization = Organization(
            id=other_organization_id,
            name="Billing API Other Organization",
        )

        db.add_all([
            organization,
            other_organization,
        ])

        # ---------------------------------------------------------
        # 2. Create users
        # ---------------------------------------------------------
        user = User(
            id=user_id,
            email=email,
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE,
        )

        other_user = User(
            id=other_user_id,
            email=other_email,
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE,
        )

        db.add_all([
            user,
            other_user,
        ])

        db.flush()

        # ---------------------------------------------------------
        # 3. Find billing permissions
        # ---------------------------------------------------------
        permissions = {}

        for permission_code in BILLING_PERMISSIONS:
            permission = db.scalar(
                select(Permission).where(
                    Permission.code == permission_code
                )
            )

            if permission is None:
                raise RuntimeError(
                    f"Permission '{permission_code}' does not exist. "
                    "Run scripts/seed_permissions.py first."
                )

            permissions[permission_code] = permission

        # ---------------------------------------------------------
        # 4. Create roles
        # ---------------------------------------------------------
        role = Role(
            id=uuid4(),
            organization_id=organization_id,
            name="Billing API Test Role",
        )

        other_role = Role(
            id=uuid4(),
            organization_id=other_organization_id,
            name="Other Organization Role",
        )

        db.add_all([
            role,
            other_role,
        ])

        db.flush()

        # ---------------------------------------------------------
        # 5. Attach all billing permissions to test role
        # ---------------------------------------------------------
        for permission in permissions.values():
            db.execute(
                role_permissions.insert().values(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )

        # ---------------------------------------------------------
        # 6. Attach only invoice.read to other role
        # ---------------------------------------------------------
        db.execute(
            role_permissions.insert().values(
                role_id=other_role.id,
                permission_id=permissions[
                    "billing.invoice.read"
                ].id,
            )
        )

        # ---------------------------------------------------------
        # 7. Create memberships
        # ---------------------------------------------------------
        membership = Membership(
            id=uuid4(),
            user_id=user_id,
            organization_id=organization_id,
            role_id=role.id,
            status=MembershipStatus.ACTIVE,
        )

        other_membership = Membership(
            id=uuid4(),
            user_id=other_user_id,
            organization_id=other_organization_id,
            role_id=other_role.id,
            status=MembershipStatus.ACTIVE,
        )

        db.add_all([
            membership,
            other_membership,
        ])

        # ---------------------------------------------------------
        # 8. Find MVP plan
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
        # 9. Create subscription
        # ---------------------------------------------------------
        now = datetime.now(timezone.utc)

        subscription = Subscription(
            id=uuid4(),
            organization_id=organization_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            provider="test",
            provider_subscription_id=f"billing-test-{uuid4()}",
            price=0,
            currency="INR",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )

        db.add(subscription)

        db.commit()

        # ---------------------------------------------------------
        # 10. Login
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
        # 11. Create billing record
        # ---------------------------------------------------------
        period_start = now
        period_end = now + timedelta(days=30)

        billing_record_response = client.post(
            "/api/v1/billing/records",
            params={
                "organization_id": str(organization_id),
            },
            json={
                "subscription_id": str(subscription.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "amount": "1000.00",
                "currency": "INR",
                "description": "Billing API integration test",
            },
            headers=headers,
        )

        assert billing_record_response.status_code == 201, (
            f"Billing record creation failed: "
            f"{billing_record_response.status_code} "
            f"{billing_record_response.text}"
        )

        billing_record = billing_record_response.json()

        assert billing_record["organization_id"] == str(
            organization_id
        )

        # ---------------------------------------------------------
        # 12. Read billing record
        # ---------------------------------------------------------
        billing_record_read = client.get(
            f"/api/v1/billing/records/{billing_record['id']}",
            params={
                "organization_id": str(organization_id),
            },
            headers=headers,
        )

        assert billing_record_read.status_code == 200, (
            f"Billing record read failed: "
            f"{billing_record_read.status_code} "
            f"{billing_record_read.text}"
        )

        # ---------------------------------------------------------
        # 13. Create invoice
        # ---------------------------------------------------------
        invoice_response = client.post(
            "/api/v1/billing/invoices",
            params={
                "organization_id": str(organization_id),
            },
            json={
                "subscription_id": str(subscription.id),
                "invoice_number": f"BILLING-TEST-{uuid4().hex[:8]}",
                "subtotal": "1000.00",
                "tax_amount": "0.00",
                "total_amount": "1000.00",
                "currency": "INR",
                "description": "Billing API integration invoice",
            },
            headers=headers,
        )

        assert invoice_response.status_code == 201, (
            f"Invoice creation failed: "
            f"{invoice_response.status_code} "
            f"{invoice_response.text}"
        )

        invoice = invoice_response.json()

        # ---------------------------------------------------------
        # 14. Read invoice
        # ---------------------------------------------------------
        invoice_read = client.get(
            f"/api/v1/billing/invoices/{invoice['id']}",
            params={
                "organization_id": str(organization_id),
            },
            headers=headers,
        )

        assert invoice_read.status_code == 200, (
            f"Invoice read failed: "
            f"{invoice_read.status_code} "
            f"{invoice_read.text}"
        )

        # ---------------------------------------------------------
        # 15. Create payment
        # ---------------------------------------------------------
        payment_response = client.post(
            "/api/v1/billing/payments",
            params={
                "organization_id": str(organization_id),
            },
            json={
                "invoice_id": invoice["id"],
                "amount": "1000.00",
                "currency": "INR",
                "method": "other",
                "provider": "mock",
            },
            headers=headers,
        )

        assert payment_response.status_code == 201, (
            f"Payment creation failed: "
            f"{payment_response.status_code} "
            f"{payment_response.text}"
        )

        payment = payment_response.json()

        # ---------------------------------------------------------
        # 16. Read payment
        # ---------------------------------------------------------
        payment_read = client.get(
            f"/api/v1/billing/payments/{payment['id']}",
            params={
                "organization_id": str(organization_id),
            },
            headers=headers,
        )

        assert payment_read.status_code == 200, (
            f"Payment read failed: "
            f"{payment_read.status_code} "
            f"{payment_read.text}"
        )

        # ---------------------------------------------------------
        # 17. Mark payment paid
        # ---------------------------------------------------------
        paid_response = client.post(
            f"/api/v1/billing/payments/{payment['id']}/paid",
            params={
                "organization_id": str(organization_id),
            },
            headers=headers,
        )

        assert paid_response.status_code == 200, (
            f"Payment update failed: "
            f"{paid_response.status_code} "
            f"{paid_response.text}"
        )

        assert paid_response.json()["status"].lower() == "captured"

        # ---------------------------------------------------------
        # 18. Tenant isolation
        # ---------------------------------------------------------
        cross_tenant_invoice = client.get(
            f"/api/v1/billing/invoices/{invoice['id']}",
            params={
                "organization_id": str(other_organization_id),
            },
            headers=headers,
        )

        assert cross_tenant_invoice.status_code == 403, (
            f"Cross-tenant access unexpectedly allowed: "
            f"{cross_tenant_invoice.status_code} "
            f"{cross_tenant_invoice.text}"
        )

        # ---------------------------------------------------------
        # 19. RBAC denial
        # ---------------------------------------------------------
        other_token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": other_email,
                "password": password,
            },
        )

        assert other_token_response.status_code == 200

        other_access_token = other_token_response.json()[
            "access_token"
        ]

        other_headers = {
            "Authorization": f"Bearer {other_access_token}",
        }

        unauthorized_invoice = client.post(
            "/api/v1/billing/invoices",
            params={
                "organization_id": str(other_organization_id),
            },
            json={
                "invoice_number": f"UNAUTHORIZED-{uuid4().hex[:8]}",
                "subtotal": "100.00",
                "tax_amount": "0.00",
                "total_amount": "100.00",
                "currency": "INR",
            },
            headers=other_headers,
        )

        assert unauthorized_invoice.status_code == 403, (
            f"RBAC denial failed: "
            f"{unauthorized_invoice.status_code} "
            f"{unauthorized_invoice.text}"
        )

        print()
        print("=" * 55)
        print("DAY 2.6 BILLING API INTEGRATION TEST PASSED")
        print("=" * 55)
        print("JWT AUTH:                PASS")
        print("BILLING RECORD CREATE:   PASS")
        print("BILLING RECORD READ:     PASS")
        print("INVOICE CREATE:          PASS")
        print("INVOICE READ:            PASS")
        print("PAYMENT CREATE:          PASS")
        print("PAYMENT READ:            PASS")
        print("PAYMENT UPDATE:          PASS")
        print("TENANT ISOLATION:        PASS")
        print("RBAC DENIAL:             PASS")
        print("=" * 55)

    finally:
        try:
            cleanup(
                db,
                organization_id,
                user_id,
            )
            cleanup(
                db,
                other_organization_id,
                other_user_id,
            )
        finally:
            db.close()


if __name__ == "__main__":
    main()