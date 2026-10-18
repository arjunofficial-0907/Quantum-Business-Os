from decimal import Decimal
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.services.payment_recovery import create_recovery_attempt
from app.services.payment_recovery_contract import (
    PaymentRecoveryError,
    PaymentRecoveryRequest,
)
from app.services.payment_recovery_policy import (
    PaymentRecoveryPolicy,
    check_recovery_eligibility,
    validate_recovery_amount,
    validate_recovery_currency,
)


db = SessionLocal()

try:
    organization = Organization(
        id=uuid4(),
        name=f"Recovery Policy Test {uuid4().hex[:8]}",
    )

    db.add(organization)
    db.flush()

    invoice = Invoice(
        id=uuid4(),
        organization_id=organization.id,
        invoice_number=f"RECOVERY-POLICY-{uuid4().hex[:8]}",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1000.00"),
        currency="INR",
        status=InvoiceStatus.OPEN,
    )

    db.add(invoice)
    db.flush()

    payment = Payment(
        id=uuid4(),
        organization_id=organization.id,
        invoice_id=invoice.id,
        amount=Decimal("1000.00"),
        currency="INR",
        status=PaymentStatus.FAILED,
        method=PaymentMethod.OTHER,
        provider="mock",
    )

    db.add(payment)
    db.flush()

    # Initial payment must be eligible.
    eligibility = check_recovery_eligibility(
        db,
        payment_id=payment.id,
        organization_id=organization.id,
    )

    assert eligibility.allowed is True
    assert eligibility.next_attempt_number == 1

    # Create attempt #1.
    attempt1 = create_recovery_attempt(
        db,
        request=PaymentRecoveryRequest(
            payment_id=payment.id,
            organization_id=organization.id,
            amount=Decimal("1000.00"),
            currency="INR",
            attempt_number=1,
        ),
    )

    # Create attempt #2.
    attempt2 = create_recovery_attempt(
        db,
        request=PaymentRecoveryRequest(
            payment_id=payment.id,
            organization_id=organization.id,
            amount=Decimal("1000.00"),
            currency="INR",
            attempt_number=2,
        ),
    )

    # Create attempt #3.
    attempt3 = create_recovery_attempt(
        db,
        request=PaymentRecoveryRequest(
            payment_id=payment.id,
            organization_id=organization.id,
            amount=Decimal("1000.00"),
            currency="INR",
            attempt_number=3,
        ),
    )

    eligibility = check_recovery_eligibility(
        db,
        payment_id=payment.id,
        organization_id=organization.id,
    )

    assert eligibility.allowed is False
    assert eligibility.next_attempt_number == 4
    assert eligibility.reason == "Maximum recovery attempts reached."

    # Non-failed payment must be blocked.
    payment.status = PaymentStatus.CAPTURED
    db.flush()

    eligibility = check_recovery_eligibility(
        db,
        payment_id=payment.id,
        organization_id=organization.id,
    )

    assert eligibility.allowed is False
    assert eligibility.reason == (
        "Only failed payments are eligible for recovery."
    )

    # Amount validation.
    validate_recovery_amount(
        payment_amount=Decimal("1000.00"),
        recovery_amount=Decimal("1000.00"),
    )

    try:
        validate_recovery_amount(
            payment_amount=Decimal("1000.00"),
            recovery_amount=Decimal("1000.01"),
        )
        raise AssertionError("Expected amount validation failure.")
    except PaymentRecoveryError:
        pass

    # Currency validation.
    validate_recovery_currency(
        payment_currency="INR",
        recovery_currency="inr",
    )

    try:
        validate_recovery_currency(
            payment_currency="INR",
            recovery_currency="USD",
        )
        raise AssertionError("Expected currency validation failure.")
    except PaymentRecoveryError:
        pass

    # Custom policy validation.
    custom_policy = PaymentRecoveryPolicy(max_attempts=5)

    assert custom_policy.max_attempts == 5

    print("=" * 55)
    print("DAY 2.5.5 RECOVERY POLICY TEST PASSED")
    print("=" * 55)
    print("INITIAL ELIGIBILITY: PASS")
    print("ATTEMPT LIMIT: PASS")
    print("MAX ATTEMPTS BLOCKED: PASS")
    print("NON-FAILED PAYMENT BLOCKED: PASS")
    print("AMOUNT VALIDATION: PASS")
    print("CURRENCY VALIDATION: PASS")
    print("CUSTOM POLICY: PASS")
    print("=" * 55)

    db.commit()

except Exception:
    db.rollback()
    raise

finally:
    db.close()