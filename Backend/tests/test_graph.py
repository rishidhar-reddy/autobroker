from app.config import BUYER_CONFIG, VENDOR_CONFIG
from app.graph import (
    MAX_TURNS,
    _build_system_prompt,
    _conversation_messages,
    build_graph,
    build_initial_state,
    buyer_agent,
    generate_invoice,
    guardrail_validator,
    parse_offer,
    payment_authorization,
    payment_request,
    route_after_guardrail,
    vendor_agent,
)


def _state_with_messages(messages, **overrides):
    state = build_initial_state("txn-1", VENDOR_CONFIG, BUYER_CONFIG)
    state["messages"] = messages
    state.update(overrides)
    return state


def _message(sender, price, quantity, action):
    return {
        "sender": sender,
        "text": f"[OFFER price={price:.2f} quantity={quantity} action={action}]",
        "extracted_price": price,
        "extracted_quantity": quantity,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }


def _raise_not_implemented(*args, **kwargs):
    raise NotImplementedError("Promise Platform not configured")


def test_parse_offer_extracts_price_quantity_and_action():
    text = "Sounds good. [OFFER price=9.50 quantity=200 action=COUNTER]"

    price, quantity, action = parse_offer(text)

    assert price == 9.50
    assert quantity == 200
    assert action == "COUNTER"


def test_parse_offer_returns_none_when_no_tag_present():
    assert parse_offer("no structured offer here") == (None, None, None)


def test_guardrail_terminates_when_vendor_price_below_floor():
    state = _state_with_messages(
        [_message("VendorAgent", VENDOR_CONFIG["Floor_Price"] - 1, 200, "COUNTER")]
    )

    update = guardrail_validator(state)

    assert update["status"] == "TERMINATED"


def test_guardrail_terminates_when_buyer_accepts_above_ceiling():
    state = _state_with_messages(
        [_message("BuyerAgent", BUYER_CONFIG["Buyer_Ceiling_Price"] + 1, 200, "ACCEPT")]
    )

    update = guardrail_validator(state)

    assert update["status"] == "TERMINATED"


def test_guardrail_terminates_when_buyer_counters_above_ceiling():
    """The buyer's system prompt forbids it to "accept or offer" above its
    ceiling, and the vendor's floor is enforced on every offer regardless of
    action. The buyer ceiling must be enforced the same way, otherwise an
    agent can propose a price it is not allowed to pay and only get caught
    if the vendor happens to accept it."""
    state = _state_with_messages(
        [_message("BuyerAgent", BUYER_CONFIG["Buyer_Ceiling_Price"] + 1, 200, "COUNTER")]
    )

    update = guardrail_validator(state)

    assert update["status"] == "TERMINATED"


def test_guardrail_allows_buyer_counter_at_exactly_the_ceiling():
    """The bound is inclusive: the ceiling itself is a legal offer."""
    state = _state_with_messages(
        [_message("BuyerAgent", BUYER_CONFIG["Buyer_Ceiling_Price"], 200, "COUNTER")]
    )

    update = guardrail_validator(state)

    assert update["status"] == "NEGOTIATING"


def test_guardrail_terminates_when_turn_limit_exceeded():
    state = _state_with_messages(
        [_message("BuyerAgent", 9.00, 200, "COUNTER")], turn=MAX_TURNS
    )

    update = guardrail_validator(state)

    assert update["status"] == "TERMINATED"


def test_guardrail_marks_agreement_on_accept_within_bounds():
    agreed_price = (VENDOR_CONFIG["Floor_Price"] + BUYER_CONFIG["Buyer_Ceiling_Price"]) / 2
    state = _state_with_messages(
        [_message("VendorAgent", agreed_price, 200, "ACCEPT")]
    )

    update = guardrail_validator(state)

    assert update["status"] == "AGREEMENT"
    assert update["current_price"] == agreed_price
    assert update["current_quantity"] == 200


def test_route_after_guardrail_alternates_turns():
    negotiating_buyer_last = _state_with_messages(
        [_message("BuyerAgent", 8.00, 200, "COUNTER")], status="NEGOTIATING"
    )
    negotiating_vendor_last = _state_with_messages(
        [_message("VendorAgent", 8.00, 200, "COUNTER")], status="NEGOTIATING"
    )

    assert route_after_guardrail(negotiating_buyer_last) == "vendor_agent"
    assert route_after_guardrail(negotiating_vendor_last) == "buyer_agent"


def test_route_after_guardrail_handles_terminal_statuses():
    agreement_state = _state_with_messages([], status="AGREEMENT")
    terminated_state = _state_with_messages([], status="TERMINATED")

    assert route_after_guardrail(agreement_state) == "agreement"
    assert route_after_guardrail(terminated_state) == "terminated"


def test_negotiation_graph_reaches_a_terminal_status_within_turn_limit():
    graph = build_graph()
    initial_state = build_initial_state("txn-1", VENDOR_CONFIG, BUYER_CONFIG)

    final_state = graph.invoke(initial_state)

    assert final_state["status"] in ("FULFILLED", "TERMINATED")
    assert final_state["turn"] <= MAX_TURNS
    assert final_state["messages"][0]["sender"] == "BuyerAgent"


def test_negotiation_graph_converges_to_fulfilled_with_invoice():
    graph = build_graph()
    initial_state = build_initial_state("txn-1", VENDOR_CONFIG, BUYER_CONFIG)

    final_state = graph.invoke(initial_state)

    assert final_state["status"] == "FULFILLED"
    assert VENDOR_CONFIG["Floor_Price"] <= final_state["current_price"] <= BUYER_CONFIG["Buyer_Ceiling_Price"]

    invoice = final_state["invoice"]
    assert invoice["transaction_id"] == "txn-1"
    assert invoice["product_id"] == VENDOR_CONFIG["Product_ID"]
    assert invoice["unit_price"] == final_state["current_price"]
    assert invoice["quantity"] == final_state["current_quantity"]
    assert invoice["total_amount"] == round(final_state["current_price"] * final_state["current_quantity"], 2)
    assert invoice["payment_status"] == "succeeded"


def test_buyer_agent_logs_message_via_telemetry(monkeypatch):
    logged = []
    monkeypatch.setattr(
        "app.graph.telemetry.log_message", lambda **kwargs: logged.append(kwargs)
    )

    initial_state = build_initial_state("txn-1", VENDOR_CONFIG, BUYER_CONFIG)
    buyer_agent(initial_state)

    assert len(logged) == 1
    assert logged[0]["transaction_id"] == "txn-1"
    assert logged[0]["sender_type"] == "BuyerAgent"


def test_guardrail_validator_logs_system_message_via_telemetry(monkeypatch):
    logged = []
    monkeypatch.setattr(
        "app.graph.telemetry.log_message", lambda **kwargs: logged.append(kwargs)
    )

    state = _state_with_messages([_message("BuyerAgent", 8.00, 200, "COUNTER")])
    guardrail_validator(state)

    assert len(logged) == 1
    assert logged[0]["sender_type"] == "System"


def test_payment_request_sets_payment_pending_and_records_invoice_fields():
    state = _state_with_messages([], status="AGREEMENT", current_price=9.0, current_quantity=200)

    update = payment_request(state)

    assert update["status"] == "PAYMENT_PENDING"
    assert update["invoice"]["agreed_unit_price"] == 9.0
    assert update["invoice"]["quantity"] == 200
    assert update["invoice"]["total_amount"] == 1800.0
    assert update["invoice"]["payment_status"] == "requires_confirmation"


def test_payment_authorization_sets_fulfilled_and_succeeded_status():
    request_state = _state_with_messages([], status="AGREEMENT", current_price=9.0, current_quantity=200)
    invoice = payment_request(request_state)["invoice"]

    state = _state_with_messages(
        [], status="PAYMENT_PENDING", current_price=9.0, current_quantity=200, invoice=invoice
    )

    update = payment_authorization(state)

    assert update["status"] == "FULFILLED"
    assert update["invoice"]["authorized_amount"] == 1800.0
    assert update["invoice"]["payment_status"] == "succeeded"
    assert update["invoice"]["payment_intent_id"] == invoice["payment_intent_id"]


def test_payment_authorization_logs_validation_error_for_unknown_intent(monkeypatch):
    logged = []
    monkeypatch.setattr(
        "app.graph.telemetry.log_tool_execution", lambda **kwargs: logged.append(kwargs)
    )

    state = _state_with_messages(
        [],
        status="PAYMENT_PENDING",
        current_price=9.0,
        current_quantity=200,
        invoice={"total_amount": 1800.0, "payment_intent_id": "pi_mock_does_not_exist"},
    )

    update = payment_authorization(state)

    assert logged[0]["execution_status"] == "ValidationError"
    assert "payment_status" not in update["invoice"]


def test_generate_invoice_builds_invoice_from_agreed_terms():
    state = _state_with_messages(
        [], status="FULFILLED", current_price=9.0, current_quantity=200, invoice={}
    )

    update = generate_invoice(state)

    invoice = update["invoice"]
    assert invoice["transaction_id"] == "txn-1"
    assert invoice["product_id"] == VENDOR_CONFIG["Product_ID"]
    assert invoice["unit_price"] == 9.0
    assert invoice["quantity"] == 200
    assert invoice["total_amount"] == 1800.0


def test_conversation_messages_maps_own_and_other_sender_roles_and_appends_prompt():
    state = _state_with_messages(
        [
            _message("BuyerAgent", 7.00, 200, "COUNTER"),
            _message("VendorAgent", 11.00, 200, "COUNTER"),
        ]
    )

    messages = _conversation_messages(state, "BuyerAgent")

    assert messages[0] == {"role": "assistant", "content": state["messages"][0]["text"]}
    assert messages[1] == {"role": "user", "content": state["messages"][1]["text"]}
    assert messages[-1]["role"] == "user"


def test_buyer_system_prompt_includes_buyer_bounds_and_offer_format():
    prompt = _build_system_prompt("BuyerAgent", VENDOR_CONFIG, BUYER_CONFIG)

    assert f"{BUYER_CONFIG['Buyer_Ceiling_Price']:.2f}" in prompt
    assert "[OFFER price=" in prompt


def test_vendor_system_prompt_includes_vendor_bounds_and_offer_format():
    prompt = _build_system_prompt("VendorAgent", VENDOR_CONFIG, BUYER_CONFIG)

    assert f"{VENDOR_CONFIG['Floor_Price']:.2f}" in prompt
    assert "[OFFER price=" in prompt


def test_buyer_agent_uses_promise_platform_response_when_configured(monkeypatch):
    monkeypatch.setattr(
        "app.graph.llm_client.generate",
        lambda system_prompt, messages: "Let's start at $7.00. [OFFER price=7.00 quantity=200 action=COUNTER]",
    )

    initial_state = build_initial_state("txn-1", VENDOR_CONFIG, BUYER_CONFIG)
    update = buyer_agent(initial_state)

    message = update["messages"][-1]
    assert message["text"] == "Let's start at $7.00. [OFFER price=7.00 quantity=200 action=COUNTER]"
    assert message["extracted_price"] == 7.00
    assert message["extracted_quantity"] == 200


def test_buyer_agent_falls_back_to_mock_when_promise_platform_not_configured(monkeypatch):
    monkeypatch.setattr("app.graph.llm_client.generate", _raise_not_implemented)

    initial_state = build_initial_state("txn-1", VENDOR_CONFIG, BUYER_CONFIG)
    update = buyer_agent(initial_state)

    message = update["messages"][-1]
    assert message["extracted_price"] == BUYER_CONFIG["Buyer_Floor_Price"]
    assert message["extracted_quantity"] == BUYER_CONFIG["Desired_Quantity"]


def test_vendor_agent_uses_promise_platform_response_when_configured(monkeypatch):
    monkeypatch.setattr(
        "app.graph.llm_client.generate",
        lambda system_prompt, messages: "I can do $11.00. [OFFER price=11.00 quantity=200 action=COUNTER]",
    )

    state = _state_with_messages([_message("BuyerAgent", 7.00, 200, "COUNTER")])
    update = vendor_agent(state)

    message = update["messages"][-1]
    assert message["text"] == "I can do $11.00. [OFFER price=11.00 quantity=200 action=COUNTER]"
    assert message["extracted_price"] == 11.00
    assert message["extracted_quantity"] == 200


def test_vendor_agent_falls_back_to_mock_when_promise_platform_not_configured(monkeypatch):
    monkeypatch.setattr("app.graph.llm_client.generate", _raise_not_implemented)

    state = _state_with_messages([_message("BuyerAgent", 7.00, 200, "COUNTER")])
    update = vendor_agent(state)

    message = update["messages"][-1]
    assert message["extracted_price"] == round((VENDOR_CONFIG["Ceiling_Price"] + 7.00) / 2, 2)
    assert message["extracted_quantity"] == 200
