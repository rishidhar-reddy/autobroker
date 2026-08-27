"""LangGraph negotiation state graph.

See INSTRUCTIONS.md Section 3 (protocol) and Section 4 (orchestration design).

Both agent nodes call the Promise Platform LLM (`app.llm_client.generate`)
with a role-specific system prompt and the conversation history. If the
Promise Platform is not configured (`NotImplementedError`), the nodes fall
back to a mock LLM (see `_next_offer`) that produces canned offers/counters
by moving each side's price toward the other's last offer until the gap
closes, at which point it accepts. This lets the graph be built and tested
without real Promise Platform credentials (BE-3).
"""

import re
from datetime import datetime, timezone
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app import llm_client, payments, telemetry

MAX_TURNS = 10
CONVERGENCE_THRESHOLD = 0.5

OFFER_PATTERN = re.compile(
    r"\[OFFER price=(?P<price>[0-9]+(?:\.[0-9]+)?)"
    r" quantity=(?P<quantity>[0-9]+)"
    r" action=(?P<action>ACCEPT|COUNTER|REJECT)\]"
)


class Message(TypedDict):
    sender: Literal["VendorAgent", "BuyerAgent", "System"]
    text: str
    extracted_price: Optional[float]
    extracted_quantity: Optional[int]
    timestamp: str


class NegotiationState(TypedDict):
    transaction_id: str
    turn: int
    status: Literal["NEGOTIATING", "AGREEMENT", "PAYMENT_PENDING", "FULFILLED", "TERMINATED"]
    messages: list[Message]
    current_price: Optional[float]
    current_quantity: Optional[int]
    vendor_config: dict
    buyer_config: dict
    invoice: Optional[dict]


def build_initial_state(transaction_id: str, vendor_config: dict, buyer_config: dict) -> NegotiationState:
    return {
        "transaction_id": transaction_id,
        "turn": 0,
        "status": "NEGOTIATING",
        "messages": [],
        "current_price": None,
        "current_quantity": None,
        "vendor_config": vendor_config,
        "buyer_config": buyer_config,
        "invoice": None,
    }


def parse_offer(text: str) -> tuple[Optional[float], Optional[int], Optional[str]]:
    match = OFFER_PATTERN.search(text)
    if not match:
        return None, None, None
    return float(match["price"]), int(match["quantity"]), match["action"]


def _build_message(sender: Literal["VendorAgent", "BuyerAgent"], text: str) -> Message:
    price, quantity, _ = parse_offer(text)
    return {
        "sender": sender,
        "text": text,
        "extracted_price": price,
        "extracted_quantity": quantity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _last_message_from(state: NegotiationState, sender: str) -> Optional[Message]:
    for message in reversed(state["messages"]):
        if message["sender"] == sender:
            return message
    return None


def _next_offer(state: NegotiationState, *, sender: str, anchor_price: float) -> tuple[float, str]:
    """Mock LLM negotiation strategy: move toward the other side's last
    offer, accepting once the gap is within CONVERGENCE_THRESHOLD."""
    other_sender = "VendorAgent" if sender == "BuyerAgent" else "BuyerAgent"
    other_message = _last_message_from(state, other_sender)
    own_message = _last_message_from(state, sender)

    own_price = own_message["extracted_price"] if own_message else anchor_price
    other_price = other_message["extracted_price"] if other_message else None

    if other_price is None:
        return own_price, "COUNTER"
    if abs(own_price - other_price) <= CONVERGENCE_THRESHOLD:
        return other_price, "ACCEPT"
    return round((own_price + other_price) / 2, 2), "COUNTER"


_NEGOTIATION_INSTRUCTIONS = (
    "Negotiate to get the best possible price. Keep replies short -- one or two sentences.\n"
    "Every reply MUST end with exactly one structured tag in this format:\n"
    "[OFFER price=X.XX quantity=N action=ACCEPT|COUNTER|REJECT]\n\n"
    "- action=ACCEPT: you agree to the other side's last offer (echo their price and quantity).\n"
    "- action=COUNTER: you are proposing a different price.\n"
    "- action=REJECT: you are walking away from the deal."
)


def _build_system_prompt(sender: str, vendor_config: dict, buyer_config: dict) -> str:
    if sender == "BuyerAgent":
        return (
            f"You are BuyerAgent, an autonomous procurement agent negotiating the purchase "
            f"of product {buyer_config['Target_Product_ID']}.\n"
            f"You want to buy {buyer_config['Desired_Quantity']} units.\n"
            f"Your hard ceiling is ${buyer_config['Buyer_Ceiling_Price']:.2f} per unit -- "
            f"you must never accept or offer a price above this.\n"
            f"Your ideal opening price is ${buyer_config['Buyer_Floor_Price']:.2f} per unit.\n\n"
            f"{_NEGOTIATION_INSTRUCTIONS}"
        )

    return (
        f"You are VendorAgent, an autonomous sales agent negotiating the sale "
        f"of product {vendor_config['Product_ID']}.\n"
        f"You have {vendor_config['Stock_Quantity']} units in stock.\n"
        f"Your hard floor is ${vendor_config['Floor_Price']:.2f} per unit -- "
        f"you must never accept or offer a price below this.\n"
        f"Your ideal opening price is ${vendor_config['Ceiling_Price']:.2f} per unit.\n\n"
        f"{_NEGOTIATION_INSTRUCTIONS}"
    )


def _conversation_messages(state: NegotiationState, sender: str) -> list[dict]:
    other_sender = "VendorAgent" if sender == "BuyerAgent" else "BuyerAgent"
    messages: list[dict] = []
    for message in state["messages"]:
        if message["sender"] == sender:
            messages.append({"role": "assistant", "content": message["text"]})
        elif message["sender"] == other_sender:
            messages.append({"role": "user", "content": message["text"]})
    messages.append(
        {"role": "user", "content": "Continue the negotiation. Respond with your message and offer tag now."}
    )
    return messages


def _llm_offer_text(state: NegotiationState, sender: str) -> Optional[str]:
    try:
        system_prompt = _build_system_prompt(sender, state["vendor_config"], state["buyer_config"])
        messages = _conversation_messages(state, sender)
        return llm_client.generate(system_prompt, messages)
    except NotImplementedError:
        return None


def buyer_agent(state: NegotiationState) -> dict:
    config = state["buyer_config"]
    text = _llm_offer_text(state, "BuyerAgent")
    if text is not None:
        source = "promise_platform"
    else:
        price, action = _next_offer(state, sender="BuyerAgent", anchor_price=config["Buyer_Floor_Price"])
        quantity = config["Desired_Quantity"]
        text = (
            f"I'd like to buy {quantity} units at ${price:.2f} per unit. "
            f"[OFFER price={price:.2f} quantity={quantity} action={action}]"
        )
        source = "mock_llm"

    message = _build_message("BuyerAgent", text)
    _, _, action = parse_offer(text)
    telemetry.log_message(
        transaction_id=state["transaction_id"],
        conversation_turn=state["turn"] + 1,
        sender_type="BuyerAgent",
        sender_id="BuyerAgent",
        receiver_id="VendorAgent",
        raw_message=text,
        extracted_price=message["extracted_price"],
        extracted_quantity=message["extracted_quantity"],
        llm_metadata={"source": source, "action": action},
    )
    return {"messages": state["messages"] + [message]}


def vendor_agent(state: NegotiationState) -> dict:
    config = state["vendor_config"]
    text = _llm_offer_text(state, "VendorAgent")
    if text is not None:
        source = "promise_platform"
    else:
        price, action = _next_offer(state, sender="VendorAgent", anchor_price=config["Ceiling_Price"])
        quantity = _last_message_from(state, "BuyerAgent")["extracted_quantity"]
        text = (
            f"I can supply {quantity} units at ${price:.2f} per unit. "
            f"[OFFER price={price:.2f} quantity={quantity} action={action}]"
        )
        source = "mock_llm"

    message = _build_message("VendorAgent", text)
    _, _, action = parse_offer(text)
    telemetry.log_message(
        transaction_id=state["transaction_id"],
        conversation_turn=state["turn"] + 1,
        sender_type="VendorAgent",
        sender_id="VendorAgent",
        receiver_id="BuyerAgent",
        raw_message=text,
        extracted_price=message["extracted_price"],
        extracted_quantity=message["extracted_quantity"],
        llm_metadata={"source": source, "action": action},
    )
    return {"messages": state["messages"] + [message]}


def guardrail_validator(state: NegotiationState) -> dict:
    last_message = state["messages"][-1]
    _, _, action = parse_offer(last_message["text"])
    price = last_message["extracted_price"]
    quantity = last_message["extracted_quantity"]
    turn = state["turn"] + 1

    vendor_config = state["vendor_config"]
    buyer_config = state["buyer_config"]
    sender = last_message["sender"]

    if sender == "VendorAgent" and price is not None and price < vendor_config["Floor_Price"]:
        status = "TERMINATED"
    elif (
        sender == "BuyerAgent"
        and price is not None
        and price > buyer_config["Buyer_Ceiling_Price"]
    ):
        # Enforced on every offer, not just ACCEPT, mirroring the vendor floor
        # check above. The buyer's system prompt forbids it to "accept or offer"
        # above this bound, so proposing one is already a violation.
        status = "TERMINATED"
    elif turn > MAX_TURNS:
        status = "TERMINATED"
    elif action == "ACCEPT":
        status = "AGREEMENT"
    else:
        status = "NEGOTIATING"

    telemetry.log_message(
        transaction_id=state["transaction_id"],
        conversation_turn=turn,
        sender_type="System",
        sender_id="GuardrailValidator",
        receiver_id="System",
        raw_message=f"status={status} action={action}",
        extracted_price=price,
        extracted_quantity=quantity,
        llm_metadata={"action": action},
    )

    update: dict = {"turn": turn, "status": status}
    if price is not None:
        update["current_price"] = price
    if quantity is not None:
        update["current_quantity"] = quantity
    return update


def _run_payment_tool(state: NegotiationState, *, agent_id: str, tool_name: str, payload: dict, tool_fn) -> dict:
    try:
        result = tool_fn(**payload)
        execution_status = "Success"
        error_message = ""
    except payments.PaymentValidationError as exc:
        result = {}
        execution_status = "ValidationError"
        error_message = str(exc)
    except Exception as exc:
        result = {}
        execution_status = "Failed"
        error_message = str(exc)

    telemetry.log_tool_execution(
        transaction_id=state["transaction_id"],
        agent_id=agent_id,
        tool_name=tool_name,
        payload=payload,
        execution_status=execution_status,
        error_message=error_message,
    )

    return result


def payment_request(state: NegotiationState) -> dict:
    unit_price = state["current_price"]
    quantity = state["current_quantity"]
    payload = {
        "transaction_id": state["transaction_id"],
        "buyer_agent_id": "BuyerAgent",
        "product_id": state["vendor_config"]["Product_ID"],
        "agreed_unit_price": unit_price,
        "quantity": quantity,
        "total_amount": round(unit_price * quantity, 2),
    }

    result = _run_payment_tool(
        state,
        agent_id="VendorAgent",
        tool_name="payment_request",
        payload=payload,
        tool_fn=payments.create_payment_request,
    )

    return {"status": "PAYMENT_PENDING", "invoice": {**payload, **result}}


def payment_authorization(state: NegotiationState) -> dict:
    invoice = dict(state["invoice"] or {})
    payload = {
        "transaction_id": state["transaction_id"],
        "payment_intent_id": invoice.get("payment_intent_id"),
        "payment_method_token": "tok_mock_visa",
        "authorized_amount": invoice.get("total_amount"),
    }

    result = _run_payment_tool(
        state,
        agent_id="BuyerAgent",
        tool_name="payment_authorization",
        payload=payload,
        tool_fn=payments.authorize_payment,
    )

    status = "FULFILLED" if result.get("payment_status") == "succeeded" else "TERMINATED"
    return {"status": status, "invoice": {**invoice, **payload, **result}}


def generate_invoice(state: NegotiationState) -> dict:
    invoice = dict(state["invoice"] or {})
    invoice.update(
        {
            "transaction_id": state["transaction_id"],
            "product_id": state["vendor_config"]["Product_ID"],
            "unit_price": state["current_price"],
            "quantity": state["current_quantity"],
            "total_amount": round(state["current_price"] * state["current_quantity"], 2),
        }
    )
    return {"invoice": invoice}


def route_after_guardrail(state: NegotiationState) -> str:
    if state["status"] == "TERMINATED":
        return "terminated"
    if state["status"] == "AGREEMENT":
        return "agreement"
    last_sender = state["messages"][-1]["sender"]
    return "vendor_agent" if last_sender == "BuyerAgent" else "buyer_agent"


def build_graph():
    graph = StateGraph(NegotiationState)
    graph.add_node("buyer_agent", buyer_agent)
    graph.add_node("vendor_agent", vendor_agent)
    graph.add_node("guardrail_validator", guardrail_validator)
    graph.add_node("payment_request", payment_request)
    graph.add_node("payment_authorization", payment_authorization)
    graph.add_node("generate_invoice", generate_invoice)

    graph.add_edge(START, "buyer_agent")
    graph.add_edge("buyer_agent", "guardrail_validator")
    graph.add_edge("vendor_agent", "guardrail_validator")
    graph.add_edge("payment_request", "payment_authorization")
    graph.add_edge("payment_authorization", "generate_invoice")
    graph.add_edge("generate_invoice", END)

    graph.add_conditional_edges(
        "guardrail_validator",
        route_after_guardrail,
        {
            "buyer_agent": "buyer_agent",
            "vendor_agent": "vendor_agent",
            "agreement": "payment_request",
            "terminated": END,
        },
    )

    return graph.compile()
