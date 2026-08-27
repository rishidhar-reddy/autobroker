# autobroker — portfolio notes

> **⚠️ Before sharing this repo, fill in every `[FILL IN]` below and delete this line.**
> Everything in *My contributions* is verifiable from `git log`. *My role on the original
> build* is yours to state accurately — I have left it blank rather than guess.

---

## What this system is

Two autonomous LLM agents — a Vendor and a Buyer — negotiate the unit price of a
purchase inside a LangGraph state machine. Each turn must end in a structured tag
(`[OFFER price=X.XX quantity=N action=ACCEPT|COUNTER|REJECT]`), which a guardrail node
validates against each side's hard price bounds. When one side accepts, the graph
transitions automatically into a payment flow — create a PaymentIntent, confirm it,
generate an invoice — with no human in the loop.

The interesting problem is making free-form LLM output reliably machine-parseable while
enforcing business constraints the model may try to violate.

**Stack:** Python · LangGraph · FastAPI · React/Vite · ClickHouse telemetry

- Architecture walkthrough → [`docs/SYSTEM-DEEPDIVE.md`](docs/SYSTEM-DEEPDIVE.md)

---

## Provenance

Original implementation by **intimanjunath** and **aditya-dawadikar** across 58 commits
on 2026-06-12, built in roughly 8.5 hours for the Harness Engineering Hackathon. This
repository preserves that full history; the original remains at
[Aditya-Dawadikar/HarnessEngineeringHackathon](https://github.com/Aditya-Dawadikar/HarnessEngineeringHackathon),
tracked here as the `upstream` remote.

29 of the original 58 commits carry Claude Code co-author trailers. That is visible to
anyone reading the history, so it is better said plainly than discovered.

### My role on the original build

[FILL IN — name the components you actually worked on and the problems you solved. If
you did not work on the original hackathon build at all, say so and let the fix below
stand on its own; one real bug found and fixed with tests is a perfectly good story.]

---

## My contributions in this repository

Verifiable with `git log --author="Rishi Dhar"`.

### Found and fixed an asymmetric guardrail (`348a7e8`)

The guardrail enforced the vendor's price floor against **every** offer, but enforced
the buyer's price ceiling **only when the action was ACCEPT**. The buyer's own system
prompt forbids it to *"accept or offer"* above its ceiling, so a `COUNTER` above that
bound was already a violation the graph let through — caught only if the vendor happened
to accept it, which routes straight into the payment flow at a price the buyer had
declared it could not pay.

I wrote the failing test first (it returned `NEGOTIATING` where it should have
terminated), removed the `action == "ACCEPT"` condition so both bounds are enforced
symmetrically, and added an inclusive-bound test so the ceiling itself remains a legal
offer.

Test suite: **50 → 52 tests, all passing.**

### Documented the architecture (`8974686`)

A component-level deep dive traced to specific files and lines: the graph topology and
why the guardrail node is structurally unavoidable rather than advisory, the offer-tag
protocol, the perspective rewrite in `_conversation_messages` that gives each agent a
coherent first-person transcript, and the `NotImplementedError` fallback that makes the
whole graph testable without credentials.

---

## What I would build next

1. Persist negotiations to a database. `NEGOTIATIONS` and `_PAYMENT_INTENTS` are
   in-process dicts, so a restart loses every negotiation and a second worker sees none.
2. Lock CORS to the UI origin — it is currently `allow_origins=["*"]` — and add auth on
   `/negotiations/start`.
3. Parameterize `config.py`, which currently fixes a single vendor/buyer pair.
4. A retry path for malformed LLM output. A missing offer tag yields a `None` price,
   which the guardrail treats as "no constraint violated."
5. A LICENSE file — there is currently none, in this repo or upstream.

---

## Honest limitations

- **Payments are mocked.** `payments.py` simulates Stripe's PaymentIntent lifecycle; it
  is shaped like the real object model but settles nothing. The module says so itself.
- **The README headlines a fine-tuned Qwen3-8B**, while the code defaults to
  `gpt-4.1-mini` (`Backend/app/llm_client.py:31`). The README does disclose the default
  in its env table, but anyone cloning and running this locally gets `gpt-4.1-mini`, or
  the deterministic mock strategy if no key is configured. Know the difference before
  demoing it.
- Built in a single day, so breadth is limited: one product, one buyer, one vendor.
