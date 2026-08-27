import pytest

from app import payments, store


@pytest.fixture(autouse=True)
def _clear_payment_intents():
    store.reset()


def test_create_payment_request_returns_requires_confirmation_intent():
    result = payments.create_payment_request(
        transaction_id="txn-1",
        buyer_agent_id="BuyerAgent",
        product_id="PROD-1001",
        agreed_unit_price=9.00,
        quantity=200,
        total_amount=1800.00,
    )

    assert result["payment_intent_id"].startswith("pi_mock_")
    assert result["payment_status"] == "requires_confirmation"


def test_authorize_payment_confirms_matching_payment_intent():
    created = payments.create_payment_request(
        transaction_id="txn-1",
        buyer_agent_id="BuyerAgent",
        product_id="PROD-1001",
        agreed_unit_price=9.00,
        quantity=200,
        total_amount=1800.00,
    )

    result = payments.authorize_payment(
        transaction_id="txn-1",
        payment_intent_id=created["payment_intent_id"],
        payment_method_token="tok_mock_visa",
        authorized_amount=1800.00,
    )

    assert result["payment_intent_id"] == created["payment_intent_id"]
    assert result["payment_status"] == "succeeded"


def test_authorize_payment_unknown_intent_raises_validation_error():
    with pytest.raises(payments.PaymentValidationError):
        payments.authorize_payment(
            transaction_id="txn-1",
            payment_intent_id="pi_mock_does_not_exist",
            payment_method_token="tok_mock_visa",
            authorized_amount=1800.00,
        )


def test_authorize_payment_amount_mismatch_raises_validation_error():
    created = payments.create_payment_request(
        transaction_id="txn-1",
        buyer_agent_id="BuyerAgent",
        product_id="PROD-1001",
        agreed_unit_price=9.00,
        quantity=200,
        total_amount=1800.00,
    )

    with pytest.raises(payments.PaymentValidationError):
        payments.authorize_payment(
            transaction_id="txn-1",
            payment_intent_id=created["payment_intent_id"],
            payment_method_token="tok_mock_visa",
            authorized_amount=999.00,
        )
