from pydantic import BaseModel, ConfigDict, Field

from app.schemas.license import LicensePayload


class SignedLicense(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    format_version: int = Field(
        default=1,
        ge=1,
    )

    key_id: str = Field(
        min_length=1,
        max_length=100,
    )

    payload: LicensePayload

    signature: str = Field(
        min_length=1,
    )
