from decimal import Decimal
from uuid import uuid4

from app.providers.mock import MockPaymentProvider
from app.providers.payment import PaymentProviderError


provider = MockPaymentProvider()

organization_id = uuid4()
invoice_id = uuid4()

try:
    # ---------------------------------------------------------
    # CREATE PAYMENT
    # ---------------------------------------------------------
    creation = provider.create_payment(
        organization_id=organization_id,
        invoice_id=invoice_id,
        amount=Decimal("1000.00"),
        currency="INR",
    )

    assert creation.provider_payment_id.startswith("mock_pay_")
    assert creation.status == "created"
    assert creation.amount == Decimal("1000.00")
    assert creation.currency == "INR"

    # ---------------------------------------------------------
    # CAPTURE PAYMENT
    # ---------------------------------------------------------
    capture = provider.capture_payment(
        provider_payment_id=creation.provider_payment_id,
        amount=Decimal("1000.00"),
        currency="INR",
    )

    assert capture.provider_payment_id == creation.provider_payment_id
    assert capture.status == "captured"
    assert capture.amount == Decimal("1000.00")
    assert capture.currency == "INR"

    # ---------------------------------------------------------
    # REFUND PAYMENT
    # ---------------------------------------------------------
    refund = provider.refund_payment(
        provider_payment_id=creation.provider_payment_id,
        amount=Decimal("500.00"),
        currency="INR",
    )

    assert refund.provider_payment_id == creation.provider_payment_id
    assert refund.provider_refund_id.startswith("mock_ref_")
    assert refund.status == "refunded"
    assert refund.amount == Decimal("500.00")
    assert refund.currency == "INR"

    # ---------------------------------------------------------
    # INVALID CREATE AMOUNT
    # ---------------------------------------------------------
    invalid_create_failed = False

    try:
        provider.create_payment(
            organization_id=organization_id,
            invoice_id=invoice_id,
            amount=Decimal("0.00"),
            currency="INR",
        )
    except PaymentProviderError:
        invalid_create_failed = True

    assert invalid_create_failed is True

    # ---------------------------------------------------------
    # INVALID CAPTURE
    # ---------------------------------------------------------
    invalid_capture_failed = False

    try:
        provider.capture_payment(
            provider_payment_id="",
            amount=Decimal("1000.00"),
            currency="INR",
        )
    except PaymentProviderError:
        invalid_capture_failed = True

    assert invalid_capture_failed is True

    # ---------------------------------------------------------
    # INVALID REFUND
    # ---------------------------------------------------------
    invalid_refund_failed = False

    try:
        provider.refund_payment(
            provider_payment_id=creation.provider_payment_id,
            amount=Decimal("0.00"),
            currency="INR",
        )
    except PaymentProviderError:
        invalid_refund_failed = True

    assert invalid_refund_failed is True

    print("=" * 55)
    print("DAY 2.3.4 PAYMENT PROVIDER TEST PASSED")
    print("=" * 55)
    print("CREATE PAYMENT: PASS")
    print("CAPTURE PAYMENT: PASS")
    print("REFUND PAYMENT: PASS")
    print("INVALID CREATE: PASS")
    print("INVALID CAPTURE: PASS")
    print("INVALID REFUND: PASS")
    print("=" * 55)

except Exception:
    raise