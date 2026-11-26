"""A05 Injection: search is parameterised; output is JSON."""

from __future__ import annotations

import pytest

SQLI = ["' OR '1'='1", "'; DROP TABLE products; --", "%' AND pg_sleep(3) IS NULL AND '%'='", "%", "_"]


@pytest.mark.parametrize("payload", SQLI)
def test_product_search_is_parameterised(app, world, payload):
    assert world.alice.client.get(world.url("/products"), params={"q": payload}).json() == []


def test_sku_format_enforced(app, world):
    assert world.alice.client.post(world.url("/products"), json={"sku": "a'--", "name": "x"}).status_code == 422


def test_html_is_stored_as_data(app, world):
    payload = "<script>alert(1)</script>"
    r = world.alice.client.post(world.url("/products"), json={"sku": "XSS-1", "name": payload})
    assert r.status_code == 201 and r.json()["name"] == payload


def test_validation_errors_do_not_reflect_input(app, world):
    marker = "<svg/onload=alert(1)>"
    r = world.alice.client.post(world.url("/products"), json={"sku": marker, "name": "x"})
    assert r.status_code == 422 and "onload" not in r.text
