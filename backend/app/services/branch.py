from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import Branch, BranchStatus
from app.models.membership import (
    Membership,
    MembershipStatus,
    membership_branches,
)
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


def create_branch(
    db: Session,
    membership: Membership,
    organization_id: UUID,
    name: str,
    code: str,
    address_line_1: str | None = None,
    address_line_2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str = "India",
    timezone: str = "Asia/Kolkata",
) -> Branch:
    branch = Branch(
        organization_id=organization_id,
        name=name,
        code=code,
        address_line_1=address_line_1,
        address_line_2=address_line_2,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
        timezone=timezone,
        status=BranchStatus.ACTIVE,
    )

    db.add(branch)
    db.flush()

    db.execute(
        membership_branches.insert().values(
            membership_id=membership.id,
            branch_id=branch.id,
        )
    )

    db.commit()
    db.refresh(branch)

    return branch


def get_accessible_branches(
    db: Session,
    membership: Membership,
) -> list[Branch]:
    if membership.all_branches:
        statement = (
            select(Branch)
            .where(
                Branch.organization_id == membership.organization_id,
                Branch.status == BranchStatus.ACTIVE,
            )
            .order_by(Branch.created_at.desc())
        )

        return list(db.scalars(statement))

    statement = (
        select(Branch)
        .join(
            membership_branches,
            membership_branches.c.branch_id == Branch.id,
        )
        .where(
            membership_branches.c.membership_id == membership.id,
            Branch.organization_id == membership.organization_id,
            Branch.status == BranchStatus.ACTIVE,
        )
        .order_by(Branch.created_at.desc())
    )

    return list(db.scalars(statement))

def set_membership_branch_scope(
    db: Session,
    membership: Membership,
    organization_id: UUID,
    all_branches: bool,
    branch_ids: list[UUID],
) -> Membership:
    if membership.organization_id != organization_id:
        raise ValueError("Membership does not belong to this organization.")

    if membership.status != MembershipStatus.ACTIVE:
        raise ValueError("Membership is not active.")

    if all_branches:
        branch_ids = []

    else:
        if not branch_ids:
            raise ValueError(
                "At least one branch is required when all_branches is false."
            )

        branches = list(
            db.scalars(
                select(Branch).where(
                    Branch.id.in_(branch_ids),
                    Branch.organization_id == organization_id,
                    Branch.status == BranchStatus.ACTIVE,
                )
            )
        )

        found_branch_ids = {branch.id for branch in branches}
        requested_branch_ids = set(branch_ids)

        if found_branch_ids != requested_branch_ids:
            raise ValueError(
                "One or more branches do not belong to this organization "
                "or are not active."
            )

    db.execute(
        membership_branches.delete().where(
            membership_branches.c.membership_id == membership.id
        )
    )

    membership.all_branches = all_branches

    if not all_branches:
        for branch_id in branch_ids:
            db.execute(
                membership_branches.insert().values(
                    membership_id=membership.id,
                    branch_id=branch_id,
                )
            )

    db.commit()
    db.refresh(membership)

    return membership