import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


membership_branches = Table(
    "membership_branches",
    Base.metadata,
    Column(
        "membership_id",
        Uuid(as_uuid=True),
        ForeignKey("memberships.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "branch_id",
        Uuid(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class MembershipStatus(str, enum.Enum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class Membership(Base):
    __tablename__ = "memberships"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_memberships_user_organization",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    all_branches: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    status: Mapped[MembershipStatus] = mapped_column(
        Enum(
            MembershipStatus,
            name="membership_status",
            native_enum=False,
        ),
        nullable=False,
        default=MembershipStatus.INVITED,
    )

    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
