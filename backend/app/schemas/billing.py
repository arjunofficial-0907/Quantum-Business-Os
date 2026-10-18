from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BillingRecordCreate(BaseModel):
    subscription_id: UUID
    period_start: datetime
    period_end: datetime
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    description: str | None = None


class BillingRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    subscription_id: UUID

    period_start: datetime = Field(
        validation_alias="billing_period_start",
        serialization_alias="period_start",
    )
    period_end: datetime = Field(
        validation_alias="billing_period_end",
        serialization_alias="period_end",
    )

    amount: Decimal
    currency: str
    status: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    

class InvoiceCreate(BaseModel):
    subscription_id: UUID | None = None
    invoice_number: str = Field(min_length=1, max_length=100)
    subtotal: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(ge=0)
    total_amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    description: str | None = None
    due_at: datetime | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    subscription_id: UUID | None
    invoice_number: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    status: str
    description: str | None
    issued_at: datetime | None
    due_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentCreate(BaseModel):
    invoice_id: UUID
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    method: str
    provider: str = Field(min_length=1, max_length=50)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    invoice_id: UUID
    amount: Decimal
    currency: str
    status: str
    method: str
    provider: str
    provider_payment_id: str | None
    captured_at: datetime | None
    created_at: datetime
    updated_at: datetime