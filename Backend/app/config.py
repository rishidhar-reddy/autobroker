"""Default domain configuration for the negotiation POC.

The catalog in catalog.py is the source of truth now that the service supports
more than one product. These names are kept because the graph, the tests and
the /config endpoint all import them, and they resolve to the default product.
"""

from app.catalog import DEFAULT_PRODUCT_ID, get_configs

VENDOR_CONFIG, BUYER_CONFIG = get_configs(DEFAULT_PRODUCT_ID)
