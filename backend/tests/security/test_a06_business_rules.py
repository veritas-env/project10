"""A06 Insecure Design: warehouse rules (other than the lab scenario)."""

from __future__ import annotations

from tests.conftest import make_client


def test_sku_unique_per_warehouse(app, world):
    assert world.alice.client.post(world.url("/products"), json={"sku": "SKU-A1", "name": "dup"}).status_code == 409
    assert world.mallory.client.post(world.url("/products", "b"), json={"sku": "SKU-A1", "name": "ok"}).status_code == 201


def test_adjust_cannot_go_negative(app, world):
    r = world.alice.client.post(world.url(f"/products/{world.product_a}/adjust"),
                                json={"location_id": str(world.ids["loc1_a"]), "delta": -9999})
    assert r.status_code == 409


def test_transfer_same_location_rejected(app, world):
    r = world.alice.client.post(world.url("/transfers"), json={"product_id": str(world.product_a),
        "from_location_id": str(world.ids["loc1_a"]), "to_location_id": str(world.ids["loc1_a"]), "quantity": 1})
    assert r.status_code == 422


def test_location_code_unique(app, world):
    assert world.alice.client.post(world.url("/locations"), json={"code": "ABIN1"}).status_code == 409


def test_po_received_once(app, world):
    po = world.alice.client.post(world.url("/purchase-orders"), json={"supplier": "ACME", "product_id": str(world.product_a),
                                 "location_id": str(world.ids["loc1_a"]), "quantity": 20}).json()
    assert world.alice.client.post(world.url(f"/purchase-orders/{po['id']}/receive")).status_code == 200
    assert world.alice.client.post(world.url(f"/purchase-orders/{po['id']}/receive")).status_code == 409


def test_invitation_single_use(app, world):
    body = {"token": world.invite_token, "display_name": "N", "password": "Brand-new-Passphrase-42"}
    assert make_client(app).post("/api/v1/invitations/register", json=body).status_code == 201
    assert make_client(app).post("/api/v1/invitations/register", json=body).status_code == 404


def test_limits(app, world):
    assert world.alice.client.get(world.url("/products"), params={"limit": 10_000}).status_code == 422
    assert world.alice.client.post(world.url("/products"), json={"sku": "L-1", "name": "x" * 200}).status_code == 422


def test_transfer_moves_stock_between_locations(app, world):
    c = world.alice.client
    r = c.post(world.url("/transfers"), json={"product_id": str(world.product_a), "from_location_id": str(world.ids["loc1_a"]),
                                              "to_location_id": str(world.ids["loc2_a"]), "quantity": 20})
    assert r.status_code == 201 and r.json()["status"] == "completed"
    levels = {lv["location_id"]: lv["quantity"] for lv in c.get(world.url(f"/products/{world.product_a}")).json()["levels"]}
    assert levels[str(world.ids["loc1_a"])] == 30 and levels[str(world.ids["loc2_a"])] == 20
