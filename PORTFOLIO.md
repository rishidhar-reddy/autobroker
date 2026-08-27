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

Verifiable with `git log --author="Rishidhar Reddy Garlapati"`.

### Found and fixed an asymmetric guardrail

> commit `fix: enforce the buyer price ceiling on every offer, not only on ACCEPT`

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

### Documented the architecture

> commit `docs: add engineering deep dive of the negotiation graph and payment flow`

A component-level deep dive traced to specific files and lines: the graph topology and
why the guardrail node is structurally unavoidable rather than advisory, the offer-tag
protocol, the perspective rewrite in `_conversation_messages` that gives each agent a
coherent first-person transcript, and the `NotImplementedError` fallback that makes the
whole graph testable without credentials.

### Built the platform layer out (`feat: persistence, product catalog, API auth and negotiation stats`)

Four gaps that blocked building anything on top of the service:

- **Persistence.** Negotiations and payment intents lived in module dicts, so
  every run died with the process and a second worker saw none of the first
  worker's state — `GET /negotiations/{id}` would 404 at random behind any real
  deployment. Now SQLite-backed, persisting every streamed step so a crash
  leaves a readable partial transcript.
- **Product catalog.** One hardcoded vendor/buyer pair became a three-product
  catalog with an optional `product_id`, and a `has_overlap` flag that makes an
  unsettleable price range visible before you start.
- **Security.** `allow_origins=["*"]` and no auth became configurable origins
  defaulting to local, plus an `API_KEY` guard using a constant-time compare.
  Reads stay open — the point is to guard spend, not inspection.
- **Observability.** `telemetry.py` wrote every message to ClickHouse and
  nothing ever read it back. `GET /stats` aggregates convergence rate, average
  turns to settle, and deal values.

26 new tests. Suite 52 → 78.

### Rebuilt the frontend (`feat(ui): rebuild the interface on Tailwind with a component system`)

880 lines of bare React over hand-rolled CSS, rebuilt on Tailwind v4 with
shadcn-style primitives composed via `cva` and `tailwind-merge`. Product
selection, a two-sided transcript that lifts the structured offer tag out of the
prose, live stats, and OS-following theming with a persisted manual override.

Status is never colour-alone — every state pairs a reserved status colour with an
icon and a label, which matters because two of those steps sit below 3:1 on the
light surface by design. The stats are stat tiles rather than charts: six
single-value measures with no series and no time axis.

Verified against a live backend in both themes. Two layout bugs were caught only
by looking at the render — long payment ids overflowed the invoice card
(`truncate` needs `min-w-0` on both the grid item *and* the flex child), and the
transcript clipped its newest offer until the scroll was deferred a frame and
moved onto the container itself.

---

## What I would build next

1. Postgres behind the same `store.py` interface, so the service can run on more
   than one host.
2. Per-key rate limiting on `/negotiations/start` — the API key gates who can
   start a run, not how many.
3. A retry path for malformed LLM output. A missing offer tag yields a `None`
   price, which the guardrail treats as "no constraint violated."
4. Server-sent events instead of 1-second polling.
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
