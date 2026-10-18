from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.branch import Branch, BranchStatus
from app.models.device_activation import (
    DeviceActivation,
    DeviceActivationStatus,
)
from app.models.licensed_device import (
    LicensedDevice,
    LicensedDeviceStatus,
    LicensedDeviceType,
)
from app.models.organization import Organization, OrganizationStatus
from app.models.subscription import Subscription
from app.services.entitlement import (
    get_active_subscription,
    get_entitlement_value,
)


MAX_DEVICES_ENTITLEMENT = "max_devices"

DEVICE_TYPE_ENTITLEMENTS = {
    LicensedDeviceType.WINDOWS: "windows_client",
    LicensedDeviceType.ANDROID: "android_client",
}


@dataclass(frozen=True)
class DeviceActivationAuthorization:
    authorized: bool
    device_id: UUID
    organization_id: UUID
    subscription_id: UUID | None
    device_type: str | None = None
    reason: str | None = None


def _deny(
    device_id: UUID,
    organization_id: UUID,
    reason: str,
    subscription_id: UUID | None = None,
) -> DeviceActivationAuthorization:
    return DeviceActivationAuthorization(
        authorized=False,
        device_id=device_id,
        organization_id=organization_id,
        subscription_id=subscription_id,
        reason=reason,
    )


def authorize_device_activation(
    db: Session,
    organization_id: UUID,
    device_id: UUID,
) -> DeviceActivationAuthorization:
    device = db.get(LicensedDevice, device_id)

    if device is None:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            reason="DEVICE_NOT_FOUND",
        )

    if device.organization_id != organization_id:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            reason="DEVICE_NOT_OWNED",
        )

    organization = db.get(
        Organization,
        organization_id,
    )

    if organization is None:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            reason="ORGANIZATION_NOT_FOUND",
        )

    if organization.status != OrganizationStatus.ACTIVE:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            reason="ORGANIZATION_INACTIVE",
        )

    if device.branch_id is not None:
        branch = db.get(
            Branch,
            device.branch_id,
        )

        if branch is None:
            return _deny(
                device_id=device_id,
                organization_id=organization_id,
                reason="BRANCH_NOT_FOUND",
            )

        if branch.organization_id != organization_id:
            return _deny(
                device_id=device_id,
                organization_id=organization_id,
                reason="BRANCH_NOT_OWNED",
            )

        if branch.status != BranchStatus.ACTIVE:
            return _deny(
                device_id=device_id,
                organization_id=organization_id,
                reason="BRANCH_INACTIVE",
            )

    subscription = get_active_subscription(
        db=db,
        organization_id=organization_id,
    )

    if subscription is None:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            reason="SUBSCRIPTION_INVALID",
        )

    if device.status in {
        LicensedDeviceStatus.SUSPENDED,
        LicensedDeviceStatus.REVOKED,
    }:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            subscription_id=subscription.id,
            reason="DEVICE_INACTIVE",
        )

    entitlement_code = DEVICE_TYPE_ENTITLEMENTS.get(
        device.device_type,
    )

    if entitlement_code is None:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            subscription_id=subscription.id,
            reason="DEVICE_TYPE_UNSUPPORTED",
        )

    device_type_enabled = get_entitlement_value(
        db=db,
        organization_id=organization_id,
        entitlement_code=entitlement_code,
    )

    if device_type_enabled is not True:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            subscription_id=subscription.id,
            reason="DEVICE_TYPE_NOT_ENTITLED",
        )

    max_devices = get_entitlement_value(
        db=db,
        organization_id=organization_id,
        entitlement_code=MAX_DEVICES_ENTITLEMENT,
    )

    if (
        isinstance(max_devices, bool)
        or not isinstance(max_devices, int)
        or max_devices < 1
    ):
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            subscription_id=subscription.id,
            reason="MAX_DEVICES_ENTITLEMENT_INVALID",
        )

    active_activation_count = db.scalar(
        select(func.count(DeviceActivation.id))
        .where(
            DeviceActivation.subscription_id == subscription.id,
            DeviceActivation.status == DeviceActivationStatus.ACTIVE,
        )
    )

    if active_activation_count >= max_devices:
        return _deny(
            device_id=device_id,
            organization_id=organization_id,
            subscription_id=subscription.id,
            reason="DEVICE_LIMIT_REACHED",
        )

    return DeviceActivationAuthorization(
        authorized=True,
        device_id=device_id,
        organization_id=organization_id,
        subscription_id=subscription.id,
        reason=None,
    )

def issue_device_activation(
    db: Session,
    organization_id: UUID,
    device_id: UUID,
    activation_reference: str,
) -> DeviceActivation:
    if not activation_reference.strip():
        raise ValueError("ACTIVATION_REFERENCE_REQUIRED")

    authorization = authorize_device_activation(
        db=db,
        organization_id=organization_id,
        device_id=device_id,
    )

    if not authorization.authorized:
        raise ValueError(
            authorization.reason or "DEVICE_ACTIVATION_DENIED"
        )

    if authorization.subscription_id is None:
        raise ValueError("SUBSCRIPTION_INVALID")

    subscription = db.scalar(
        select(Subscription)
        .where(
            Subscription.id == authorization.subscription_id,
        )
        .with_for_update()
    )

    if subscription is None:
        raise ValueError("SUBSCRIPTION_NOT_FOUND")

    max_devices = get_entitlement_value(
        db=db,
        organization_id=organization_id,
        entitlement_code=MAX_DEVICES_ENTITLEMENT,
    )

    if (
        isinstance(max_devices, bool)
        or not isinstance(max_devices, int)
        or max_devices < 1
    ):
        raise ValueError(
            "MAX_DEVICES_ENTITLEMENT_INVALID"
        )

    active_activation_count = db.scalar(
        select(func.count(DeviceActivation.id))
        .where(
            DeviceActivation.subscription_id == subscription.id,
            DeviceActivation.status == DeviceActivationStatus.ACTIVE,
        )
    )

    if active_activation_count >= max_devices:
        raise ValueError(
            "DEVICE_LIMIT_REACHED"
        )

    existing_activation = db.scalar(
        select(DeviceActivation)
        .where(
            DeviceActivation.device_id == device_id,
            DeviceActivation.subscription_id == subscription.id,
        )
    )

    if existing_activation is not None:
        if existing_activation.status == DeviceActivationStatus.ACTIVE:
            raise ValueError(
                "DEVICE_ALREADY_ACTIVATED"
            )

        existing_activation.status = DeviceActivationStatus.ACTIVE
        existing_activation.activation_reference = activation_reference
        existing_activation.revoked_at = None
        existing_activation.revoke_reason = None
        existing_activation.last_validated_at = None
        existing_activation.last_online_at = None

        db.flush()

        return existing_activation

    activation = DeviceActivation(
        device_id=device_id,
        subscription_id=subscription.id,
        status=DeviceActivationStatus.ACTIVE,
        activation_reference=activation_reference,
    )

    db.add(activation)
    db.flush()

    return activation
