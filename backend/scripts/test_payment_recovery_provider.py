from decimal import Decimal
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.providers.mock import MockPaymentProvider
from app.services.payment_recovery_contract import PaymentRecoveryError
from app.services.payment_recovery_provider import recover_payment_with_provider


db = SessionLocal()

try:
    organization = Organization(
        id=uuid4(),
        name=f"Recovery Provider Test {uuid4().hex[:8]}",
    )

    db.add(organization)
    db.flush()

    invoice = Invoice(
        id=uuid4(),
        organization_id=organization.id,
        invoice_number=f"RECOVERY-PROVIDER-{uuid4().hex[:8]}",
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
        provider_payment_id=None,
    )

    db.add(payment)
    db.flush()

    provider = MockPaymentProvider()

    recovered_payment = recover_payment_with_provider(
        db,
        payment_id=payment.id,
        organization_id=organization.id,
        payment_provider=provider,
    )

    db.refresh(recovered_payment)
    db.refresh(invoice)

    assert recovered_payment.status == PaymentStatus.CAPTURED
    assert recovered_payment.provider_payment_id is not None
    assert recovered_payment.captured_at is not None

    assert invoice.status == InvoiceStatus.PAID
    assert invoice.paid_at is not None

    attempts = recovered_payment.recovery_attempts

    assert len(attempts) == 1
    assert attempts[0].status.value == "succeeded"
    assert attempts[0].provider_payment_id is not None

    print("=" * 55)
    print("DAY 2.5.4 PROVIDER-BACKED RECOVERY TEST PASSED")
    print("=" * 55)
    print("PROVIDER PAYMENT CREATION: PASS")
    print("PROVIDER PAYMENT CAPTURE: PASS")
    print("RECOVERY SUCCEEDED: PASS")
    print("PAYMENT CAPTURED: PASS")
    print("INVOICE PAID: PASS")
    print("RECOVERY ATTEMPT PERSISTENCE: PASS")
    print("=" * 55)

    db.commit()

except Exception:
    db.rollback()
    raise

finally:
    db.close()