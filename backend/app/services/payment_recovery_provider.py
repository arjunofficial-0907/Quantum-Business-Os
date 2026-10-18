from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.services.payment_recovery import (
    create_recovery_attempt,
    mark_recovery_failed,
    mark_recovery_processing,
    mark_recovery_succeeded,
)
from app.services.payment_recovery_contract import (
    PaymentRecoveryError,
    PaymentRecoveryRequest,
)
from app.services.payment_recovery_policy import (
    PaymentRecoveryPolicy,
    check_recovery_eligibility,
)
from app.providers.payment import PaymentProvider, PaymentProviderError


def recover_payment_with_provider(
    db: Session,
    *,
    payment_id: UUID,
    organization_id: UUID,
    payment_provider: PaymentProvider,
) -> Payment:
    """
    Execute a failed payment recovery through the configured payment provider.

    Flow:
        FAILED payment
            -> recovery attempt
            -> provider create payment
            -> provider capture
            -> recovery succeeded
            -> payment captured
            -> invoice paid
    """

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.organization_id == organization_id,
        )
        .first()
    )

    if payment is None:
        raise PaymentRecoveryError(
            "Payment not found for organization."
        )

    if payment.status != PaymentStatus.FAILED:
        raise PaymentRecoveryError(
            "Only failed payments can enter provider recovery."
        )

    eligibility = check_recovery_eligibility(
        db,
        payment_id=payment_id,
        organization_id=organization_id,
        policy=PaymentRecoveryPolicy(),
    )

    if not eligibility.allowed:
        raise PaymentRecoveryError(
            eligibility.reason or "Payment recovery is not allowed."
        )

    attempt_number = eligibility.next_attempt_number

    request = PaymentRecoveryRequest(
        payment_id=payment_id,
        organization_id=organization_id,
        amount=Decimal(payment.amount),
        currency=payment.currency,
        attempt_number=attempt_number,
    )

    attempt = create_recovery_attempt(
        db,
        request=request,
    )

    mark_recovery_processing(
        db,
        attempt_id=attempt.id,
        organization_id=organization_id,
    )

    try:
        creation_result = payment_provider.create_payment(
            organization_id=organization_id,
            invoice_id=payment.invoice_id,
            amount=Decimal(payment.amount),
            currency=payment.currency,
        )

        provider_payment_id = creation_result.provider_payment_id

        payment.provider_payment_id = provider_payment_id
        db.flush()

        capture_result = payment_provider.capture_payment(
            provider_payment_id=provider_payment_id,
            amount=Decimal(payment.amount),
            currency=payment.currency,
        )

        mark_recovery_succeeded(
            db,
            attempt_id=attempt.id,
            organization_id=organization_id,
            provider_payment_id=capture_result.provider_payment_id,
        )

        invoice = (
            db.query(Invoice)
            .filter(
                Invoice.id == payment.invoice_id,
                Invoice.organization_id == organization_id,
            )
            .first()
        )

        if invoice is None:
            raise PaymentRecoveryError(
                "Invoice not found for recovered payment."
            )

        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = payment.captured_at

        db.flush()

        return payment

    except PaymentProviderError as exc:
        mark_recovery_failed(
            db,
            attempt_id=attempt.id,
            organization_id=organization_id,
            error_message=str(exc),
        )

        raise PaymentRecoveryError(
            f"Payment provider recovery failed: {exc}"
        ) from exc