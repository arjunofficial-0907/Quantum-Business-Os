from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentStatus
from app.models.payment_recovery import (
    PaymentRecoveryAttempt,
    PaymentRecoveryAttemptStatus,
)
from app.services.payment_recovery_contract import (
    PaymentRecoveryError,
    PaymentRecoveryNotAllowed,
    PaymentRecoveryRequest,
)
from app.services.payment_recovery import (
    create_recovery_attempt,
    mark_recovery_failed,
    mark_recovery_processing,
    mark_recovery_succeeded,
)


db = SessionLocal()

try:
    organization = Organization(
        name=f"Recovery Test Org {uuid4().hex[:8]}",
    )
    db.add(organization)
    db.flush()

    invoice = Invoice(
        id=uuid4(),
        organization_id=organization.id,
        invoice_number=f"RECOVERY-TEST-{uuid4().hex[:8]}",
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
        status=PaymentStatus.FAILED,
        provider="mock",
        provider_payment_id=f"mock_pay_{uuid4().hex}",
    )
    db.add(payment)
    db.flush()

    # ---------------------------------------------------------
    # CREATE ATTEMPT #1
    # ---------------------------------------------------------

    attempt_one = create_recovery_attempt(
        db,
        request=PaymentRecoveryRequest(
            payment_id=payment.id,
            organization_id=organization.id,
            amount=Decimal("1000.00"),
            currency="INR",
            attempt_number=1,
        ),
    )

    assert attempt_one.attempt_number == 1
    assert attempt_one.status == PaymentRecoveryAttemptStatus.PENDING

    # ---------------------------------------------------------
    # PROCESSING
    # ---------------------------------------------------------

    processing_attempt = mark_recovery_processing(
        db,
        attempt_id=attempt_one.id,
        organization_id=organization.id,
    )

    assert processing_attempt.status == (
        PaymentRecoveryAttemptStatus.PROCESSING
    )

    # ---------------------------------------------------------
    # FAILED ATTEMPT
    # ---------------------------------------------------------

    failed_attempt = mark_recovery_failed(
        db,
        attempt_id=attempt_one.id,
        organization_id=organization.id,
        error_message="Provider declined recovery attempt.",
    )

    assert failed_attempt.status == PaymentRecoveryAttemptStatus.FAILED
    assert failed_attempt.error_message is not None

    # ---------------------------------------------------------
    # CREATE ATTEMPT #2
    # ---------------------------------------------------------

    attempt_two = create_recovery_attempt(
        db,
        request=PaymentRecoveryRequest(
            payment_id=payment.id,
            organization_id=organization.id,
            amount=Decimal("1000.00"),
            currency="INR",
            attempt_number=2,
        ),
    )

    assert attempt_two.attempt_number == 2
    assert attempt_two.status == PaymentRecoveryAttemptStatus.PENDING

    # ---------------------------------------------------------
    # SUCCESSFUL RECOVERY
    # ---------------------------------------------------------

    succeeded_attempt = mark_recovery_succeeded(
        db,
        attempt_id=attempt_two.id,
        organization_id=organization.id,
        provider_payment_id="mock_recovery_success",
    )

    db.refresh(payment)

    assert succeeded_attempt.status == (
        PaymentRecoveryAttemptStatus.SUCCEEDED
    )
    assert succeeded_attempt.processed_at is not None
    assert succeeded_attempt.provider_payment_id == (
        "mock_recovery_success"
    )
    assert payment.status == PaymentStatus.CAPTURED
    assert payment.captured_at is not None

    # ---------------------------------------------------------
    # INVALID ATTEMPT NUMBER
    # ---------------------------------------------------------

    invalid_attempt_number_failed = False

    try:
        create_recovery_attempt(
            db,
            request=PaymentRecoveryRequest(
                payment_id=payment.id,
                organization_id=organization.id,
                amount=Decimal("1000.00"),
                currency="INR",
                attempt_number=3,
            ),
        )
    except PaymentRecoveryNotAllowed:
        invalid_attempt_number_failed = True

    assert invalid_attempt_number_failed is True

    # ---------------------------------------------------------
    # PAYMENT IS NOW CAPTURED
    # ---------------------------------------------------------

    captured_payment_recovery_failed = False

    try:
        create_recovery_attempt(
            db,
            request=PaymentRecoveryRequest(
                payment_id=payment.id,
                organization_id=organization.id,
                amount=Decimal("1000.00"),
                currency="INR",
                attempt_number=3,
            ),
        )
    except PaymentRecoveryNotAllowed:
        captured_payment_recovery_failed = True
    except PaymentRecoveryError:
        captured_payment_recovery_failed = True

    assert captured_payment_recovery_failed is True

    # ---------------------------------------------------------
    # TENANT ISOLATION
    # ---------------------------------------------------------

    other_organization = Organization(
        name=f"Recovery Other Org {uuid4().hex[:8]}",
    )
    db.add(other_organization)
    db.flush()

    tenant_isolation_failed = False

    try:
        mark_recovery_processing(
            db,
            attempt_id=attempt_two.id,
            organization_id=other_organization.id,
        )
    except PaymentRecoveryError:
        tenant_isolation_failed = True

    assert tenant_isolation_failed is True

    # ---------------------------------------------------------
    # PERSISTENCE
    # ---------------------------------------------------------

    persisted_attempts = db.execute(
        select(PaymentRecoveryAttempt).where(
            PaymentRecoveryAttempt.payment_id == payment.id
        )
    ).scalars().all()

    assert len(persisted_attempts) == 2

    db.commit()

    print("=" * 55)
    print("DAY 2.5.3 PAYMENT RECOVERY TEST PASSED")
    print("=" * 55)
    print("ATTEMPT #1 CREATION: PASS")
    print("PROCESSING STATE: PASS")
    print("FAILED ATTEMPT: PASS")
    print("ATTEMPT #2 CREATION: PASS")
    print("SUCCESSFUL RECOVERY: PASS")
    print("PAYMENT CAPTURED: PASS")
    print("ATTEMPT NUMBER VALIDATION: PASS")
    print("CAPTURED PAYMENT BLOCKED: PASS")
    print("TENANT ISOLATION: PASS")
    print("PERSISTENCE: PASS")
    print("=" * 55)

except Exception:
    db.rollback()
    raise

finally:
    db.close()