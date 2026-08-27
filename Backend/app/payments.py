"""Mock Stripe payment tool.

[PLACEHOLDER] Real Stripe API keys, mode (test/live), and preferred flow
(PaymentIntents vs. Checkout vs. Invoices API) are not yet known -- see
INSTRUCTIONS.md Section 5. Ask the user for these before swapping in the
real Stripe SDK (a future ticket, mirroring BE-7 for ClickHouse).

Until then, this module mocks Stripe's PaymentIntent lifecycle well enough
for the payment_request / payment_authorization / generate_invoice graph
nodes (BE-4) to exercise a realistic create -> confirm flow:

- create_payment_request ("payment request", Vendor-side) creates a
  Stripe-shaped PaymentIntent in `requires_confirmation` status and stores
  it in-memory.
- authorize_payment ("payment initiation", Buyer-side) looks up that
  PaymentIntent by `payment_intent_id`, validates the amount, and confirms
  it (status -> "succeeded").

An unknown `payment_intent_id` or an amount mismatch raises
PaymentValidationError, which graph.py logs as
execution_status="ValidationError".

PaymentIntents are persisted through `app.store` rather than held in a module
dict, so an intent created before a restart can still be confirmed afterwards
and a second worker can confirm one the first worker created.
"""

import time
import uuid

from app import store


class PaymentValidationError(Exception):
    """Raised when a mock Stripe call references an unknown PaymentIntent
    or supplies a value that doesn't match the stored PaymentIntent."""


def create_payment_request(
    *,
    transaction_id: str,
    buyer_agent_id: str,
    product_id: str,
    agreed_unit_price: float,
    quantity: int,
    total_amount: float,
) -> dict:
    payment_intent_id = f"pi_mock_{uuid.uuid4().hex[:24]}"
    payment_intent = {
        "id": payment_intent_id,
        "object": "payment_intent",
        "amount": round(total_amount * 100),
        "currency": "usd",
        "status": "requires_confirmation",
        "created": int(time.time()),
        "metadata": {
            "transaction_id": transaction_id,
            "buyer_agent_id": buyer_agent_id,
            "product_id": product_id,
            "agreed_unit_price": agreed_unit_price,
            "quantity": quantity,
        },
    }
    store.save_payment_intent(payment_intent)

    return {
        "payment_intent_id": payment_intent_id,
        "payment_status": payment_intent["status"],
    }


def authorize_payment(
    *,
    transaction_id: str,
    payment_intent_id: str,
    payment_method_token: str,
    authorized_amount: float,
) -> dict:
    payment_intent = store.get_payment_intent(payment_intent_id)
    if payment_intent is None:
        raise PaymentValidationError(f"Unknown payment_intent_id: {payment_intent_id!r}")

    expected_amount = round(authorized_amount * 100)
    if payment_intent["amount"] != expected_amount:
        raise PaymentValidationError(
            f"authorized_amount {authorized_amount!r} does not match "
            f"PaymentIntent amount {payment_intent['amount'] / 100:.2f}"
        )

    payment_intent["status"] = "succeeded"
    payment_intent["payment_method"] = payment_method_token
    store.save_payment_intent(payment_intent)

    return {
        "payment_intent_id": payment_intent_id,
        "payment_status": payment_intent["status"],
    }
