from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaymentCreationResult:
    provider_payment_id: str
    status: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class PaymentCaptureResult:
    provider_payment_id: str
    status: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class PaymentRefundResult:
    provider_payment_id: str
    provider_refund_id: str
    status: str
    amount: Decimal
    currency: str