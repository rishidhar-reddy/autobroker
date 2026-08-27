"""Product catalog.

The POC hardcoded a single vendor/buyer pair in config.py, so the service could
only ever run one negotiation scenario. This module holds the same shape keyed
by product, and config.py re-exports the default entry so existing imports and
the /config endpoint keep working unchanged.

Each entry carries the graph keys the negotiation state machine reads
(Product_ID, Floor_Price, ...) alongside display keys the UI renders.
"""

from typing import Any

DEFAULT_PRODUCT_ID = "PROD-1001"

PRODUCTS: dict[str, dict[str, Any]] = {
    "PROD-1001": {
        "vendor": {
            "Product_ID": "PROD-1001",
            "Stock_Quantity": 500,
            "Floor_Price": 8.00,
            "Ceiling_Price": 12.00,
            "agent_id": "VendorAgent",
            "company": "Acme Supplies Co.",
            "product_name": "Industrial Widget",
            "product_description": "Heavy-duty steel widget, grade A",
            "product_unit": "pcs",
        },
        "buyer": {
            "Target_Product_ID": "PROD-1001",
            "Desired_Quantity": 200,
            "Buyer_Floor_Price": 7.00,
            "Buyer_Ceiling_Price": 10.00,
            "agent_id": "BuyerAgent",
            "company": "BuildCorp Ltd.",
            "product_name": "Industrial Widget",
            "product_unit": "pcs",
        },
    },
    "PROD-2002": {
        "vendor": {
            "Product_ID": "PROD-2002",
            "Stock_Quantity": 120,
            "Floor_Price": 45.00,
            "Ceiling_Price": 68.00,
            "agent_id": "VendorAgent",
            "company": "Northwind Materials",
            "product_name": "Titanium Bracket",
            "product_description": "Aerospace-grade titanium mounting bracket",
            "product_unit": "pcs",
        },
        "buyer": {
            "Target_Product_ID": "PROD-2002",
            "Desired_Quantity": 60,
            "Buyer_Floor_Price": 40.00,
            "Buyer_Ceiling_Price": 58.00,
            "agent_id": "BuyerAgent",
            "company": "Vertex Aerospace",
            "product_name": "Titanium Bracket",
            "product_unit": "pcs",
        },
    },
    "PROD-3003": {
        "vendor": {
            "Product_ID": "PROD-3003",
            "Stock_Quantity": 5000,
            "Floor_Price": 0.85,
            "Ceiling_Price": 1.60,
            "agent_id": "VendorAgent",
            "company": "Pallas Polymers",
            "product_name": "Sealing Gasket",
            "product_description": "Nitrile rubber gasket, 40mm",
            "product_unit": "pcs",
        },
        "buyer": {
            "Target_Product_ID": "PROD-3003",
            "Desired_Quantity": 2500,
            "Buyer_Floor_Price": 0.70,
            "Buyer_Ceiling_Price": 1.30,
            "agent_id": "BuyerAgent",
            "company": "Redline Automotive",
            "product_name": "Sealing Gasket",
            "product_unit": "pcs",
        },
    },
}


class UnknownProductError(KeyError):
    """Raised when a negotiation is requested for a product not in the catalog."""


def get_product(product_id: str | None = None) -> dict[str, Any]:
    """Return the vendor/buyer config pair for a product."""
    resolved = product_id or DEFAULT_PRODUCT_ID
    if resolved not in PRODUCTS:
        raise UnknownProductError(resolved)
    return PRODUCTS[resolved]


def get_configs(product_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    product = get_product(product_id)
    return product["vendor"], product["buyer"]


def describe(product_id: str) -> dict[str, Any]:
    """Public shape for the /products listing."""
    vendor, buyer = get_configs(product_id)
    return {
        "product_id": product_id,
        "name": vendor["product_name"],
        "description": vendor["product_description"],
        "unit": vendor["product_unit"],
        "vendor_company": vendor["company"],
        "buyer_company": buyer["company"],
        "stock_quantity": vendor["Stock_Quantity"],
        "desired_quantity": buyer["Desired_Quantity"],
        # The zone of possible agreement — empty when the buyer cannot reach
        # the vendor's floor, which makes an impossible deal visible up front.
        "vendor_floor_price": vendor["Floor_Price"],
        "buyer_ceiling_price": buyer["Buyer_Ceiling_Price"],
        "has_overlap": buyer["Buyer_Ceiling_Price"] >= vendor["Floor_Price"],
    }


def list_products() -> list[dict[str, Any]]:
    return [describe(pid) for pid in PRODUCTS]
