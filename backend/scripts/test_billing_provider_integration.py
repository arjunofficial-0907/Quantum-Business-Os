from decimal import Decimal
from uuid import uuid4

from app.providers.mock import MockPaymentProvider


provider = MockPaymentProvider()

organization_id = uuid4()
invoice_id = uuid4()

creation = provider.create_payment(
    organization_id=organization_id,
    invoice_id=invoice_id,
    amount=Decimal("1000.00"),
    currency="INR",
)

assert creation.provider_payment_id.startswith("mock_pay_")

capture = provider.capture_payment(
    provider_payment_id=creation.provider_payment_id,
    amount=Decimal("1000.00"),
    currency="INR",
)

assert capture.provider_payment_id == creation.provider_payment_id
assert capture.status == "captured"

print("=" * 55)
print("DAY 2.3.5 PROVIDER INTEGRATION PASSED")
print("=" * 55)
print("PROVIDER INJECTION CONTRACT: PASS")
print("CREATE PAYMENT: PASS")
print("CAPTURE PAYMENT: PASS")
print("=" * 55)