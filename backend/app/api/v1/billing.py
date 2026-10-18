from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization.dependencies import require_permission
from app.db.session import get_db
from app.models.billing import BillingRecord
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentMethod
from app.schemas.billing import (
    BillingRecordCreate,
    BillingRecordResponse,
    InvoiceCreate,
    InvoiceResponse,
    PaymentCreate,
    PaymentResponse,
)
from app.services.billing import (
    BillingServiceError,
    create_billing_record,
    create_invoice,
    create_payment,
    mark_payment_failed,
    mark_payment_paid,
)


router = APIRouter(
    prefix="/billing",
    tags=["Billing"],
)


@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("billing.invoice.create"))],
)
def create_invoice_endpoint(
    organization_id: UUID,
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
):
    try:
        invoice = create_invoice(
            db,
            organization_id=organization_id,
            subscription_id=payload.subscription_id,
            invoice_number=payload.invoice_number,
            amount=payload.total_amount,
            currency=payload.currency,
            issued_at=None,
            due_at=payload.due_at,
        )
        db.commit()
        db.refresh(invoice)
        return invoice

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice number already exists for this organization.",
        ) from exc

    except BillingServiceError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    dependencies=[
        Depends(require_permission("billing.invoice.read")),
    ],
)
def get_invoice_endpoint(
    invoice_id: UUID,
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.organization_id == organization_id,
        )
        .first()
    )

    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    return invoice


@router.post(
    "/records",
    response_model=BillingRecordResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("billing.record.create")),
    ],
)
def create_billing_record_endpoint(
    organization_id: UUID,
    payload: BillingRecordCreate,
    db: Session = Depends(get_db),
):
    try:
        billing_record = create_billing_record(
            db,
            organization_id=organization_id,
            subscription_id=payload.subscription_id,
            amount=payload.amount,
            currency=payload.currency,
            billing_period_start=payload.period_start,
            billing_period_end=payload.period_end,
            provider=None,
            provider_reference=None,
        )

        db.commit()
        db.refresh(billing_record)

        return billing_record

    except BillingServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/records/{billing_record_id}",
    response_model=BillingRecordResponse,
    dependencies=[
        Depends(require_permission("billing.record.read")),
    ],
)
def get_billing_record_endpoint(
    billing_record_id: UUID,
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    billing_record = (
        db.query(BillingRecord)
        .filter(
            BillingRecord.id == billing_record_id,
            BillingRecord.organization_id == organization_id,
        )
        .first()
    )

    if billing_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing record not found.",
        )

    return billing_record


@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("billing.payment.create")),
    ],
)
def create_payment_endpoint(
    organization_id: UUID,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
):
    try:
        try:
            method = PaymentMethod(payload.method)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported payment method: {payload.method}",
            ) from exc

        payment = create_payment(
            db,
            organization_id=organization_id,
            invoice_id=payload.invoice_id,
            amount=Decimal(payload.amount),
            currency=payload.currency,
            method=method,
            provider=payload.provider,
        )

        db.commit()
        db.refresh(payment)

        return payment

    except BillingServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[
        Depends(require_permission("billing.payment.read")),
    ],
)
def get_payment_endpoint(
    payment_id: UUID,
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.organization_id == organization_id,
        )
        .first()
    )

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    return payment


@router.post(
    "/payments/{payment_id}/paid",
    response_model=PaymentResponse,
    dependencies=[
        Depends(require_permission("billing.payment.update")),
    ],
)
def mark_payment_paid_endpoint(
    payment_id: UUID,
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        payment = mark_payment_paid(
            db,
            payment_id=payment_id,
            organization_id=organization_id,
            paid_at=datetime.utcnow(),
        )

        db.commit()
        db.refresh(payment)

        return payment

    except BillingServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/payments/{payment_id}/failed",
    response_model=PaymentResponse,
    dependencies=[
        Depends(require_permission("billing.payment.update")),
    ],
)
def mark_payment_failed_endpoint(
    payment_id: UUID,
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        payment = mark_payment_failed(
            db,
            payment_id=payment_id,
            organization_id=organization_id,
        )

        db.commit()
        db.refresh(payment)

        return payment

    except BillingServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc