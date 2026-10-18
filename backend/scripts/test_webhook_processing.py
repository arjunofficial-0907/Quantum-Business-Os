from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import SubscriptionPlan
from app.models.webhook_event import WebhookEvent, WebhookEventStatus
from app.providers.webhooks import (
    PaymentWebhookEvent,
    WebhookEventType,
)
from app.services.webhook_processing import (
    WebhookProcessingError,
    process_payment_webhook,
)


db = SessionLocal()

try:
    organization = Organization(
        name=f"Webhook Processing Org {uuid4().hex[:8]}",
    )
    db.add(organization)
    db.flush()

    plan = db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.code == "DEV_MVP"
        )
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

    # ---------------------------------------------------------
    # CAPTURED PAYMENT
    # ---------------------------------------------------------

    invoice = Invoice(
        organization_id=organization.id,
        subscription_id=subscription.id,
        invoice_number=f"WH-{uuid4().hex[:10]}",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1000.00"),
        currency="INR",
        status=InvoiceStatus.OPEN,
    )
    db.add(invoice)
    db.flush()

    payment = Payment(
        organization_id=organization.id,
        invoice_id=invoice.id,
        amount=Decimal("1000.00"),
        currency="INR",
        status=PaymentStatus.PENDING,
        provider="mock",
        provider_payment_id=f"mock_pay_{uuid4().hex}",
    )
    db.add(payment)
    db.flush()

    event_id = f"evt_{uuid4().hex}"

    event = PaymentWebhookEvent(
        event_id=event_id,
        event_type=WebhookEventType.PAYMENT_CAPTURED,
        provider_payment_id=payment.provider_payment_id,
        organization_id=organization.id,
        invoice_id=invoice.id,
        amount=Decimal("1000.00"),
        currency="INR",
        raw_payload={
            "event": "payment.captured",
        },
    )

    processed = process_payment_webhook(
        db,
        event=event,
    )

    assert processed is True

    db.refresh(payment)
    db.refresh(invoice)

    assert payment.status == PaymentStatus.CAPTURED
    assert invoice.status == InvoiceStatus.PAID

    webhook_record = db.execute(
        select(WebhookEvent).where(
            WebhookEvent.event_id == event_id
        )
    ).scalar_one()

    assert webhook_record.status == WebhookEventStatus.PROCESSED
    assert webhook_record.processed_at is not None

    # ---------------------------------------------------------
    # DUPLICATE WEBHOOK
    # ---------------------------------------------------------

    duplicate_processed = process_payment_webhook(
        db,
        event=event,
    )

    assert duplicate_processed is False

    # ---------------------------------------------------------
    # FAILED PAYMENT
    # ---------------------------------------------------------

    failed_invoice = Invoice(
        organization_id=organization.id,
        subscription_id=subscription.id,
        invoice_number=f"WH-FAIL-{uuid4().hex[:10]}",
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("500.00"),
        currency="INR",
        status=InvoiceStatus.OPEN,
    )
    db.add(failed_invoice)
    db.flush()

    failed_payment = Payment(
        organization_id=organization.id,
        invoice_id=failed_invoice.id,
        amount=Decimal("500.00"),
        currency="INR",
        status=PaymentStatus.PENDING,
        provider="mock",
        provider_payment_id=f"mock_pay_{uuid4().hex}",
    )
    db.add(failed_payment)
    db.flush()

    failed_event = PaymentWebhookEvent(
        event_id=f"evt_{uuid4().hex}",
        event_type=WebhookEventType.PAYMENT_FAILED,
        provider_payment_id=failed_payment.provider_payment_id,
        organization_id=organization.id,
        invoice_id=failed_invoice.id,
        amount=Decimal("500.00"),
        currency="INR",
        raw_payload={
            "event": "payment.failed",
        },
    )

    failed_processed = process_payment_webhook(
        db,
        event=failed_event,
    )

    assert failed_processed is True

    db.refresh(failed_payment)
    db.refresh(failed_invoice)

    assert failed_payment.status == PaymentStatus.FAILED
    assert failed_invoice.status == InvoiceStatus.OPEN

    # ---------------------------------------------------------
    # MISMATCHED AMOUNT
    # ---------------------------------------------------------

    mismatch_event = PaymentWebhookEvent(
        event_id=f"evt_{uuid4().hex}",
        event_type=WebhookEventType.PAYMENT_CAPTURED,
        provider_payment_id=failed_payment.provider_payment_id,
        organization_id=organization.id,
        invoice_id=failed_invoice.id,
        amount=Decimal("999.00"),
        currency="INR",
        raw_payload={
            "event": "payment.captured",
        },
    )

    mismatch_failed = False

    try:
        process_payment_webhook(
            db,
            event=mismatch_event,
        )
    except WebhookProcessingError:
        mismatch_failed = True

    assert mismatch_failed is True

    mismatch_record = db.execute(
        select(WebhookEvent).where(
            WebhookEvent.event_id == mismatch_event.event_id
        )
    ).scalar_one()

    assert mismatch_record.status == WebhookEventStatus.FAILED
    assert mismatch_record.error_message is not None

    db.commit()

    print("=" * 55)
    print("DAY 2.4.5 WEBHOOK PROCESSING TEST PASSED")
    print("=" * 55)
    print("CAPTURED PAYMENT: PASS")
    print("INVOICE PAID: PASS")
    print("WEBHOOK PERSISTENCE: PASS")
    print("DUPLICATE WEBHOOK: PASS")
    print("FAILED PAYMENT: PASS")
    print("FAILED INVOICE REMAINS OPEN: PASS")
    print("MISMATCH DETECTION: PASS")
    print("=" * 55)

except Exception:
    db.rollback()
    raise

finally:
    db.close()