from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.services.payment_recovery import get_next_attempt_number
from app.services.payment_recovery_contract import (
    PaymentRecoveryError,
)


DEFAULT_MAX_RECOVERY_ATTEMPTS = 3


@dataclass(frozen=True)
class PaymentRecoveryPolicy:
    max_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS

    def validate(self) -> None:
        if self.max_attempts <= 0:
            raise PaymentRecoveryError(
                "Maximum recovery attempts must be greater than zero."
            )


@dataclass(frozen=True)
class PaymentRecoveryEligibility:
    allowed: bool
    reason: str | None
    next_attempt_number: int


def check_recovery_eligibility(
    db: Session,
    *,
    payment_id: UUID,
    organization_id: UUID,
    policy: PaymentRecoveryPolicy | None = None,
) -> PaymentRecoveryEligibility:
    policy = policy or PaymentRecoveryPolicy()
    policy.validate()

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

    next_attempt_number = get_next_attempt_number(
        db,
        payment_id=payment_id,
        organization_id=organization_id,
    )

    if payment.status != PaymentStatus.FAILED:
        return PaymentRecoveryEligibility(
            allowed=False,
            reason="Only failed payments are eligible for recovery.",
            next_attempt_number=next_attempt_number,
        )

    if next_attempt_number > policy.max_attempts:
        return PaymentRecoveryEligibility(
            allowed=False,
            reason="Maximum recovery attempts reached.",
            next_attempt_number=next_attempt_number,
        )

    return PaymentRecoveryEligibility(
        allowed=True,
        reason=None,
        next_attempt_number=next_attempt_number,
    )


def validate_recovery_amount(
    *,
    payment_amount: Decimal,
    recovery_amount: Decimal,
) -> None:
    if recovery_amount <= 0:
        raise PaymentRecoveryError(
            "Recovery amount must be greater than zero."
        )

    if recovery_amount > payment_amount:
        raise PaymentRecoveryError(
            "Recovery amount cannot exceed payment amount."
        )


def validate_recovery_currency(
    *,
    payment_currency: str,
    recovery_currency: str,
) -> None:
    if payment_currency.upper() != recovery_currency.upper():
        raise PaymentRecoveryError(
            "Recovery currency does not match payment currency."
        )