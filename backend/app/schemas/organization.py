from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrganizationCreateRequest(BaseModel):
    name: str
    legal_name: str | None = None


class OrganizationUpdateRequest(BaseModel):
    name: str | None = None
    legal_name: str | None = None


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    legal_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)