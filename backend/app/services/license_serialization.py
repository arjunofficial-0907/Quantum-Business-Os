import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.schemas.license import LicensePayload


def _json_default(value: Any) -> str:
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    raise TypeError(
        f"Unsupported JSON value type: {type(value).__name__}"
    )


def canonicalize_license_payload(
    payload: LicensePayload,
) -> bytes:
    data = payload.model_dump(mode="python")

    canonical_json = json.dumps(
        data,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return canonical_json.encode("utf-8")
