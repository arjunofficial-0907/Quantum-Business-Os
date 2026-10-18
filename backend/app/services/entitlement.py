from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entitlement_definition import (
    EntitlementDefinition,
    EntitlementValueType,
)
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription, SubscriptionStatus


@dataclass(frozen=True)
class EffectiveEntitlement:
    code: str
    value_type: EntitlementValueType
    enabled: bool
    value: object | None


def get_active_subscription(
    db: Session,
    organization_id: UUID,
) -> Subscription | None:
    now = datetime.now(timezone.utc)

    statement = (
        select(Subscription)
        .where(
            Subscription.organization_id == organization_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.current_period_start <= now,
            Subscription.current_period_end > now,
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )

    return db.scalar(statement)


def get_plan_entitlements(
    db: Session,
    plan_id: UUID,
) -> list[PlanEntitlement]:
    statement = (
        select(PlanEntitlement)
        .where(
            PlanEntitlement.plan_id == plan_id,
        )
        .order_by(PlanEntitlement.created_at.asc())
    )

    return list(db.scalars(statement))


def get_subscription_entitlements(
    db: Session,
    organization_id: UUID,
) -> list[PlanEntitlement]:
    subscription = get_active_subscription(
        db=db,
        organization_id=organization_id,
    )

    if subscription is None:
        return []

    return get_plan_entitlements(
        db=db,
        plan_id=subscription.plan_id,
    )


def get_entitlement_definition(
    db: Session,
    entitlement_id: UUID,
) -> EntitlementDefinition | None:
    return db.get(
        EntitlementDefinition,
        entitlement_id,
    )


def get_entitlement_by_code(
    db: Session,
    code: str,
) -> EntitlementDefinition | None:
    statement = (
        select(EntitlementDefinition)
        .where(
            EntitlementDefinition.code == code,
            EntitlementDefinition.is_active.is_(True),
        )
    )

    return db.scalar(statement)


def get_subscription_entitlement(
    db: Session,
    organization_id: UUID,
    entitlement_code: str,
) -> PlanEntitlement | None:
    subscription = get_active_subscription(
        db=db,
        organization_id=organization_id,
    )

    if subscription is None:
        return None

    statement = (
        select(PlanEntitlement)
        .join(
            EntitlementDefinition,
            EntitlementDefinition.id == PlanEntitlement.entitlement_id,
        )
        .where(
            PlanEntitlement.plan_id == subscription.plan_id,
            EntitlementDefinition.code == entitlement_code,
            EntitlementDefinition.is_active.is_(True),
            PlanEntitlement.enabled.is_(True),
        )
        .limit(1)
    )

    return db.scalar(statement)


def has_entitlement(
    db: Session,
    organization_id: UUID,
    entitlement_code: str,
) -> bool:
    return (
        get_subscription_entitlement(
            db=db,
            organization_id=organization_id,
            entitlement_code=entitlement_code,
        )
        is not None
    )


def _validate_entitlement_value(
    definition: EntitlementDefinition,
    value: object | None,
) -> object | None:
    if value is None:
        return None

    value_type = definition.value_type

    if value_type == EntitlementValueType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError(
                f"Entitlement '{definition.code}' requires a boolean value."
            )
        return value

    if value_type == EntitlementValueType.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"Entitlement '{definition.code}' requires an integer value."
            )
        return value

    if value_type == EntitlementValueType.DECIMAL:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(
                f"Entitlement '{definition.code}' requires a decimal value."
            )
        return Decimal(str(value))

    if value_type == EntitlementValueType.STRING:
        if not isinstance(value, str):
            raise ValueError(
                f"Entitlement '{definition.code}' requires a string value."
            )
        return value

    if value_type == EntitlementValueType.JSON:
        return value

    raise ValueError(
        f"Unsupported entitlement value type: {value_type}"
    )


def resolve_effective_entitlements(
    db: Session,
    organization_id: UUID,
) -> dict[str, EffectiveEntitlement]:
    subscription = get_active_subscription(
        db=db,
        organization_id=organization_id,
    )

    if subscription is None:
        return {}

    statement = (
        select(
            EntitlementDefinition,
            PlanEntitlement,
        )
        .join(
            PlanEntitlement,
            PlanEntitlement.entitlement_id == EntitlementDefinition.id,
        )
        .where(
            PlanEntitlement.plan_id == subscription.plan_id,
            EntitlementDefinition.is_active.is_(True),
        )
        .order_by(EntitlementDefinition.code.asc())
    )

    results = db.execute(statement).all()

    resolved: dict[str, EffectiveEntitlement] = {}

    for definition, plan_entitlement in results:
        enabled = plan_entitlement.enabled

        value = (
            _validate_entitlement_value(
                definition,
                plan_entitlement.value,
            )
            if enabled
            else None
        )

        resolved[definition.code] = EffectiveEntitlement(
            code=definition.code,
            value_type=definition.value_type,
            enabled=enabled,
            value=value,
        )

    return resolved


def get_entitlement_value(
    db: Session,
    organization_id: UUID,
    entitlement_code: str,
) -> object | None:
    entitlement = resolve_effective_entitlements(
        db=db,
        organization_id=organization_id,
    ).get(entitlement_code)

    if entitlement is None or not entitlement.enabled:
        return None

    return entitlement.value
