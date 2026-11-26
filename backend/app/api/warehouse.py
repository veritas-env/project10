"""Locations, products, stock levels, adjustments, transfers and purchase orders."""

from __future__ import annotations

import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import (
    Activity,
    Location,
    Product,
    PurchaseOrder,
    StockLevel,
    StockMove,
    Transfer,
    User,
)
from ..schemas import (
    AdjustIn,
    DashboardOut,
    LocationIn,
    LocationOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
    PurchaseOrderIn,
    PurchaseOrderOut,
    StockLevelOut,
    TransferIn,
    TransferOut,
)
from ..services import activity
from .common import load
from .deps import WorkspaceContext, workspace_access

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["warehouse"])


def _ref(prefix: str) -> str:
    return prefix + "".join(secrets.choice(string.digits) for _ in range(6))


# --- locations ----------------------------------------------------------------------

@router.get("/locations", response_model=list[LocationOut])
def list_locations(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db)) -> list[LocationOut]:
    rows = db.scalars(select(Location).where(Location.workspace_id == ctx.workspace.id).order_by(Location.code))
    return [LocationOut(id=l.id, code=l.code, name=l.name) for l in rows]


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(body: LocationIn, ctx: WorkspaceContext = Depends(workspace_access("manager")), db: Session = Depends(get_db)) -> LocationOut:
    l = Location(workspace_id=ctx.workspace.id, code=body.code, name=body.name)
    db.add(l)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "location_exists") from None
    return LocationOut(id=l.id, code=l.code, name=l.name)


# --- products and stock -------------------------------------------------------------

def product_out(db: Session, p: Product) -> ProductOut:
    rows = db.execute(select(StockLevel, Location.code).join(Location, Location.id == StockLevel.location_id)
                      .where(StockLevel.product_id == p.id)).all()
    levels = [StockLevelOut(location_id=sl.location_id, location_code=code, quantity=sl.quantity) for sl, code in rows]
    total = sum(x.quantity for x in levels)
    return ProductOut(id=p.id, sku=p.sku, name=p.name, unit=p.unit, reorder_level=p.reorder_level,
                      total_quantity=total, low_stock=total <= p.reorder_level, levels=levels)


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/products", response_model=list[ProductOut])
def list_products(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db),
                  q: str | None = Query(default=None, max_length=100), low_stock: bool = False,
                  limit: int = Query(default=200, ge=1, le=500)) -> list[ProductOut]:
    stmt = select(Product).where(Product.workspace_id == ctx.workspace.id)
    if q:
        like = f"%{_escape_like(q)}%"
        stmt = stmt.where(Product.name.ilike(like, escape="\\") | Product.sku.ilike(like, escape="\\"))
    out = [product_out(db, p) for p in db.scalars(stmt.order_by(Product.sku).limit(limit))]
    return [p for p in out if p.low_stock] if low_stock else out


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(body: ProductIn, ctx: WorkspaceContext = Depends(workspace_access("member")), db: Session = Depends(get_db)) -> ProductOut:
    p = Product(workspace_id=ctx.workspace.id, **body.model_dump())
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "sku_taken") from None
    activity.log(db, ctx.workspace.id, ctx.user.id, "created", "product", p.id, f"added product {p.sku} “{p.name}”")
    db.commit()
    db.refresh(p)
    return product_out(db, p)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db)) -> ProductOut:
    return product_out(db, load(db, Product, ctx.workspace.id, product_id))


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: uuid.UUID, body: ProductUpdate, ctx: WorkspaceContext = Depends(workspace_access("member")),
                   db: Session = Depends(get_db)) -> ProductOut:
    p = load(db, Product, ctx.workspace.id, product_id, lock=True)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return product_out(db, p)


def _level(db: Session, workspace_id, product_id, location_id, lock=False) -> StockLevel:
    stmt = select(StockLevel).where(StockLevel.product_id == product_id, StockLevel.location_id == location_id)
    sl = db.scalar(stmt.with_for_update() if lock else stmt)
    if sl is None:
        sl = StockLevel(workspace_id=workspace_id, product_id=product_id, location_id=location_id, quantity=0)
        db.add(sl)
        db.flush()
    return sl


@router.post("/products/{product_id}/adjust", response_model=ProductOut)
def adjust_stock(product_id: uuid.UUID, body: AdjustIn, ctx: WorkspaceContext = Depends(workspace_access("member")),
                 db: Session = Depends(get_db)) -> ProductOut:
    p = load(db, Product, ctx.workspace.id, product_id)
    load(db, Location, ctx.workspace.id, body.location_id)
    if body.delta == 0:
        raise HTTPException(422, {"error": "validation_error", "fields": [{"loc": ["body", "delta"], "msg": "must not be zero"}]})
    sl = _level(db, ctx.workspace.id, p.id, body.location_id, lock=True)
    if sl.quantity + body.delta < 0:
        raise HTTPException(409, "insufficient_stock")
    sl.quantity += body.delta
    db.add(StockMove(workspace_id=ctx.workspace.id, product_id=p.id, location_id=body.location_id, delta=body.delta,
                     reason="adjustment", note=body.note, created_by=ctx.user.id))
    activity.log(db, ctx.workspace.id, ctx.user.id, "adjusted", "product", p.id, f"adjusted {p.sku} by {body.delta:+d}")
    db.commit()
    db.refresh(p)
    return product_out(db, p)


# --- transfers ----------------------------------------------------------------------

@router.get("/transfers", response_model=list[TransferOut])
def list_transfers(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db),
                   limit: int = Query(default=100, ge=1, le=500)) -> list[TransferOut]:
    rows = db.scalars(select(Transfer).where(Transfer.workspace_id == ctx.workspace.id).order_by(Transfer.created_at.desc()).limit(limit))
    return [TransferOut(id=t.id, reference=t.reference, product_id=t.product_id, from_location_id=t.from_location_id,
                        to_location_id=t.to_location_id, quantity=t.quantity, status=t.status, created_at=t.created_at) for t in rows]


@router.post("/transfers", response_model=TransferOut, status_code=201)
def create_transfer(body: TransferIn, ctx: WorkspaceContext = Depends(workspace_access("member")), db: Session = Depends(get_db)) -> TransferOut:
    if body.from_location_id == body.to_location_id:
        raise HTTPException(422, {"error": "validation_error", "fields": [{"loc": ["body", "to_location_id"], "msg": "same location"}]})
    p = load(db, Product, ctx.workspace.id, body.product_id)
    load(db, Location, ctx.workspace.id, body.from_location_id)
    load(db, Location, ctx.workspace.id, body.to_location_id)

    # Credit the destination first, then take the stock off the source.
    dest = _level(db, ctx.workspace.id, p.id, body.to_location_id, lock=True)
    dest.quantity += body.quantity
    db.add(StockMove(workspace_id=ctx.workspace.id, product_id=p.id, location_id=body.to_location_id, delta=body.quantity,
                     reason="transfer", created_by=ctx.user.id))
    db.flush()

    source = _level(db, ctx.workspace.id, p.id, body.from_location_id, lock=True)
    try:
        with db.begin_nested():
            source.quantity -= body.quantity
            db.add(StockMove(workspace_id=ctx.workspace.id, product_id=p.id, location_id=body.from_location_id,
                             delta=-body.quantity, reason="transfer", created_by=ctx.user.id))
            db.flush()  # the stock_levels quantity >= 0 CHECK fires here if the source goes negative
    except IntegrityError:
        pass  # couldn't take it off the source; the goods are already at the destination

    t = Transfer(workspace_id=ctx.workspace.id, reference=_ref("TR"), product_id=p.id, from_location_id=body.from_location_id,
                 to_location_id=body.to_location_id, quantity=body.quantity, status="completed", created_by=ctx.user.id)
    db.add(t)
    activity.log(db, ctx.workspace.id, ctx.user.id, "transferred", "product", p.id,
                 f"transferred {body.quantity} × {p.sku}")
    db.commit()
    db.refresh(t)
    return TransferOut(id=t.id, reference=t.reference, product_id=t.product_id, from_location_id=t.from_location_id,
                       to_location_id=t.to_location_id, quantity=t.quantity, status=t.status, created_at=t.created_at)


# --- purchase orders ----------------------------------------------------------------

def po_out(po: PurchaseOrder) -> PurchaseOrderOut:
    return PurchaseOrderOut(id=po.id, reference=po.reference, supplier=po.supplier, product_id=po.product_id,
                            location_id=po.location_id, quantity=po.quantity, status=po.status, created_at=po.created_at)


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
def list_pos(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db)) -> list[PurchaseOrderOut]:
    return [po_out(po) for po in db.scalars(select(PurchaseOrder).where(PurchaseOrder.workspace_id == ctx.workspace.id).order_by(PurchaseOrder.created_at.desc()))]


@router.post("/purchase-orders", response_model=PurchaseOrderOut, status_code=201)
def create_po(body: PurchaseOrderIn, ctx: WorkspaceContext = Depends(workspace_access("member")), db: Session = Depends(get_db)) -> PurchaseOrderOut:
    p = load(db, Product, ctx.workspace.id, body.product_id)
    load(db, Location, ctx.workspace.id, body.location_id)
    po = PurchaseOrder(workspace_id=ctx.workspace.id, reference=_ref("PO"), supplier=body.supplier, product_id=p.id,
                       location_id=body.location_id, quantity=body.quantity, created_by=ctx.user.id)
    db.add(po)
    db.commit()
    db.refresh(po)
    return po_out(po)


@router.post("/purchase-orders/{po_id}/receive", response_model=PurchaseOrderOut)
def receive_po(po_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("member")), db: Session = Depends(get_db)) -> PurchaseOrderOut:
    po = load(db, PurchaseOrder, ctx.workspace.id, po_id, lock=True)
    if po.status not in ("draft", "placed"):
        raise HTTPException(409, "already_closed")
    sl = _level(db, ctx.workspace.id, po.product_id, po.location_id, lock=True)
    sl.quantity += po.quantity
    po.status = "received"
    db.add(StockMove(workspace_id=ctx.workspace.id, product_id=po.product_id, location_id=po.location_id, delta=po.quantity,
                     reason="receipt", note=f"PO {po.reference}", created_by=ctx.user.id))
    activity.log(db, ctx.workspace.id, ctx.user.id, "received", "product", po.product_id, f"received {po.quantity} from {po.supplier}")
    db.commit()
    db.refresh(po)
    return po_out(po)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db)) -> DashboardOut:
    ws = ctx.workspace.id
    recent = db.execute(select(Activity, User.display_name).outerjoin(User, User.id == Activity.actor_id)
                        .where(Activity.workspace_id == ws).order_by(Activity.id.desc()).limit(10)).all()
    products = list(db.scalars(select(Product).where(Product.workspace_id == ws)))
    low = sum(1 for p in products if product_out(db, p).low_stock)
    return DashboardOut(
        products=len(products),
        locations=db.scalar(select(func.count()).select_from(Location).where(Location.workspace_id == ws)),
        total_units=db.scalar(select(func.coalesce(func.sum(StockLevel.quantity), 0)).where(StockLevel.workspace_id == ws)),
        low_stock=low,
        open_purchase_orders=db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.workspace_id == ws, PurchaseOrder.status.in_(("draft", "placed")))),
        recent_activity=[{"id": a.id, "at": a.at, "actor_name": name, "summary": a.summary} for a, name in recent],
    )
