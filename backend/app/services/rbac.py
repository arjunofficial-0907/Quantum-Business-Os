from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership, MembershipStatus
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.user import User


def get_active_membership(
    db: Session,
    current_user: User,
    organization_id: UUID,
) -> Membership | None:
    statement = (
        select(Membership)
        .where(
            Membership.user_id == current_user.id,
            Membership.organization_id == organization_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    )

    return db.scalar(statement)

def has_permission(
    db: Session,
    current_user: User,
    organization_id: UUID,
    permission_code: str,
) -> bool:
    statement = (
        select(Permission.id)
        .join(
            role_permissions,
            role_permissions.c.permission_id == Permission.id,
        )
        .join(
            Role,
            Role.id == role_permissions.c.role_id,
        )
        .join(
            Membership,
            Membership.role_id == Role.id,
        )
        .where(
            Membership.user_id == current_user.id,
            Membership.organization_id == organization_id,
            Membership.status == MembershipStatus.ACTIVE,
            Role.organization_id == organization_id,
            Permission.code == permission_code,
        )
        .limit(1)
    )

    return db.scalar(statement) is not None

def assign_role_to_membership(
    db: Session,
    organization_id: UUID,
    membership_id: UUID,
    role_id: UUID,
) -> Membership | None:
    membership_statement = (
        select(Membership)
        .where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
        )
    )

    membership = db.scalar(membership_statement)

    if membership is None:
        return None

    role = get_role(
        db=db,
        organization_id=organization_id,
        role_id=role_id,
    )

    if role is None:
        return None

    membership.role_id = role.id

    db.commit()
    db.refresh(membership)

    return membership

def create_role(
    db: Session,
    organization_id: UUID,
    name: str,
    description: str | None = None,
) -> Role:
    role = Role(
        organization_id=organization_id,
        name=name,
        description=description,
        is_system=False,
    )

    db.add(role)
    db.commit()
    db.refresh(role)

    return role


def get_organization_roles(
    db: Session,
    organization_id: UUID,
) -> list[Role]:
    statement = (
        select(Role)
        .where(Role.organization_id == organization_id)
        .order_by(Role.created_at.desc())
    )

    return list(db.scalars(statement))


def get_role(
    db: Session,
    organization_id: UUID,
    role_id: UUID,
) -> Role | None:
    statement = (
        select(Role)
        .where(
            Role.id == role_id,
            Role.organization_id == organization_id,
        )
    )

    return db.scalar(statement)


def get_permissions(
    db: Session,
) -> list[Permission]:
    statement = (
        select(Permission)
        .order_by(Permission.code)
    )

    return list(db.scalars(statement))


def get_role_permissions(
    db: Session,
    role_id: UUID,
) -> list[Permission]:
    statement = (
        select(Permission)
        .join(
            role_permissions,
            role_permissions.c.permission_id == Permission.id,
        )
        .where(
            role_permissions.c.role_id == role_id,
        )
        .order_by(Permission.code)
    )

    return list(db.scalars(statement))


def assign_permissions_to_role(
    db: Session,
    role: Role,
    permission_ids: list[UUID],
) -> list[Permission]:
    permissions = list(
        db.scalars(
            select(Permission).where(
                Permission.id.in_(permission_ids)
            )
        )
    )

    existing_permission_ids = {
        row.permission_id
        for row in db.execute(
            select(role_permissions.c.permission_id).where(
                role_permissions.c.role_id == role.id
            )
        )
    }

    for permission in permissions:
        if permission.id not in existing_permission_ids:
            db.execute(
                role_permissions.insert().values(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )

    db.commit()

    return get_role_permissions(
        db=db,
        role_id=role.id,
    )
