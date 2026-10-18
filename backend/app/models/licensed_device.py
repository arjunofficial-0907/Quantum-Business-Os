import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Uuid,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LicensedDeviceType(str, enum.Enum):
    WINDOWS = "windows"
    ANDROID = "android"


class LicensedDeviceStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class LicensedDevice(Base):
    __tablename__ = "licensed_devices"

    __table_args__ = (
        UniqueConstraint(
            "device_identifier",
            name="uq_licensed_devices_device_identifier",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "branches.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    device_type: Mapped[LicensedDeviceType] = mapped_column(
        Enum(
            LicensedDeviceType,
            name="licensed_device_type",
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )

    device_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    device_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[LicensedDeviceStatus] = mapped_column(
        Enum(
            LicensedDeviceStatus,
            name="licensed_device_status",
            native_enum=False,
        ),
        nullable=False,
        default=LicensedDeviceStatus.PENDING,
        index=True,
    )

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
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
