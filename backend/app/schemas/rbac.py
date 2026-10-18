from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    name: str
    description: str | None = None


class RoleResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionAssignRequest(BaseModel):
    permission_ids: list[UUID]


class MembershipRoleAssignRequest(BaseModel):
    role_id: UUID


class MembershipRoleAssignResponse(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role_id: UUID | None
    all_branches: bool
    status: str
    joined_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipBranchScopeRequest(BaseModel):
    all_branches: bool = False
    branch_ids: list[UUID] = []


class MembershipBranchScopeResponse(BaseModel):
    membership_id: UUID
    organization_id: UUID
    all_branches: bool
    branch_ids: list[UUID]

    model_config = ConfigDict(from_attributes=True)

class MembershipInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    
class MembershipResponse(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role_id: UUID | None
    all_branches: bool
    status: str
    joined_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)