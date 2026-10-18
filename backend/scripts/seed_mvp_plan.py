import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.entitlement_definition import EntitlementDefinition
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription_plan import BillingInterval, SubscriptionPlan


PLAN_CODE = "DEV_MVP"

ENTITLEMENTS = {
    "max_devices": 10,
    "offline_validity_days": 7,
    "windows_client": True,
    "android_client": True,
}


def seed_mvp_plan() -> None:
    db = SessionLocal()

    try:
        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.code == PLAN_CODE)
            .one_or_none()
        )

        if plan is None:
            plan = SubscriptionPlan(
                code=PLAN_CODE,
                name="Quantum MVP Development",
                description="Internal development plan for licensing MVP validation.",
                price=0,
                currency="INR",
                billing_interval=BillingInterval.MONTHLY,
                is_custom_pricing=False,
                is_active=True,
            )
            db.add(plan)
            db.flush()

        definitions = (
            db.query(EntitlementDefinition)
            .filter(
                EntitlementDefinition.code.in_(ENTITLEMENTS.keys())
            )
            .all()
        )

        definitions_by_code = {
            definition.code: definition
            for definition in definitions
        }

        missing = set(ENTITLEMENTS) - set(definitions_by_code)

        if missing:
            raise RuntimeError(
                f"Missing entitlement definitions: {sorted(missing)}"
            )

        for code, value in ENTITLEMENTS.items():
            existing = (
                db.query(PlanEntitlement)
                .filter(
                    PlanEntitlement.plan_id == plan.id,
                    PlanEntitlement.entitlement_id
                    == definitions_by_code[code].id,
                )
                .one_or_none()
            )

            if existing is None:
                db.add(
                    PlanEntitlement(
                        plan_id=plan.id,
                        entitlement_id=definitions_by_code[code].id,
                        enabled=True,
                        value=value,
                    )
                )
            else:
                existing.enabled = True
                existing.value = value

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_mvp_plan()
    print("MVP_PLAN_SEEDED")
