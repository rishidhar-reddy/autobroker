import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import catalog, security, stats, store
from app.config import BUYER_CONFIG, VENDOR_CONFIG
from app.graph import NegotiationState, build_graph, build_initial_state

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    security.warn_if_unprotected()
    yield


app = FastAPI(
    title="Agentic Negotiation & Procurement Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=security.allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

_GRAPH = build_graph()


class StartNegotiationRequest(BaseModel):
    product_id: str | None = Field(
        default=None,
        description="Catalog product to negotiate. Defaults to the catalog default.",
    )


def run_negotiation(transaction_id: str) -> None:
    """Drive the graph to completion, persisting after every step.

    Persisting each streamed state rather than only the final one means a crash
    mid-negotiation leaves a readable partial transcript instead of nothing.
    """
    state = store.get_negotiation(transaction_id)
    if state is None:
        logger.error("Negotiation %s vanished before it could run", transaction_id)
        return

    try:
        for updated_state in _GRAPH.stream(state, stream_mode="values"):
            store.save_negotiation(updated_state)
    except Exception:
        logger.exception("Negotiation %s failed", transaction_id)
        state = store.get_negotiation(transaction_id) or state
        state["status"] = "TERMINATED"
        store.save_negotiation(state)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/products")
def list_products():
    return {"products": catalog.list_products(), "default": catalog.DEFAULT_PRODUCT_ID}


@app.post("/negotiations/start", dependencies=[Depends(security.require_api_key)])
def start_negotiation(background_tasks: BackgroundTasks, request: StartNegotiationRequest | None = None):
    product_id = request.product_id if request else None

    try:
        vendor_config, buyer_config = catalog.get_configs(product_id)
    except catalog.UnknownProductError:
        raise HTTPException(status_code=404, detail=f"Unknown product_id: {product_id!r}")

    transaction_id = str(uuid.uuid4())
    store.save_negotiation(build_initial_state(transaction_id, vendor_config, buyer_config))
    background_tasks.add_task(run_negotiation, transaction_id)

    return {"transaction_id": transaction_id, "product_id": vendor_config["Product_ID"]}


@app.get("/negotiations")
def list_negotiations(limit: int = Query(default=20, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    return {
        "negotiations": store.list_negotiations(limit=limit, offset=offset),
        "total": store.count_negotiations(),
    }


@app.get("/stats")
def get_stats():
    return stats.summary()


def _config_payload(vendor_config: dict, buyer_config: dict) -> dict:
    v, b = vendor_config, buyer_config
    return {
        "vendor": {
            "agent_id": v["agent_id"],
            "company": v["company"],
            "product": {
                "id": v["Product_ID"],
                "name": v["product_name"],
                "description": v["product_description"],
                "unit": v["product_unit"],
            },
            "stock_quantity": v["Stock_Quantity"],
            "floor_price": v["Floor_Price"],
            "ceiling_price": v["Ceiling_Price"],
        },
        "buyer": {
            "agent_id": b["agent_id"],
            "company": b["company"],
            "product": {
                "id": b["Target_Product_ID"],
                "name": b["product_name"],
                "unit": b["product_unit"],
            },
            "desired_quantity": b["Desired_Quantity"],
            "floor_price": b["Buyer_Floor_Price"],
            "ceiling_price": b["Buyer_Ceiling_Price"],
        },
    }


@app.get("/config")
def get_config(product_id: str | None = None):
    if product_id is None:
        return _config_payload(VENDOR_CONFIG, BUYER_CONFIG)
    try:
        vendor_config, buyer_config = catalog.get_configs(product_id)
    except catalog.UnknownProductError:
        raise HTTPException(status_code=404, detail=f"Unknown product_id: {product_id!r}")
    return _config_payload(vendor_config, buyer_config)


@app.get("/negotiations/{transaction_id}")
def get_negotiation(transaction_id: str):
    state: NegotiationState | None = store.get_negotiation(transaction_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    return {
        "transaction_id": state["transaction_id"],
        "status": state["status"],
        "turn": state["turn"],
        "product_id": (state.get("vendor_config") or {}).get("Product_ID"),
        "messages": state["messages"],
        "invoice": state["invoice"],
    }
