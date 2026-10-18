from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.core.config import get_settings


def _resolve_key_path(configured_path: str) -> Path:
    if not configured_path.strip():
        raise RuntimeError("LICENSE_KEY_PATH_NOT_CONFIGURED")

    settings = get_settings()

    path = Path(configured_path)

    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1].parent / path

    return path.resolve()


def load_license_private_key() -> Ed25519PrivateKey:
    settings = get_settings()

    path = _resolve_key_path(
        settings.license_private_key_path
    )

    if not path.is_file():
        raise RuntimeError(
            "LICENSE_PRIVATE_KEY_FILE_NOT_FOUND"
        )

    key_data = path.read_bytes()

    try:
        key = serialization.load_pem_private_key(
            key_data,
            password=None,
        )
    except Exception as exc:
        raise RuntimeError(
            "LICENSE_PRIVATE_KEY_INVALID"
        ) from exc

    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError(
            "LICENSE_PRIVATE_KEY_WRONG_TYPE"
        )

    return key


def load_license_public_key() -> Ed25519PublicKey:
    settings = get_settings()

    path = _resolve_key_path(
        settings.license_public_key_path
    )

    if not path.is_file():
        raise RuntimeError(
            "LICENSE_PUBLIC_KEY_FILE_NOT_FOUND"
        )

    key_data = path.read_bytes()

    try:
        key = serialization.load_pem_public_key(
            key_data,
        )
    except Exception as exc:
        raise RuntimeError(
            "LICENSE_PUBLIC_KEY_INVALID"
        ) from exc

    if not isinstance(key, Ed25519PublicKey):
        raise RuntimeError(
            "LICENSE_PUBLIC_KEY_WRONG_TYPE"
        )

    return key
