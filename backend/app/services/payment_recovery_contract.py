from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


class PaymentRecoveryStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PaymentRecoveryError(Exception):
    """Base exception for payment recovery errors."""


class PaymentRecoveryNotAllowed(PaymentRecoveryError):
    """Raised when a payment cannot be retried."""


@dataclass(frozen=True)
class PaymentRecoveryRequest:
    payment_id: UUID
    organization_id: UUID
    amount: Decimal
    currency: str
    attempt_number: int


@dataclass(frozen=True)
class PaymentRecoveryResult:
    payment_id: UUID
    status: PaymentRecoveryStatus
    attempt_number: int
    provider_payment_id: str | None = None
    error_message: str | None = None