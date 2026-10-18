from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership, MembershipStatus
from app.models.user import User


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    statement = (
        select(User)
        .where(
            User.email == email.lower().strip(),
        )
    )

    return db.scalar(statement)


def get_organization_memberships(
    db: Session,
    organization_id: UUID,
) -> list[Membership]:
    statement = (
        select(Membership)
        .where(
            Membership.organization_id == organization_id,
        )
        .order_by(Membership.created_at.desc())
    )

    return list(db.scalars(statement))


def get_membership_by_id(
    db: Session,
    organization_id: UUID,
    membership_id: UUID,
) -> Membership | None:
    statement = (
        select(Membership)
        .where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
        )
    )

    return db.scalar(statement)

def get_membership_for_user(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
) -> Membership | None:
    statement = (
        select(Membership)
        .where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    )

    return db.scalar(statement)


def create_invited_membership(
    db: Session,
    user: User,
    organization_id: UUID,
) -> Membership:
    membership = Membership(
        user_id=user.id,
        organization_id=organization_id,
        status=MembershipStatus.INVITED,
        role_id=None,
        all_branches=False,
    )

    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership


def accept_membership(
    db: Session,
    membership: Membership,
) -> Membership:
    if membership.status != MembershipStatus.INVITED:
        raise ValueError(
            "Membership is not awaiting acceptance."
        )

    membership.status = MembershipStatus.ACTIVE
    membership.joined_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(membership)

    return membership