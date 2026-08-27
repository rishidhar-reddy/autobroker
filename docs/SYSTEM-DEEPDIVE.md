# Agentic Negotiation Platform — Engineering Deep Dive

> A component-level walkthrough of how two LLM agents negotiate a deal and settle payment.
> Written from a full read of the source; every claim below is traceable to a file and line.

---

## 1. What the system actually does

Two autonomous agents — a Vendor and a Buyer — negotiate the unit price of a product
inside a LangGraph state machine. Each turn, an agent emits a natural-language message
that **must** terminate in a structured tag:

```
[OFFER price=X.XX quantity=N action=ACCEPT|COUNTER|REJECT]
```

A guardrail node parses that tag and validates the offer against each side's hard
constraints. When one side accepts, the graph transitions automatically into a payment
flow — create a PaymentIntent, confirm it, generate an invoice — with no human in the loop.

The interesting engineering problem here is **making an LLM's free-form output
machine-parseable without losing the natural language**, and then enforcing business
constraints the model might violate.

---

## 2. Graph topology

Built in `Backend/app/graph.py:364-391`:

```
START ──> buyer_agent ──> guardrail_validator ──┬──> vendor_agent ──┐
                                                │                   │
          ┌─────────────────────────────────────┘   (loops back) ───┘
          │
          ├──> [agreement]  ──> payment_request ──> payment_authorization
          │                                              │
          │                                              v
          │                                        generate_invoice ──> END
          └──> [terminated] ──> END
```

Every agent turn funnels through `guardrail_validator` before routing continues
(`route_after_guardrail`, line 355). There is no path where an offer reaches the payment
flow without passing validation — the guardrail is structurally unavoidable rather than a
politely-requested check. That is the correct way to build this.

---

## 3. The offer protocol

### Parsing

`OFFER_PATTERN` (line 25) is a strict regex requiring price, quantity, and action in a
fixed order. `parse_offer` (line 66) returns a `(price, quantity, action)` triple, or
`(None, None, None)` on no match.

Every message is wrapped by `_build_message` (line 73), which parses the tag at
construction time and stores `extracted_price` / `extracted_quantity` **alongside** the
raw text. Structured data and human-readable narrative travel together in the same
`Message` TypedDict (line 32) — so the UI can render the conversation while the graph
reasons over numbers.

### Prompt design

`_build_system_prompt` (line 118) gives each side its role, quantity, and a *hard*
price bound, then appends `_NEGOTIATION_INSTRUCTIONS` (line 108) specifying the tag
format and the exact semantics of each action.

`_conversation_messages` (line 141) does something subtle and correct: it rewrites the
shared transcript **from the perspective of the agent about to speak** — that agent's own
prior messages become `assistant` turns, the counterparty's become `user` turns. Each
agent therefore sees a coherent first-person dialogue rather than a third-person log.

---

## 4. Guardrail semantics

`guardrail_validator` (line 224) resolves status in strict precedence order:

| Condition | Resulting status |
|---|---|
| Vendor offers below its `Floor_Price` | `TERMINATED` |
| Buyer **accepts** above its `Buyer_Ceiling_Price` | `TERMINATED` |
| `turn > MAX_TURNS` (10) | `TERMINATED` |
| `action == ACCEPT` | `AGREEMENT` |
| otherwise | `NEGOTIATING` |

**An asymmetry that was here, and is now fixed:** the vendor floor was checked on *any*
offer, but the buyer ceiling only when `action == "ACCEPT"`. A buyer could therefore
*propose* a price above its own ceiling and only be caught if it later accepted one —
even though its system prompt forbids it to "accept **or offer**" above that bound.
The check now mirrors the vendor's and applies to every offer, covered by
`test_guardrail_terminates_when_buyer_counters_above_ceiling` and an inclusive-bound
test asserting the ceiling itself remains a legal offer.

The turn cap at `MAX_TURNS = 10` guarantees termination, so the graph cannot loop forever.

---

## 5. LLM integration and the mock fallback

`Backend/app/llm_client.py` posts to Pioneer.ai's OpenAI-compatible
`/v1/chat/completions` with an `X-API-Key` header, 30-second timeout.

The fallback path is the design decision worth explaining:

- With no API key, `generate` raises `NotImplementedError` (line 36).
- `_llm_offer_text` (`graph.py:155`) catches exactly that exception and returns `None`.
- Both agent nodes then fall back to `_next_offer` (line 91) — a deterministic strategy
  that moves toward the counterparty's last offer and accepts once the gap is within
  `CONVERGENCE_THRESHOLD` (0.5).

Crucially, the message records which path produced it: `source` is tagged
`"promise_platform"` or `"mock_llm"` and shipped to telemetry (line 189). The system is
honest with itself about whether real inference happened.

This makes the whole graph testable with zero credentials — which is why the test suite
can be meaningful without network access.

**Be ready to answer this:** the README headlines a fine-tuned **Qwen3-8B** adapter, while
`PROMISE_MODEL` defaults to `gpt-4.1-mini` (`llm_client.py:31`, and `.env.example:5`). The
README does disclose the default in its env table, and states the Qwen adapter is what
production uses — but anyone cloning and running this locally gets `gpt-4.1-mini`, or the
mock if unconfigured. Know that distinction before demoing.

---

## 6. Payment flow

`Backend/app/payments.py` mocks Stripe's PaymentIntent lifecycle — and the module docstring
says so plainly, which is the right call.

- `create_payment_request` mints a `pi_mock_*` intent in `requires_confirmation`,
  amount in cents, held in an in-process dict.
- `authorize_payment` looks it up, **validates the amount matches**, and transitions to
  `succeeded`. Unknown intent or amount mismatch raises `PaymentValidationError`.

`_run_payment_tool` (`graph.py:271`) is a clean wrapper: it distinguishes
`PaymentValidationError` (→ `"ValidationError"`) from unexpected exceptions
(→ `"Failed"`), logs both to telemetry, and returns `{}` rather than propagating. A payment
failure degrades the negotiation to `TERMINATED` instead of crashing the graph.

The mock is shaped like the real Stripe object model, so swapping in the SDK is a
contained change.

---

## 7. Test coverage

734 lines of tests against 990 lines of application code — a strong ratio, and better than
most projects of this size:

| File | Target |
|---|---|
| `test_graph.py` (314) | State machine, routing, guardrails |
| `test_telemetry.py` (153) | ClickHouse logging |
| `test_llm_client.py` (96) | Client and fallback behavior |
| `test_payments.py` (72) | PaymentIntent lifecycle, validation errors |
| `test_main.py`, `test_negotiations.py`, `test_config.py` | API surface |

The deterministic mock strategy is what makes the state machine testable end to end.

---

## 8. Known gaps

| Gap | Detail |
|---|---|
| **Payments are mocked** | Intentional and documented, but it is not a real settlement. |
| **Single-host persistence** | SQLite is durable and shared across workers on one machine, but does not span hosts. Postgres is the next step if this ever runs on more than one. |
| **No rate limiting** | The API key gates *who* can start a negotiation, not *how many* they can start. |
| **Mock strategy is deterministic** | Without credentials both agents converge by midpoint arithmetic, so the transcript is reproducible but not a real language-model negotiation. |
| **No LICENSE** | Neither a file nor a declaration, here or upstream. |

### Closed since the first review

These were listed as gaps and have since been fixed — see the git history.

| Was | Now |
|---|---|
| Buyer ceiling enforced only on `ACCEPT` | Enforced on every offer, symmetric with the vendor floor |
| All state in process dicts | SQLite-backed via `app/store.py`; survives restart, shared across workers |
| `allow_origins=["*"]` | Driven by `ALLOWED_ORIGINS`, defaulting to local dev origins |
| No authentication | `API_KEY` guards mutating endpoints with a constant-time compare |
| One hardcoded vendor/buyer pair | `app/catalog.py` with three products and a `product_id` parameter |
| Telemetry written but never read | `GET /stats` aggregates it; the UI renders it |

### What I would build next

1. Postgres behind the same `store.py` interface, for multi-host deployment.
2. Per-key rate limiting on `/negotiations/start`.
3. A retry path for malformed LLM output — a missing tag yields a `None` price,
   which the guardrail currently treats as "no constraint violated".
4. Server-sent events instead of 1-second polling.

## 9. Provenance and attribution

Original implementation by **intimanjunath** and **aditya-dawadikar** across 58 commits on
2026-06-12, built in roughly 8.5 hours (12:37 → 21:15) for the Harness Engineering
Hackathon. 29 of those commits carry Claude Code co-author trailers, so this was an
AI-assisted build — worth stating plainly, since it is visible in the history to anyone
who looks.

This document is my own technical analysis of that system.
