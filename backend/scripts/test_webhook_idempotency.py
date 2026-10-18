from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.webhook_event import WebhookEvent, WebhookEventStatus
from app.services.webhook import (
    DuplicateWebhookEvent,
    WebhookEventError,
    mark_webhook_failed,
    mark_webhook_processed,
    mark_webhook_processing,
    receive_webhook_event,
)


db = SessionLocal()

try:
    organization = Organization(
        name=f"Webhook Test Org {uuid4().hex[:8]}",
    )
    db.add(organization)
    db.flush()

    event_id = f"evt_{uuid4().hex}"

    # ---------------------------------------------------------
    # FIRST EVENT
    # ---------------------------------------------------------

    event = receive_webhook_event(
        db,
        organization_id=organization.id,
        provider="mock",
        event_id=event_id,
        event_type="payment.captured",
    )

    assert event.event_id == event_id
    assert event.status == WebhookEventStatus.RECEIVED

    # ---------------------------------------------------------
    # EVENT PERSISTENCE
    # ---------------------------------------------------------

    persisted = db.execute(
        select(WebhookEvent).where(
            WebhookEvent.event_id == event_id
        )
    ).scalar_one()

    assert persisted.id == event.id

    # ---------------------------------------------------------
    # PROCESSING
    # ---------------------------------------------------------

    processing_event = mark_webhook_processing(
        db,
        event_id=event_id,
        organization_id=organization.id,
    )

    assert processing_event.status == WebhookEventStatus.PROCESSING

    # ---------------------------------------------------------
    # PROCESSED
    # ---------------------------------------------------------

    processed_event = mark_webhook_processed(
        db,
        event_id=event_id,
        organization_id=organization.id,
    )

    assert processed_event.status == WebhookEventStatus.PROCESSED
    assert processed_event.processed_at is not None

    # ---------------------------------------------------------
    # DUPLICATE EVENT
    # ---------------------------------------------------------

    duplicate_failed = False

    try:
        receive_webhook_event(
            db,
            organization_id=organization.id,
            provider="mock",
            event_id=event_id,
            event_type="payment.captured",
        )
    except DuplicateWebhookEvent:
        duplicate_failed = True

    assert duplicate_failed is True

    # ---------------------------------------------------------
    # DIFFERENT EVENT
    # ---------------------------------------------------------

    second_event_id = f"evt_{uuid4().hex}"

    second_event = receive_webhook_event(
        db,
        organization_id=organization.id,
        provider="mock",
        event_id=second_event_id,
        event_type="payment.failed",
    )

    assert second_event.event_id == second_event_id
    assert second_event.status == WebhookEventStatus.RECEIVED

    # ---------------------------------------------------------
    # FAILED EVENT
    # ---------------------------------------------------------

    failed_event = mark_webhook_failed(
        db,
        event_id=second_event_id,
        organization_id=organization.id,
        error_message="Payment provider rejected the payment.",
    )

    assert failed_event.status == WebhookEventStatus.FAILED
    assert failed_event.error_message is not None

    # ---------------------------------------------------------
    # TENANT ISOLATION
    # ---------------------------------------------------------

    other_organization = Organization(
        name=f"Webhook Other Org {uuid4().hex[:8]}",
    )
    db.add(other_organization)
    db.flush()

    tenant_isolation_failed = False

    try:
        mark_webhook_processed(
            db,
            event_id=event_id,
            organization_id=other_organization.id,
        )
    except WebhookEventError:
        tenant_isolation_failed = True

    assert tenant_isolation_failed is True

    db.commit()

    print("=" * 55)
    print("DAY 2.4.4 WEBHOOK IDEMPOTENCY TEST PASSED")
    print("=" * 55)
    print("EVENT CREATION: PASS")
    print("EVENT PERSISTENCE: PASS")
    print("PROCESSING STATE: PASS")
    print("PROCESSED STATE: PASS")
    print("DUPLICATE PROTECTION: PASS")
    print("DIFFERENT EVENT: PASS")
    print("FAILED STATE: PASS")
    print("TENANT ISOLATION: PASS")
    print("=" * 55)

except Exception:
    db.rollback()
    raise

finally:
    db.close()