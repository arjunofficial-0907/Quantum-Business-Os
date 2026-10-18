from app.core.authorization.permissions import PermissionCode
from app.db.session import SessionLocal
from app.models.permission import Permission


PERMISSIONS = [
    {
        "code": PermissionCode.ORGANIZATION_READ,
        "name": "Organization Read",
        "description": "View organization information.",
    },
    {
        "code": PermissionCode.ORGANIZATION_MANAGE,
        "name": "Organization Manage",
        "description": "Create and manage organization information.",
    },
    {
        "code": PermissionCode.BRANCH_READ,
        "name": "Branch Read",
        "description": "View organization branches.",
    },
    {
        "code": PermissionCode.BRANCH_MANAGE,
        "name": "Branch Manage",
        "description": "Create and manage organization branches.",
    },
        {
        "code": PermissionCode.MEMBERSHIP_MANAGE,
        "name": "Membership Manage",
        "description": "Manage organization memberships, roles, and branch scope.",
    },
        {
        "code": PermissionCode.LICENSE_ACTIVATE,
        "name": "License Activate",
        "description": "Activate licensed devices.",
    },
    {
        "code": PermissionCode.BILLING_RECORD_CREATE,
        "name": "Billing Record Create",
        "description": "Create billing records.",
    },
    {
        "code": PermissionCode.BILLING_RECORD_READ,
        "name": "Billing Record Read",
        "description": "View billing records.",
    },
    {
        "code": PermissionCode.BILLING_INVOICE_CREATE,
        "name": "Billing Invoice Create",
        "description": "Create invoices.",
    },
    {
        "code": PermissionCode.BILLING_INVOICE_READ,
        "name": "Billing Invoice Read",
        "description": "View invoices.",
    },
    {
        "code": PermissionCode.BILLING_PAYMENT_CREATE,
        "name": "Billing Payment Create",
        "description": "Create payments.",
    },
    {
        "code": PermissionCode.BILLING_PAYMENT_READ,
        "name": "Billing Payment Read",
        "description": "View payments.",
    },
    {
        "code": PermissionCode.BILLING_PAYMENT_UPDATE,
        "name": "Billing Payment Update",
        "description": "Update payment status.",
    },
]


def seed_permissions() -> None:
    db = SessionLocal()

    try:
        created = 0
        existing = 0

        for permission_data in PERMISSIONS:
            permission = (
                db.query(Permission)
                .filter(
                    Permission.code == permission_data["code"]
                )
                .first()
            )

            if permission is not None:
                existing += 1
                continue

            db.add(
                Permission(**permission_data)
            )
            created += 1

        db.commit()

        print(f"Permissions created: {created}")
        print(f"Permissions already existing: {existing}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_permissions()
