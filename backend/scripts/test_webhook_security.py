import hashlib
import hmac

from app.providers.mock_webhook_security import (
    MockWebhookSignatureVerifier,
)
from app.providers.webhook_security import WebhookSignatureError


verifier = MockWebhookSignatureVerifier()

payload = b'{"event":"payment.captured","payment_id":"pay_123"}'
secret = "test-webhook-secret"

signature = hmac.new(
    secret.encode("utf-8"),
    payload,
    hashlib.sha256,
).hexdigest()


# ---------------------------------------------------------
# VALID SIGNATURE
# ---------------------------------------------------------

assert verifier.verify(
    payload=payload,
    signature=signature,
    secret=secret,
) is True


# ---------------------------------------------------------
# TAMPERED PAYLOAD
# ---------------------------------------------------------

tampered_payload_failed = verifier.verify(
    payload=b'{"event":"payment.captured","payment_id":"pay_999"}',
    signature=signature,
    secret=secret,
)

assert tampered_payload_failed is False


# ---------------------------------------------------------
# WRONG SECRET
# ---------------------------------------------------------

wrong_secret_failed = verifier.verify(
    payload=payload,
    signature=signature,
    secret="wrong-secret",
)

assert wrong_secret_failed is False


# ---------------------------------------------------------
# EMPTY PAYLOAD
# ---------------------------------------------------------

empty_payload_failed = False

try:
    verifier.verify(
        payload=b"",
        signature=signature,
        secret=secret,
    )
except WebhookSignatureError:
    empty_payload_failed = True

assert empty_payload_failed is True


# ---------------------------------------------------------
# EMPTY SIGNATURE
# ---------------------------------------------------------

empty_signature_failed = False

try:
    verifier.verify(
        payload=payload,
        signature="",
        secret=secret,
    )
except WebhookSignatureError:
    empty_signature_failed = True

assert empty_signature_failed is True


# ---------------------------------------------------------
# EMPTY SECRET
# ---------------------------------------------------------

empty_secret_failed = False

try:
    verifier.verify(
        payload=payload,
        signature=signature,
        secret="",
    )
except WebhookSignatureError:
    empty_secret_failed = True

assert empty_secret_failed is True


print("=" * 55)
print("DAY 2.4.3 WEBHOOK SECURITY TEST PASSED")
print("=" * 55)
print("VALID SIGNATURE: PASS")
print("TAMPERED PAYLOAD: PASS")
print("WRONG SECRET: PASS")
print("EMPTY PAYLOAD: PASS")
print("EMPTY SIGNATURE: PASS")
print("EMPTY SECRET: PASS")
print("=" * 55)