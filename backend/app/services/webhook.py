from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent, WebhookEventStatus


class WebhookServiceError(Exception):
    """Base exception for webhook service errors."""


class DuplicateWebhookEvent(WebhookServiceError):
    """Raised when a webhook event has already been received."""


class WebhookEventError(WebhookServiceError):
    """Raised when webhook event processing is invalid."""


def receive_webhook_event(
    db: Session,
    *,
    organization_id: UUID,
    provider: str,
    event_id: str,
    event_type: str,
) -> WebhookEvent:
    """
    Persist a newly received webhook event.

    event_id is globally unique and provides the database-level
    idempotency boundary.
    """
    if not event_id.strip():
        raise WebhookEventError("Webhook event ID is required.")

    if not provider.strip():
        raise WebhookEventError("Webhook provider is required.")

    if not event_type.strip():
        raise WebhookEventError("Webhook event type is required.")

    existing = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.event_id == event_id)
        .first()
    )

    if existing is not None:
        raise DuplicateWebhookEvent(
            f"Webhook event '{event_id}' has already been received."
        )

    event = WebhookEvent(
        organization_id=organization_id,
        provider=provider,
        event_id=event_id,
        event_type=event_type,
        status=WebhookEventStatus.RECEIVED,
    )

    db.add(event)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateWebhookEvent(
            f"Webhook event '{event_id}' has already been received."
        ) from exc

    return event


def mark_webhook_processing(
    db: Session,
    *,
    event_id: str,
    organization_id: UUID,
) -> WebhookEvent:
    event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.event_id == event_id,
            WebhookEvent.organization_id == organization_id,
        )
        .first()
    )

    if event is None:
        raise WebhookEventError("Webhook event not found.")

    if event.status == WebhookEventStatus.PROCESSED:
        return event

    event.status = WebhookEventStatus.PROCESSING
    db.flush()

    return event


def mark_webhook_processed(
    db: Session,
    *,
    event_id: str,
    organization_id: UUID,
) -> WebhookEvent:
    event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.event_id == event_id,
            WebhookEvent.organization_id == organization_id,
        )
        .first()
    )

    if event is None:
        raise WebhookEventError("Webhook event not found.")

    event.status = WebhookEventStatus.PROCESSED
    event.processed_at = datetime.now(timezone.utc)
    event.error_message = None

    db.flush()

    return event


def mark_webhook_failed(
    db: Session,
    *,
    event_id: str,
    organization_id: UUID,
    error_message: str,
) -> WebhookEvent:
    event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.event_id == event_id,
            WebhookEvent.organization_id == organization_id,
        )
        .first()
    )

    if event is None:
        raise WebhookEventError("Webhook event not found.")

    if not error_message.strip():
        raise WebhookEventError("Webhook failure reason is required.")

    event.status = WebhookEventStatus.FAILED
    event.error_message = error_message

    db.flush()

    return event