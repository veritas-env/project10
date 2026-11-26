"""A01 Broken Access Control: routes covered, warehouses isolated, roles hold, CSRF enforced."""

from __future__ import annotations

import re
import uuid

import pytest

from tests.conftest import make_client

PUBLIC = {("POST", "/api/v1/auth/login"), ("POST", "/api/v1/invitations/preview"), ("POST", "/api/v1/invitations/register")}
ADMIN_PREFIX = "/api/v1/admin/"
BODIES = {
    ("POST", "/api/v1/workspaces/{workspace_id}/locations"): {"json": {"code": "NEWBIN"}},
    ("POST", "/api/v1/workspaces/{workspace_id}/products"): {"json": {"sku": "NEW-1", "name": "x"}},
    ("PATCH", "/api/v1/workspaces/{workspace_id}/products/{product_id}"): {"json": {"name": "x"}},
    ("POST", "/api/v1/workspaces/{workspace_id}/products/{product_id}/adjust"): "ADJUST",
    ("POST", "/api/v1/workspaces/{workspace_id}/transfers"): "TRANSFER",
    ("POST", "/api/v1/workspaces/{workspace_id}/purchase-orders"): "PO",
    ("POST", "/api/v1/workspaces/{workspace_id}/purchase-orders/{po_id}/receive"): {},
    ("PUT", "/api/v1/workspaces/{workspace_id}/members/{user_id}"): {"json": {"role": "viewer"}},
    ("POST", "/api/v1/workspaces/{workspace_id}/invitations"): {"json": {"email": "x@lab.test", "role": "viewer"}},
    ("DELETE", "/api/v1/workspaces/{workspace_id}/invitations/{invitation_id}"): {},
    ("POST", "/api/v1/auth/password"): {"json": {"current_password": "x", "new_password": "y"}},
    ("POST", "/api/v1/invitations/accept"): {"json": {"token": "x" * 43}},
}


def operations(app):
    ops = []
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                ops.append((method.upper(), path))
    return sorted(ops)


def fill(path, w, ws="a", res="a"):
    values = {"workspace_id": w.ws_a if ws == "a" else w.ws_b, "product_id": w.ids[f"product_{res}"],
              "po_id": w.ids.get("po_a", uuid.uuid4()), "invitation_id": w.ids["invitation_a"],
              "user_id": w.bob.id, "alert_id": 1}

    def sub(m):
        if m.group(1) not in values:
            pytest.fail(f"no test value for {{{m.group(1)}}}")
        return str(values[m.group(1)])

    return re.sub(r"{(\w+)}", sub, path)


def call(client, method, path, template, w, res="a"):
    body = BODIES.get((method, template), {})
    if body == "ADJUST":
        body = {"json": {"location_id": str(w.ids[f"loc1_{res}"]), "delta": 1}}
    elif body == "TRANSFER":
        body = {"json": {"product_id": str(w.ids[f"product_{res}"]), "from_location_id": str(w.ids[f"loc1_{res}"]),
                         "to_location_id": str(w.ids[f"loc2_{res}"]), "quantity": 1}}
    elif body == "PO":
        body = {"json": {"supplier": "ACME", "product_id": str(w.ids[f"product_{res}"]), "location_id": str(w.ids[f"loc1_{res}"]), "quantity": 1}}
    return client.request(method, path, **body)


def test_route_table_is_known(app):
    assert len(operations(app)) >= 20


def test_every_non_public_route_requires_auth(app, world):
    anon = make_client(app)
    for method, path in operations(app):
        if (method, path) in PUBLIC:
            continue
        assert call(anon, method, fill(path, world), path, world).status_code == 401, f"{method} {path}"


def test_every_warehouse_route_hides_other_warehouses(app, world):
    for method, path in operations(app):
        if "{workspace_id}" not in path:
            continue
        r = call(world.mallory.client, method, fill(path, world), path, world)
        assert r.status_code == 404, f"{method} {path} -> {r.status_code}"


def test_resource_ids_cannot_cross_warehouses(app, world):
    for method, path in operations(app):
        if "{workspace_id}" not in path or path.count("{") < 2 or "{user_id}" in path or "{invitation_id}" in path or "{po_id}" in path:
            continue
        r = call(world.mallory.client, method, fill(path, world, ws="b", res="a"), path, world, res="a")
        assert r.status_code in (404, 422), f"{method} {path} cross-warehouse -> {r.status_code}"


def test_admin_routes_hidden(app, world):
    for method, path in operations(app):
        if not path.startswith(ADMIN_PREFIX):
            continue
        assert call(world.alice.client, method, fill(path, world), path, world).status_code == 404
    assert world.root.client.get("/api/v1/admin/alerts").status_code == 200


@pytest.mark.parametrize("who,method,path,body,status", [
    ("vera", "POST", "/products", {"sku": "V-1", "name": "x"}, 403),
    ("vera", "POST", "/transfers", "T", 403),
    ("bob", "POST", "/locations", {"code": "BOBBIN"}, 403),
    ("bob", "POST", "/products", {"sku": "B-1", "name": "x"}, 201),
    ("adam", "POST", "/locations", {"code": "MGRBIN"}, 201),
])
def test_role_matrix(app, world, who, method, path, body, status):
    url = world.url(path)
    if body == "T":
        body = {"product_id": str(world.product_a), "from_location_id": str(world.ids["loc1_a"]),
                "to_location_id": str(world.ids["loc2_a"]), "quantity": 1}
    r = getattr(world, who).client.request(method, url, json=body)
    assert r.status_code == status, r.text


def test_csrf_required_on_writes(app, world):
    c = make_client(app)
    c.cookies = world.alice.client.cookies
    url = world.url("/locations")
    assert c.post(url, json={"code": "C1"}).status_code == 403
    assert c.post(url, json={"code": "C2"}, headers={"X-CSRF-Token": world.alice.csrf}).status_code == 201


@pytest.mark.parametrize("ctype", ["application/x-www-form-urlencoded", "text/plain"])
def test_cross_site_form_refused(app, world, ctype):
    assert world.alice.client.post(world.url("/locations"), content=b"x=1", headers={"Content-Type": ctype}).status_code == 415


def test_transfer_cannot_reference_other_warehouse(app, world):
    r = world.alice.client.post(world.url("/transfers"), json={"product_id": str(world.product_b),
        "from_location_id": str(world.ids["loc1_a"]), "to_location_id": str(world.ids["loc2_a"]), "quantity": 1})
    assert r.status_code == 404


def test_unknown_ids(app, world):
    assert world.alice.client.get(world.url(f"/products/{uuid.uuid4()}")).status_code == 404
    assert world.alice.client.get(world.url("/products/1%20OR%201=1")).status_code == 422
