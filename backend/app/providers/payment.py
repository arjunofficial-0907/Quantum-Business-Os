from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID


class PaymentProviderError(Exception):
    """Base exception for payment provider errors."""


class PaymentProvider(ABC):
    """Abstract interface for external payment providers."""

    @abstractmethod
    def create_payment(
        self,
        *,
        organization_id: UUID,
        invoice_id: UUID,
        amount: Decimal,
        currency: str,
    ) -> str:
        """
        Create a payment with the external provider.

        Returns:
            Provider payment identifier.
        """
        raise NotImplementedError

    @abstractmethod
    def capture_payment(
        self,
        *,
        provider_payment_id: str,
        amount: Decimal,
        currency: str,
    ) -> None:
        """Capture an authorized payment."""
        raise NotImplementedError

    @abstractmethod
    def refund_payment(
        self,
        *,
        provider_payment_id: str,
        amount: Decimal,
        currency: str,
    ) -> str:
        """
        Refund a captured payment.

        Returns:
            Provider refund identifier.
        """
        raise NotImplementedError