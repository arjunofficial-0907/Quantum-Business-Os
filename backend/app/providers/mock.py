from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from app.providers.payment import PaymentProvider, PaymentProviderError
from app.providers.results import (
    PaymentCaptureResult,
    PaymentCreationResult,
    PaymentRefundResult,
)


class MockPaymentProvider(PaymentProvider):
    """In-memory payment provider for development and integration testing."""

    def create_payment(
        self,
        *,
        organization_id: UUID,
        invoice_id: UUID,
        amount: Decimal,
        currency: str,
    ) -> PaymentCreationResult:
        if amount <= 0:
            raise PaymentProviderError(
                "Payment amount must be greater than zero."
            )

        return PaymentCreationResult(
            provider_payment_id=f"mock_pay_{uuid4().hex}",
            status="created",
            amount=amount,
            currency=currency.upper(),
        )

    def capture_payment(
        self,
        *,
        provider_payment_id: str,
        amount: Decimal,
        currency: str,
    ) -> PaymentCaptureResult:
        if not provider_payment_id:
            raise PaymentProviderError(
                "Provider payment ID is required."
            )

        if amount <= 0:
            raise PaymentProviderError(
                "Capture amount must be greater than zero."
            )

        return PaymentCaptureResult(
            provider_payment_id=provider_payment_id,
            status="captured",
            amount=amount,
            currency=currency.upper(),
        )

    def refund_payment(
        self,
        *,
        provider_payment_id: str,
        amount: Decimal,
        currency: str,
    ) -> PaymentRefundResult:
        if not provider_payment_id:
            raise PaymentProviderError(
                "Provider payment ID is required."
            )

        if amount <= 0:
            raise PaymentProviderError(
                "Refund amount must be greater than zero."
            )

        return PaymentRefundResult(
            provider_payment_id=provider_payment_id,
            provider_refund_id=f"mock_ref_{uuid4().hex}",
            status="refunded",
            amount=amount,
            currency=currency.upper(),
        )