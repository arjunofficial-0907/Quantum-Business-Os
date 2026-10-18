from __future__ import annotations

from abc import ABC, abstractmethod


class WebhookSignatureError(Exception):
    """Raised when webhook signature verification fails."""


class WebhookSignatureVerifier(ABC):
    """Abstract interface for webhook signature verification."""

    @abstractmethod
    def verify(
        self,
        *,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify the authenticity of a webhook payload.

        Returns:
            True when the signature is valid.
        """
        raise NotImplementedError