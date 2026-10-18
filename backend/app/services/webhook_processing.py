from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.webhook_event import WebhookEventStatus
from app.providers.webhooks import PaymentWebhookEvent
from app.services.webhook import (
    DuplicateWebhookEvent,
    mark_webhook_failed,
    mark_webhook_processed,
    mark_webhook_processing,
    receive_webhook_event,
)


class WebhookProcessingError(Exception):
    """Raised when webhook processing fails."""


def process_payment_webhook(
    db: Session,
    *,
    event: PaymentWebhookEvent,
) -> bool:
    """
    Process a normalized payment webhook event.

    Returns:
        True when the event was processed.
        False when the event was already received.
    """

    try:
        webhook_event = receive_webhook_event(
            db,
            organization_id=event.organization_id,
            provider="mock",
            event_id=event.event_id,
            event_type=event.event_type.value,
        )
    except DuplicateWebhookEvent:
        return False

    try:
        mark_webhook_processing(
            db,
            event_id=event.event_id,
            organization_id=event.organization_id,
        )

        payment = (
            db.query(Payment)
            .filter(
                Payment.organization_id == event.organization_id,
                Payment.provider_payment_id
                == event.provider_payment_id,
            )
            .first()
        )

        if payment is None:
            raise WebhookProcessingError(
                "Payment not found for webhook event."
            )

        if payment.invoice_id != event.invoice_id:
            raise WebhookProcessingError(
                "Webhook invoice does not match payment invoice."
            )

        if payment.amount != event.amount:
            raise WebhookProcessingError(
                "Webhook payment amount does not match payment."
            )

        if payment.currency.upper() != event.currency.upper():
            raise WebhookProcessingError(
                "Webhook payment currency does not match payment."
            )

        if event.event_type.value == "payment.captured":
            payment.status = PaymentStatus.CAPTURED

            invoice = (
                db.query(Invoice)
                .filter(
                    Invoice.id == payment.invoice_id,
                    Invoice.organization_id == event.organization_id,
                )
                .first()
            )

            if invoice is None:
                raise WebhookProcessingError(
                    "Payment invoice not found."
                )

            invoice.status = InvoiceStatus.PAID

        elif event.event_type.value == "payment.failed":
            payment.status = PaymentStatus.FAILED

        elif event.event_type.value == "payment.cancelled":
            payment.status = PaymentStatus.CANCELLED

        else:
            raise WebhookProcessingError(
                f"Unsupported webhook event type "
                f"'{event.event_type.value}'."
            )

        mark_webhook_processed(
            db,
            event_id=event.event_id,
            organization_id=event.organization_id,
        )

        db.flush()

        return True

    except Exception as exc:
        mark_webhook_failed(
            db,
            event_id=event.event_id,
            organization_id=event.organization_id,
            error_message=str(exc),
        )

        db.flush()

        raise WebhookProcessingError(str(exc)) from exc