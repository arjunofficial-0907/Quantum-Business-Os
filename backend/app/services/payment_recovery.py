from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

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


def get_next_attempt_number(
    db: Session,
    *,
    payment_id: UUID,
    organization_id: UUID,
) -> int:
    """Return the next recovery attempt number for a payment."""

    max_attempt = (
        db.query(func.max(PaymentRecoveryAttempt.attempt_number))
        .filter(
            PaymentRecoveryAttempt.payment_id == payment_id,
            PaymentRecoveryAttempt.organization_id == organization_id,
        )
        .scalar()
    )

    return (max_attempt or 0) + 1


def create_recovery_attempt(
    db: Session,
    *,
    request: PaymentRecoveryRequest,
) -> PaymentRecoveryAttempt:
    """Create a new recovery attempt for a failed payment."""

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == request.payment_id,
            Payment.organization_id == request.organization_id,
        )
        .first()
    )

    if payment is None:
        raise PaymentRecoveryError(
            "Payment not found for organization."
        )

    if payment.status != PaymentStatus.FAILED:
        raise PaymentRecoveryNotAllowed(
            "Only failed payments can enter recovery."
        )

    if request.amount <= 0:
        raise PaymentRecoveryError(
            "Recovery amount must be greater than zero."
        )

    if request.amount > payment.amount:
        raise PaymentRecoveryError(
            "Recovery amount cannot exceed payment amount."
        )

    if request.currency.upper() != payment.currency.upper():
        raise PaymentRecoveryError(
            "Recovery currency does not match payment currency."
        )

    next_attempt = get_next_attempt_number(
        db,
        payment_id=payment.id,
        organization_id=payment.organization_id,
    )

    if request.attempt_number != next_attempt:
        raise PaymentRecoveryError(
            f"Invalid attempt number. Expected {next_attempt}."
        )

    attempt = PaymentRecoveryAttempt(
        organization_id=payment.organization_id,
        payment_id=payment.id,
        attempt_number=next_attempt,
        amount=request.amount,
        currency=request.currency.upper(),
        status=PaymentRecoveryAttemptStatus.PENDING,
    )

    db.add(attempt)
    db.flush()

    return attempt


def mark_recovery_processing(
    db: Session,
    *,
    attempt_id: UUID,
    organization_id: UUID,
) -> PaymentRecoveryAttempt:
    """Move a recovery attempt into processing state."""

    attempt = (
        db.query(PaymentRecoveryAttempt)
        .filter(
            PaymentRecoveryAttempt.id == attempt_id,
            PaymentRecoveryAttempt.organization_id == organization_id,
        )
        .first()
    )

    if attempt is None:
        raise PaymentRecoveryError(
            "Recovery attempt not found."
        )

    if attempt.status == PaymentRecoveryAttemptStatus.SUCCEEDED:
        return attempt

    if attempt.status == PaymentRecoveryAttemptStatus.FAILED:
        raise PaymentRecoveryError(
            "A failed recovery attempt cannot resume processing."
        )

    attempt.status = PaymentRecoveryAttemptStatus.PROCESSING

    db.flush()

    return attempt


def mark_recovery_succeeded(
    db: Session,
    *,
    attempt_id: UUID,
    organization_id: UUID,
    provider_payment_id: str | None = None,
) -> PaymentRecoveryAttempt:
    """Mark a recovery attempt successful and capture the payment."""

    attempt = (
        db.query(PaymentRecoveryAttempt)
        .filter(
            PaymentRecoveryAttempt.id == attempt_id,
            PaymentRecoveryAttempt.organization_id == organization_id,
        )
        .first()
    )

    if attempt is None:
        raise PaymentRecoveryError(
            "Recovery attempt not found."
        )

    if attempt.status == PaymentRecoveryAttemptStatus.SUCCEEDED:
        return attempt

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == attempt.payment_id,
            Payment.organization_id == organization_id,
        )
        .first()
    )

    if payment is None:
        raise PaymentRecoveryError(
            "Recovery payment not found."
        )

    if payment.status == PaymentStatus.CANCELLED:
        raise PaymentRecoveryNotAllowed(
            "Cancelled payment cannot be recovered."
        )

    processed_at = datetime.now(timezone.utc)

    attempt.status = PaymentRecoveryAttemptStatus.SUCCEEDED
    attempt.provider_payment_id = provider_payment_id
    attempt.processed_at = processed_at
    attempt.error_message = None

    payment.status = PaymentStatus.CAPTURED
    payment.captured_at = processed_at

    db.flush()

    return attempt


def mark_recovery_failed(
    db: Session,
    *,
    attempt_id: UUID,
    organization_id: UUID,
    error_message: str,
) -> PaymentRecoveryAttempt:
    """Mark a recovery attempt as failed."""

    if not error_message.strip():
        raise PaymentRecoveryError(
            "Recovery failure reason is required."
        )

    attempt = (
        db.query(PaymentRecoveryAttempt)
        .filter(
            PaymentRecoveryAttempt.id == attempt_id,
            PaymentRecoveryAttempt.organization_id == organization_id,
        )
        .first()
    )

    if attempt is None:
        raise PaymentRecoveryError(
            "Recovery attempt not found."
        )

    if attempt.status == PaymentRecoveryAttemptStatus.SUCCEEDED:
        raise PaymentRecoveryError(
            "A successful recovery attempt cannot be marked failed."
        )

    attempt.status = PaymentRecoveryAttemptStatus.FAILED
    attempt.error_message = error_message

    db.flush()

    return attempt