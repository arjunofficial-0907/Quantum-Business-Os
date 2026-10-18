from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


class WebhookEventType(str, enum.Enum):
    PAYMENT_CREATED = "payment.created"
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_CANCELLED = "payment.cancelled"
    PAYMENT_REFUNDED = "payment.refunded"


@dataclass(frozen=True)
class PaymentWebhookEvent:
    """
    Provider-neutral representation of a payment webhook event.
    """

    event_id: str
    event_type: WebhookEventType
    provider_payment_id: str
    organization_id: UUID
    invoice_id: UUID
    amount: Decimal
    currency: str
    raw_payload: dict