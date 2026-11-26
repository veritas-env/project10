"""Synthetic demo data for StockPilot: two warehouses with staff, locations, products,
stock and some transfers. Every name and figure is invented.
Used by `python -m app.cli seed-demo`."""

from __future__ import annotations

import random
import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.security import hash_password
from .models import Activity, Location, Membership, Product, PurchaseOrder, StockLevel, StockMove, Transfer, User, Workspace

DOMAIN = "stockpilot.lab"
WAREHOUSES = [
    ("Northgate Distribution", "Regional distribution centre.", "NG",
     [("priya.raman", "Priya Raman", "Warehouse Manager", "owner"), ("scanner-a", "Alex Morgan", "Stock Clerk", "member"),
      ("marcus.webb", "Marcus Webb", "Shift Supervisor", "manager"), ("elena.kovacs", "Elena Kovacs", "Stock Clerk", "member"),
      ("owen.price", "Owen Price", "Auditor", "viewer")],
     ["Cordless Drill 18V", "Hex Bolt M8 (100pk)", "Safety Goggles", "Work Gloves L", "LED Floodlight 50W", "Extension Lead 10m",
      "Masking Tape 50mm", "Cable Ties 200mm (100pk)", "Paint Roller Set", "Tarpaulin 4x6m", "Wheelbarrow 90L", "Step Ladder 3-tread"]),
    ("Southbank Logistics", "City fulfilment hub.", "SB",
     [("scanner-b", "Jordan Blake", "Operations Lead", "owner"), ("amara.osei", "Amara Osei", "Supervisor", "manager"),
      ("lucas.ferreira", "Lucas Ferreira", "Picker", "member")],
     ["Padded Envelope C5 (50pk)", "Packing Tape Clear", "Bubble Wrap 500mm", "Shipping Label 4x6 (500)", "Box Small (25pk)",
      "Box Medium (25pk)", "Stretch Wrap 400mm", "Marker Pen Black (10pk)", "Utility Knife", "Pallet Wrap Dispenser"]),
]


def _ref(prefix) -> str:
    return prefix + "".join(secrets.choice(string.digits) for _ in range(6))


def seed_demo(s: Session, upload_dir=None, seed: int = 2026) -> dict[str, str]:
    if s.scalar(select(Workspace.id).limit(1)) is not None:
        raise RuntimeError("database already has warehouses; reset it first")
    rnd = random.Random(seed)
    now = datetime.now(timezone.utc)
    passwords: dict[str, str] = {}

    def user(local, name, title, admin=False):
        pw = "Lab-" + secrets.token_urlsafe(18)
        u = User(email=f"{local}@{DOMAIN}", display_name=name, job_title=title, password_hash=hash_password(pw), is_platform_admin=admin)
        s.add(u)
        s.flush()
        passwords[u.email] = pw
        return u

    user("platform-admin", "Platform Administrator", "IT Security", admin=True)
    for name, desc, prefix, people, product_names in WAREHOUSES:
        ws = Workspace(name=name, description=desc)
        s.add(ws)
        s.flush()
        staff = []
        for local, pname, title, role in people:
            u = user(local, pname, title)
            s.add(Membership(workspace_id=ws.id, user_id=u.id, role=role))
            if role != "viewer":
                staff.append(u)
        locations = []
        for aisle in ["A", "B", "C"]:
            for bay in range(1, 4):
                loc = Location(workspace_id=ws.id, code=f"{aisle}-{bay:02d}", name=f"Aisle {aisle} Bay {bay}")
                s.add(loc)
                locations.append(loc)
        recv = Location(workspace_id=ws.id, code="RECV", name="Receiving")
        s.add(recv)
        locations.append(recv)
        s.flush()

        products = []
        for i, pname in enumerate(product_names):
            p = Product(workspace_id=ws.id, sku=f"{prefix}-{1000 + i * 3}", name=pname,
                        unit=rnd.choice(["each", "each", "box", "pack"]), reorder_level=rnd.choice([10, 20, 25, 40]))
            s.add(p)
            s.flush()
            products.append(p)
            for loc in rnd.sample(locations[:-1], k=rnd.randint(1, 3)):
                qty = rnd.randint(5, 200)
                s.add(StockLevel(workspace_id=ws.id, product_id=p.id, location_id=loc.id, quantity=qty))
                s.add(StockMove(workspace_id=ws.id, product_id=p.id, location_id=loc.id, delta=qty, reason="receipt",
                                note="opening stock", created_by=staff[0].id, at=now - timedelta(days=30)))

        for _ in range(rnd.randint(12, 20)):
            p = rnd.choice(products)
            locs = [sl for sl in s.scalars(select(StockLevel).where(StockLevel.product_id == p.id, StockLevel.quantity > 5))]
            if len(locs) < 1:
                continue
            src = rnd.choice(locs)
            dst = rnd.choice([l for l in locations if l.id != src.location_id])
            qty = rnd.randint(1, min(src.quantity, 20))
            src.quantity -= qty
            dl = s.scalar(select(StockLevel).where(StockLevel.product_id == p.id, StockLevel.location_id == dst.id))
            if dl is None:
                dl = StockLevel(workspace_id=ws.id, product_id=p.id, location_id=dst.id, quantity=0)
                s.add(dl)
            dl.quantity += qty
            t = Transfer(workspace_id=ws.id, reference=_ref("TR"), product_id=p.id, from_location_id=src.location_id,
                         to_location_id=dst.id, quantity=qty, status="completed", created_by=rnd.choice(staff).id,
                         created_at=now - timedelta(days=rnd.randint(0, 20)))
            s.add(t)
            s.flush()
            s.add(Activity(workspace_id=ws.id, actor_id=t.created_by, verb="transferred", object_type="product", object_id=p.id,
                           summary=f"transferred {qty} × {p.sku}", at=t.created_at))

        for _ in range(rnd.randint(2, 4)):
            p = rnd.choice(products)
            s.add(PurchaseOrder(workspace_id=ws.id, reference=_ref("PO"), supplier=rnd.choice(["Fenwick Supplies", "Osprey Trade", "Corran Wholesale"]),
                                product_id=p.id, location_id=recv.id, quantity=rnd.randint(20, 200),
                                status=rnd.choice(["draft", "placed", "placed"]), created_by=rnd.choice(staff).id))
    s.commit()
    return passwords
