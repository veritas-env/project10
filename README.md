# StockPilot

A warehouse inventory and stock-management system: warehouses (workspaces), storage
locations, products with per-location stock, stock adjustments, transfers between
locations, purchase orders, and team management with invitations. Runs on synthetic data only.

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| Data | PostgreSQL 16, Redis 7 |
| Deploy | Docker Compose behind Nginx and the lab TLS gateway |

## Roles

| Role | Can |
|---|---|
| Viewer (auditor) | read inventory, transfers and purchase orders |
| Member (clerk) | + add and edit products, adjust stock, transfer stock, raise and receive purchase orders |
| Manager (supervisor) | + create locations, invite viewers and clerks, remove clerks |
| Owner (warehouse manager) | + change roles, invite managers |

## Run the tests

```
cd backend
../.venv/Scripts/python.exe -m pytest -q
```

## Run with Docker

```
cp .env.example .env      # fill in every secret
make build up
docker compose -f deployment/compose.yaml --env-file .env run --rm backend \
    python -m app.cli seed-demo --passwords-out /data/uploads/../demo-passwords.json
```

Demo data: two warehouses (Northgate Distribution, Southbank Logistics) with staff,
storage locations, products, stock, transfers and purchase orders. Passwords are written
only to the `--passwords-out` file.

## Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/security-model.md](docs/security-model.md)
- [docs/test-plan.md](docs/test-plan.md)
- [docs/operations.md](docs/operations.md)
