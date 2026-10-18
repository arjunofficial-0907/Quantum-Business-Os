import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Index,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SettingScope(str, enum.Enum):
    PLATFORM = "platform"
    ORGANIZATION = "organization"
    BRANCH = "branch"
    USER = "user"


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope: Mapped[SettingScope] = mapped_column(
        Enum(
            SettingScope,
            name="setting_scope",
            native_enum=False,
        ),
        nullable=False,
    )

    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    key: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON,
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

    __table_args__ = (
        Index(
            "ix_settings_scope_scope_id_key",
            "scope",
            "scope_id",
            "key",
        ),
    )
