import base64

from app.schemas.license import LicensePayload
from app.schemas.signed_license import SignedLicense
from app.services.license_keys import (
    load_license_private_key,
    load_license_public_key,
)
from app.services.license_signing import (
    sign_license_payload,
    verify_license_signature,
)


def create_signed_license(
    payload: LicensePayload,
) -> SignedLicense:
    private_key = load_license_private_key()

    signature = sign_license_payload(
        payload,
        private_key,
    )

    return SignedLicense(
        format_version=1,
        key_id=payload.key_id,
        payload=payload,
        signature=base64.b64encode(signature).decode("ascii"),
    )


def verify_signed_license(
    license: SignedLicense,
) -> bool:
    if license.key_id != license.payload.key_id:
        return False

    public_key = load_license_public_key()

    try:
        signature = base64.b64decode(
            license.signature,
            validate=True,
        )
    except ValueError:
        return False

    return verify_license_signature(
        license.payload,
        signature,
        public_key,
    )
