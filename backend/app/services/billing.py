from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.billing import BillingRecord, BillingRecordStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription
from app.providers.payment import PaymentProvider, PaymentProviderError


class BillingServiceError(Exception):
    """Base exception for billing service errors."""


class BillingRecordError(BillingServiceError):
    """Raised when a billing record operation is invalid."""


class InvoiceError(BillingServiceError):
    """Raised when an invoice operation is invalid."""


class PaymentError(BillingServiceError):
    """Raised when a payment operation is invalid."""


def create_billing_record(
    db: Session,
    *,
    organization_id: UUID,
    subscription_id: UUID,
    amount: Decimal,
    currency: str,
    billing_period_start: datetime,
    billing_period_end: datetime,
    provider: str | None = None,
    provider_reference: str | None = None,
) -> BillingRecord:
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.organization_id == organization_id,
        )
        .first()
    )

    if subscription is None:
        raise BillingRecordError("Subscription not found for organization.")

    if billing_period_end <= billing_period_start:
        raise BillingRecordError(
            "Billing period end must be after billing period start."
        )

    if amount < 0:
        raise BillingRecordError("Billing amount cannot be negative.")

    record = BillingRecord(
        organization_id=organization_id,
        subscription_id=subscription_id,
        amount=amount,
        currency=currency.upper(),
        status=BillingRecordStatus.PENDING,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        provider=provider,
        provider_reference=provider_reference,
    )

    db.add(record)
    db.flush()

    return record


def create_invoice(
    db: Session,
    *,
    organization_id: UUID,
    subscription_id: UUID,
    invoice_number: str,
    amount: Decimal,
    currency: str,
    issued_at: datetime | None = None,
    due_at: datetime | None = None,
) -> Invoice:
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.organization_id == organization_id,
        )
        .first()
    )

    if subscription is None:
        raise InvoiceError("Subscription not found for organization.")

    if amount < 0:
        raise InvoiceError("Invoice amount cannot be negative.")

    if due_at is not None and issued_at is not None and due_at < issued_at:
        raise InvoiceError("Invoice due date cannot precede issue date.")

    invoice = Invoice(
        organization_id=organization_id,
        subscription_id=subscription_id,
        invoice_number=invoice_number,
        subtotal=amount,
        tax_amount=Decimal("0.00"),
        total_amount=amount,
        currency=currency.upper(),
        status=InvoiceStatus.OPEN if issued_at else InvoiceStatus.DRAFT,
        issued_at=issued_at,
        due_at=due_at,
    )

    db.add(invoice)
    db.flush()

    return invoice


def create_payment(
    db: Session,
    *,
    organization_id: UUID,
    invoice_id: UUID,
    amount: Decimal,
    currency: str,
    method: str | None = None,
    provider: str | None = None,
    provider_payment_id: str | None = None,
    payment_provider: PaymentProvider | None = None,
) -> Payment:
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.organization_id == organization_id,
        )
        .first()
    )

    if invoice is None:
        raise PaymentError("Invoice not found for organization.")

    if amount <= 0:
        raise PaymentError("Payment amount must be greater than zero.")

    if amount > invoice.total_amount:
        raise PaymentError("Payment amount cannot exceed invoice amount.")

    if payment_provider is not None:
        try:
            result = payment_provider.create_payment(
                organization_id=organization_id,
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
            )
        except PaymentProviderError as exc:
            raise PaymentError(str(exc)) from exc

        provider_payment_id = result.provider_payment_id

    payment = Payment(
        organization_id=organization_id,
        invoice_id=invoice_id,
        amount=amount,
        currency=currency.upper(),
        method=method,
        status=PaymentStatus.PENDING,
        provider=provider,
        provider_payment_id=provider_payment_id,
    )

    db.add(payment)
    db.flush()

    return payment


def mark_payment_paid(
    db: Session,
    *,
    payment_id: UUID,
    organization_id: UUID,
    paid_at: datetime,
    payment_provider: PaymentProvider | None = None,
) -> Payment:
    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.organization_id == organization_id,
        )
        .first()
    )

    if payment is None:
        raise PaymentError("Payment not found for organization.")

    # Only pending payments can be marked as paid through
    # the normal billing flow.
    if payment.status != PaymentStatus.PENDING:
        raise PaymentError(
            f"Payment cannot be marked paid from status "
            f"'{payment.status.value}'."
        )

    if payment_provider is not None:
        if not payment.provider_payment_id:
            raise PaymentError(
                "Provider payment ID is required for capture."
            )

        try:
            payment_provider.capture_payment(
                provider_payment_id=payment.provider_payment_id,
                amount=payment.amount,
                currency=payment.currency,
            )
        except PaymentProviderError as exc:
            raise PaymentError(str(exc)) from exc

    payment.status = PaymentStatus.CAPTURED
    payment.captured_at = paid_at

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == payment.invoice_id,
            Invoice.organization_id == organization_id,
        )
        .first()
    )

    if invoice is None:
        raise PaymentError("Payment invoice not found.")

    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = paid_at

    db.flush()

    return payment


def mark_payment_failed(
    db: Session,
    *,
    payment_id: UUID,
    organization_id: UUID,
) -> Payment:
    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.organization_id == organization_id,
        )
        .first()
    )

    if payment is None:
        raise PaymentError("Payment not found for organization.")

    # Only pending payments can be marked as failed through
    # the normal billing flow.
    if payment.status != PaymentStatus.PENDING:
        raise PaymentError(
            f"Payment cannot be marked failed from status "
            f"'{payment.status.value}'."
        )

    payment.status = PaymentStatus.FAILED

    db.flush()

    return payment