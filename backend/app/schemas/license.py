from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LicensePayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    schema_version: int = Field(
        default=1,
        ge=1,
    )

    key_id: str = Field(
        min_length=1,
        max_length=100,
    )

    license_id: UUID
    organization_id: UUID
    device_id: UUID
    subscription_id: UUID

    activation_reference: str = Field(
        min_length=1,
        max_length=255,
    )

    device_type: str = Field(
        min_length=1,
        max_length=50,
    )

    issued_at: datetime
    expires_at: datetime
    offline_valid_until: datetime

    entitlements: dict[str, Any]
