"""Tests for the persistence, catalog, auth and stats layers."""

import importlib
import os

import pytest
from fastapi.testclient import TestClient

from app import catalog, security, stats, store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()
    yield
    store.reset()


# ── catalog ───────────────────────────────────────────────────────────────────

class TestCatalog:
    def test_lists_every_product(self):
        body = client.get("/products").json()
        assert {p["product_id"] for p in body["products"]} == set(catalog.PRODUCTS)
        assert body["default"] == catalog.DEFAULT_PRODUCT_ID

    def test_every_product_has_a_viable_price_overlap(self):
        """A buyer ceiling below the vendor floor can never settle."""
        for product in catalog.list_products():
            assert product["has_overlap"], product["product_id"]

    def test_buyer_and_vendor_agree_on_the_product_id(self):
        for product_id in catalog.PRODUCTS:
            vendor, buyer = catalog.get_configs(product_id)
            assert vendor["Product_ID"] == buyer["Target_Product_ID"] == product_id

    def test_unknown_product_raises(self):
        with pytest.raises(catalog.UnknownProductError):
            catalog.get_configs("NOPE-0000")

    def test_config_endpoint_accepts_a_product_id(self):
        response = client.get("/config", params={"product_id": "PROD-2002"})
        assert response.status_code == 200
        assert response.json()["vendor"]["product"]["id"] == "PROD-2002"

    def test_config_endpoint_404s_on_unknown_product(self):
        assert client.get("/config", params={"product_id": "NOPE-0000"}).status_code == 404


# ── multi-product negotiation ─────────────────────────────────────────────────

class TestMultiProductNegotiation:
    def test_starting_without_a_product_uses_the_default(self):
        body = client.post("/negotiations/start", json={}).json()
        assert body["product_id"] == catalog.DEFAULT_PRODUCT_ID

    @pytest.mark.parametrize("product_id", list(catalog.PRODUCTS))
    def test_each_catalog_product_can_settle(self, product_id):
        start = client.post("/negotiations/start", json={"product_id": product_id})
        assert start.status_code == 200
        transaction_id = start.json()["transaction_id"]

        result = client.get(f"/negotiations/{transaction_id}").json()
        assert result["product_id"] == product_id
        assert result["status"] == "FULFILLED"
        assert result["invoice"]["payment_status"] == "succeeded"

    def test_unknown_product_is_rejected(self):
        assert client.post("/negotiations/start", json={"product_id": "NOPE-0000"}).status_code == 404

    def test_concurrent_negotiations_stay_separate(self):
        first = client.post("/negotiations/start", json={"product_id": "PROD-1001"}).json()["transaction_id"]
        second = client.post("/negotiations/start", json={"product_id": "PROD-2002"}).json()["transaction_id"]
        assert first != second
        assert client.get(f"/negotiations/{first}").json()["product_id"] == "PROD-1001"
        assert client.get(f"/negotiations/{second}").json()["product_id"] == "PROD-2002"


# ── persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_negotiation_survives_a_fresh_store_handle(self):
        """The old in-process dict lost everything on restart."""
        transaction_id = client.post("/negotiations/start", json={}).json()["transaction_id"]
        reloaded = store.get_negotiation(transaction_id)
        assert reloaded is not None
        assert reloaded["transaction_id"] == transaction_id

    def test_listing_reflects_created_negotiations(self):
        ids = {client.post("/negotiations/start", json={}).json()["transaction_id"] for _ in range(3)}
        listed = {row["transaction_id"] for row in store.list_negotiations()}
        assert ids <= listed
        assert store.count_negotiations() >= 3

    def test_payment_intents_are_persisted(self):
        transaction_id = client.post("/negotiations/start", json={}).json()["transaction_id"]
        invoice = client.get(f"/negotiations/{transaction_id}").json()["invoice"]
        stored = store.get_payment_intent(invoice["payment_intent_id"])
        assert stored is not None
        assert stored["status"] == "succeeded"

    def test_unknown_negotiation_is_404(self):
        assert client.get("/negotiations/does-not-exist").status_code == 404


# ── auth ──────────────────────────────────────────────────────────────────────

class TestApiKeyAuth:
    def test_open_when_no_key_is_configured(self, monkeypatch):
        monkeypatch.delenv("API_KEY", raising=False)
        assert client.post("/negotiations/start", json={}).status_code == 200

    def test_rejects_a_missing_key_when_configured(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "s3cret")
        assert client.post("/negotiations/start", json={}).status_code == 401

    def test_rejects_a_wrong_key(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "s3cret")
        response = client.post("/negotiations/start", json={}, headers={"X-API-Key": "nope"})
        assert response.status_code == 401

    def test_accepts_the_right_key(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "s3cret")
        response = client.post("/negotiations/start", json={}, headers={"X-API-Key": "s3cret"})
        assert response.status_code == 200

    def test_reads_stay_open(self, monkeypatch):
        """Auth guards spend, not inspection."""
        monkeypatch.setenv("API_KEY", "s3cret")
        assert client.get("/health").status_code == 200
        assert client.get("/products").status_code == 200


class TestCorsConfiguration:
    def test_defaults_to_local_origins_not_wildcard(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        assert "*" not in security.allowed_origins()

    def test_reads_a_comma_separated_list(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example, https://b.example")
        assert security.allowed_origins() == ["https://a.example", "https://b.example"]


# ── stats ─────────────────────────────────────────────────────────────────────

class TestStats:
    def test_empty_store_reports_zeroes_without_dividing_by_zero(self):
        body = client.get("/stats").json()
        assert body["total_negotiations"] == 0
        assert body["convergence_rate"] is None
        assert body["total_settled_value"] == 0.0

    def test_settled_negotiations_are_summarised(self):
        for _ in range(3):
            client.post("/negotiations/start", json={})
        body = client.get("/stats").json()
        assert body["total_negotiations"] == 3
        assert body["by_status"]["FULFILLED"] == 3
        assert body["convergence_rate"] == 1.0
        assert body["avg_turns_to_settle"] > 0
        assert body["avg_agreed_unit_price"] > 0
        assert body["total_settled_value"] > 0

    def test_convergence_rate_excludes_in_flight_runs(self):
        assert stats.summary()["in_flight"] == 0
