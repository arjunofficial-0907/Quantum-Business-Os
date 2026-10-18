from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership, MembershipStatus
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User


def create_organization(
    db: Session,
    current_user: User,
    name: str,
    legal_name: str | None = None,
) -> Organization:
    organization = Organization(
        name=name,
        legal_name=legal_name,
        status=OrganizationStatus.ACTIVE,
    )

    db.add(organization)
    db.flush()

    membership = Membership(
        user_id=current_user.id,
        organization_id=organization.id,
        status=MembershipStatus.ACTIVE,
    )

    db.add(membership)
    db.commit()
    db.refresh(organization)

    return organization


def get_user_organizations(
    db: Session,
    current_user: User,
) -> list[Organization]:
    statement = (
        select(Organization)
        .join(
            Membership,
            Membership.organization_id == Organization.id,
        )
        .where(
            Membership.user_id == current_user.id,
            Membership.status == MembershipStatus.ACTIVE,
            Organization.status == OrganizationStatus.ACTIVE,
        )
        .order_by(Organization.created_at.desc())
    )

    return list(db.scalars(statement))

def get_organization(
    db: Session,
    organization_id,
) -> Organization | None:
    statement = (
        select(Organization)
        .where(
            Organization.id == organization_id,
            Organization.status == OrganizationStatus.ACTIVE,
        )
    )

    return db.scalar(statement)

def update_organization(
    db: Session,
    organization: Organization,
    name: str | None = None,
    legal_name: str | None = None,
) -> Organization:
    if name is not None:
        organization.name = name

    if legal_name is not None:
        organization.legal_name = legal_name

    db.commit()
    db.refresh(organization)

    return organization