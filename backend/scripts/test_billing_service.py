from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.billing import BillingRecord, BillingRecordStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.organization import Organization
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import SubscriptionPlan
from app.services.billing import (
    BillingRecordError,
    PaymentError,
    create_billing_record,
    create_invoice,
    create_payment,
    mark_payment_failed,
    mark_payment_paid,
)


db = SessionLocal()

try:
    organization = Organization(
        name=f"Billing Test Org {uuid4().hex[:8]}",
    )
    db.add(organization)
    db.flush()

    plan = db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.code == "DEV_MVP")
    ).scalar_one()

    period_start = datetime.now(timezone.utc)
    period_end = period_start.replace(
        year=period_start.year + 1
    )

    subscription = Subscription(
        organization_id=organization.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        price=Decimal("0.00"),
        currency="INR",
        current_period_start=period_start,
        current_period_end=period_end,
    )
    db.add(subscription)
    db.flush()

    billing_record = create_billing_record(
        db,
        organization_id=organization.id,
        subscription_id=subscription.id,
        amount=Decimal("1000.00"),
        currency="INR",
        billing_period_start=period_start,
        billing_period_end=period_end,
        provider="test",
        provider_reference="billing-test-001",
    )

    assert billing_record.status == BillingRecordStatus.PENDING
    assert billing_record.organization_id == organization.id

    invoice = create_invoice(
        db,
        organization_id=organization.id,
        subscription_id=subscription.id,
        invoice_number=f"TEST-{uuid4().hex[:10]}",
        amount=Decimal("1000.00"),
        currency="INR",
        issued_at=period_start,
        due_at=period_end,
    )

    assert invoice.status == InvoiceStatus.OPEN
    assert invoice.total_amount == Decimal("1000.00")

    payment = create_payment(
        db,
        organization_id=organization.id,
        invoice_id=invoice.id,
        amount=Decimal("1000.00"),
        currency="INR",
        method="OTHER",
        provider="test",
        provider_payment_id="payment-test-001",
    )

    assert payment.status == PaymentStatus.PENDING

    mark_payment_paid(
        db,
        payment_id=payment.id,
        organization_id=organization.id,
        paid_at=period_start,
    )

    db.refresh(payment)
    db.refresh(invoice)

    assert payment.status == PaymentStatus.CAPTURED
    assert payment.captured_at is not None
    assert invoice.status == InvoiceStatus.PAID
    assert invoice.paid_at is not None

    failed_invoice = create_invoice(
        db,
        organization_id=organization.id,
        subscription_id=subscription.id,
        invoice_number=f"FAIL-{uuid4().hex[:10]}",
        amount=Decimal("500.00"),
        currency="INR",
        issued_at=period_start,
        due_at=period_end,
    )

    failed_payment = create_payment(
        db,
        organization_id=organization.id,
        invoice_id=failed_invoice.id,
        amount=Decimal("500.00"),
        currency="INR",
    )

    mark_payment_failed(
        db,
        payment_id=failed_payment.id,
        organization_id=organization.id,
    )

    db.refresh(failed_payment)
    db.refresh(failed_invoice)

    assert failed_payment.status == PaymentStatus.FAILED
    assert failed_invoice.status == InvoiceStatus.OPEN

    invalid_record_failed = False

    try:
        create_billing_record(
            db,
            organization_id=organization.id,
            subscription_id=subscription.id,
            amount=Decimal("100.00"),
            currency="INR",
            billing_period_start=period_end,
            billing_period_end=period_start,
        )
    except BillingRecordError:
        invalid_record_failed = True

    assert invalid_record_failed is True

    other_organization = Organization(
        name=f"Billing Other Org {uuid4().hex[:8]}",
    )
    db.add(other_organization)
    db.flush()

    tenant_isolation_failed = False

    try:
        mark_payment_paid(
            db,
            payment_id=failed_payment.id,
            organization_id=other_organization.id,
            paid_at=datetime.now(timezone.utc),
        )
    except PaymentError:
        tenant_isolation_failed = True

    assert tenant_isolation_failed is True

    db.commit()

    print("=" * 55)
    print("DAY 2.2 BILLING SERVICE INTEGRATION TEST PASSED")
    print("=" * 55)
    print("BILLING RECORD: PASS")
    print("INVOICE CREATION: PASS")
    print("PAYMENT CREATION: PASS")
    print("PAYMENT SUCCESS: PASS")
    print("INVOICE PAID: PASS")
    print("PAYMENT FAILURE: PASS")
    print("FAILED INVOICE REMAINS UNPAID: PASS")
    print("INVALID BILLING PERIOD: PASS")
    print("TENANT ISOLATION: PASS")
    print("=" * 55)

except Exception:
    db.rollback()
    raise

finally:
    db.close()