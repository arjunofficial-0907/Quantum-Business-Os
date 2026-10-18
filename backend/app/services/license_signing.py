from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.schemas.license import LicensePayload
from app.services.license_serialization import canonicalize_license_payload


def sign_license_payload(
    payload: LicensePayload,
    private_key: Ed25519PrivateKey,
) -> bytes:
    canonical_bytes = canonicalize_license_payload(payload)

    return private_key.sign(canonical_bytes)


def verify_license_signature(
    payload: LicensePayload,
    signature: bytes,
    public_key: Ed25519PublicKey,
) -> bool:
    canonical_bytes = canonicalize_license_payload(payload)

    try:
        public_key.verify(
            signature,
            canonical_bytes,
        )
    except InvalidSignature:
        return False

    return True
