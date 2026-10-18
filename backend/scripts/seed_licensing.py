import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.entitlement_definition import (
    EntitlementDefinition,
    EntitlementValueType,
)


ENTITLEMENTS = [
    {
        "code": "max_devices",
        "name": "Maximum Devices",
        "description": "Maximum number of licensed devices allowed for the subscription.",
        "value_type": EntitlementValueType.INTEGER,
    },
    {
        "code": "offline_validity_days",
        "name": "Offline Validity Days",
        "description": "Number of days a signed client license may remain valid without online revalidation.",
        "value_type": EntitlementValueType.INTEGER,
    },
    {
        "code": "windows_client",
        "name": "Windows Client",
        "description": "Whether the Windows client is enabled for the subscription.",
        "value_type": EntitlementValueType.BOOLEAN,
    },
    {
        "code": "android_client",
        "name": "Android Client",
        "description": "Whether the Android client is enabled for the subscription.",
        "value_type": EntitlementValueType.BOOLEAN,
    },
]


def seed_entitlements() -> None:
    db = SessionLocal()

    try:
        for data in ENTITLEMENTS:
            existing = (
                db.query(EntitlementDefinition)
                .filter(
                    EntitlementDefinition.code == data["code"]
                )
                .one_or_none()
            )

            if existing is None:
                db.add(EntitlementDefinition(**data))
            else:
                existing.name = data["name"]
                existing.description = data["description"]
                existing.value_type = data["value_type"]
                existing.is_active = True

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_entitlements()
    print("LICENSING_ENTITLEMENTS_SEEDED")
