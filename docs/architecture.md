# Architecture

- **Frontend**: Next.js. Pages: warehouses, overview dashboard, inventory (products with
  per-location stock and adjustments), transfers (create and history), team & invitations,
  invitation landing page.
- **Backend**: FastAPI. Routers: `auth`, `workspaces` (members), `invitations`, `warehouse`
  (locations, products, stock levels, adjustments, transfers, purchase orders, dashboard),
  `admin` (security events, alerts).
- **Data model**: `workspaces` (warehouses) → `memberships(role)`, `invitations`,
  `locations`, `products`, `stock_levels` (product × location, `CHECK quantity >= 0`),
  `stock_moves` (audit of every change), `transfers`, `purchase_orders`; `activity`;
  `security_events` (append-only) and `alerts`.
- **Demo data**: `python -m app.cli seed-demo` (see `app/demo_data.py`).
