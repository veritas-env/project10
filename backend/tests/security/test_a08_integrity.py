"""A08 Integrity: clients can't set server-owned fields."""

from __future__ import annotations

import pytest

from tests.conftest import make_client


@pytest.mark.parametrize("extra", [{"workspace_id": "00000000-0000-0000-0000-000000000000"}, {"id": "00000000-0000-0000-0000-000000000000"}])
def test_product_rejects_server_owned_fields(app, world, extra):
    assert world.bob.client.post(world.url("/products"), json={"sku": "MA-1", "name": "x", **extra}).status_code == 422


@pytest.mark.parametrize("extra", [{"status": "failed"}, {"reference": "HACK"}])
def test_transfer_rejects_status_and_reference(app, world, extra):
    body = {"product_id": str(world.product_a), "from_location_id": str(world.ids["loc1_a"]),
            "to_location_id": str(world.ids["loc2_a"]), "quantity": 1, **extra}
    assert world.alice.client.post(world.url("/transfers"), json=body).status_code == 422


def test_login_rejects_extra_fields(app, world):
    r = make_client(app).post("/api/v1/auth/login", json={"email": world.bob.email, "password": world.bob.password, "is_platform_admin": True})
    assert r.status_code == 422
