from __future__ import annotations

import hashlib
import hmac

from app.providers.webhook_security import (
    WebhookSignatureError,
    WebhookSignatureVerifier,
)


class MockWebhookSignatureVerifier(WebhookSignatureVerifier):
    """HMAC-SHA256 webhook verifier for development and testing."""

    def verify(
        self,
        *,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        if not payload:
            raise WebhookSignatureError(
                "Webhook payload cannot be empty."
            )

        if not signature:
            raise WebhookSignatureError(
                "Webhook signature is required."
            )

        if not secret:
            raise WebhookSignatureError(
                "Webhook secret is required."
            )

        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(
            expected_signature,
            signature,
        )