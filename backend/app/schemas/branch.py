from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BranchCreateRequest(BaseModel):
    name: str
    code: str
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "India"
    timezone: str = "Asia/Kolkata"


class BranchResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    code: str
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str
    timezone: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)