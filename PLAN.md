# LagerFlow — Implementation Plan

## Context
LagerFlow is a small inventory REST API, built as a GitHub portfolio project for FIAE apprenticeship applications (Munich, 2027). The goal is a clean, well-tested MVP that takes about two days and that the author can fully explain in an interview.

This is the original plan written before implementation. The README describes the finished project. Deviations made during development:
- `GET /products/{id}/movements` was first reserved as a manual exercise, but was implemented together with milestone 4.
- The movement history uses the same paginated envelope as `GET /products` (`items`, `total`, `limit`, `offset`) instead of a plain list.
- The SKU can be changed via `PATCH`; duplicates return 409.
- Integer inputs are capped at the 64-bit database limit, so oversized values return 422 instead of 500.
- The CSV export neutralises cells that spreadsheet programs would run as formulas.
- After the MVP, a React dashboard (`frontend/`) and a guarded public demo mode (`app/demo.py`, `app/demo_guard.py`) were added. The original plan had no frontend.

---

## 1. Project structure

```
lager-flow/
├── app/
│   ├── main.py              # FastAPI app, router registration, exception handlers
│   ├── config.py            # Settings (DB URL) via pydantic-settings
│   ├── database.py          # Engine, SessionLocal, Base, get_db dependency, SQLite FK pragma
│   ├── models.py            # SQLAlchemy ORM models: Product, StockMovement
│   ├── schemas.py           # Pydantic request/response models
│   ├── errors.py            # AppError subclasses (NotFound, Conflict) + error response shape
│   ├── repositories/        # Database access only (queries, inserts, updates)
│   │   ├── products.py
│   │   └── movements.py
│   ├── services/            # Business rules; owns the transaction
│   │   ├── products.py
│   │   ├── stock.py
│   │   └── inventory.py     # low stock, summary, CSV generation
│   └── api/                 # HTTP layer: routes, status codes, request parsing
│       ├── products.py
│       ├── movements.py
│       └── inventory.py     # monitoring and CSV export
├── alembic/                 # Migrations (render_as_batch=True for SQLite)
├── tests/
│   ├── conftest.py          # In-memory DB, client fixture, product factory
│   ├── test_products.py
│   ├── test_movements.py
│   ├── test_inventory.py
│   └── test_stock_service.py
├── alembic.ini
├── pyproject.toml           # dependencies, pytest + ruff config
└── README.md
```

**What each layer does:**
- **api/**: turns HTTP requests into function calls and results into HTTP responses. It contains no business logic.
- **services/**: holds the business rules (for example, "stock can't go negative") and decides when to commit.
- **repositories/**: contains the SQLAlchemy queries. It never commits, so services control the transaction boundary.
- **schemas.py / models.py**: Pydantic models describe the API contract. ORM models describe the database. They are kept separate on purpose.

## 2. Database schema

**products**
| column | type | constraints |
|---|---|---|
| id | INTEGER | PK |
| sku | VARCHAR(50) | NOT NULL, UNIQUE (indexed) |
| name | VARCHAR(200) | NOT NULL, indexed (search) |
| description | TEXT | NULL |
| current_stock | INTEGER | NOT NULL, default 0, `CHECK (current_stock >= 0)` |
| min_stock | INTEGER | NOT NULL, default 0, `CHECK (min_stock >= 0)` |
| is_active | BOOLEAN | NOT NULL, default true |
| created_at | DATETIME | NOT NULL, default now (UTC) |

**stock_movements**
| column | type | constraints |
|---|---|---|
| id | INTEGER | PK |
| product_id | INTEGER | FK → products.id, `ON DELETE RESTRICT`, NOT NULL |
| movement_type | ENUM('IN','OUT') | NOT NULL |
| quantity | INTEGER | NOT NULL, `CHECK (quantity > 0)` |
| reason | VARCHAR(255) | NULL |
| created_at | DATETIME | NOT NULL, default now (UTC) |

Composite index: `(product_id, created_at)` makes per-product history queries fast.

**Relationship:** one Product has many StockMovements (`Product.movements` ↔ `StockMovement.product`). Products are never hard-deleted, so the movement history always stays intact.

## 3. API endpoints

| Method | Path | Purpose | Success | Main errors |
|---|---|---|---|---|
| GET | `/health` | Liveness check | 200 | – |
| POST | `/products` | Create product (initial stock is always 0) | 201 | 409 duplicate SKU, 422 |
| GET | `/products` | List; `?search=` (SKU/name), `?limit=` (default 20, max 100), `?offset=`, `?include_inactive=` | 200 | 422 |
| GET | `/products/{id}` | Get one | 200 | 404 |
| PATCH | `/products/{id}` | Update name, description, min_stock | 200 | 404, 409 SKU, 422 if `current_stock` is sent |
| POST | `/products/{id}/deactivate` | Soft-delete (`is_active=false`) | 200 | 404 |
| POST | `/products/{id}/movements` | Record IN/OUT movement | 201 | 404, 409 insufficient stock, 409 inactive product, 422 |
| GET | `/products/{id}/movements` | Movement history (see §9) | 200 | 404 |
| GET | `/inventory/levels` | Current stock for all active products, with an `is_low` flag | 200 | – |
| GET | `/inventory/low-stock` | Active products where `current_stock < min_stock` | 200 | – |
| GET | `/inventory/summary` | Product count, total units, low-stock count, out-of-stock count | 200 | – |
| GET | `/reports/inventory.csv` | CSV download (`text/csv`, `Content-Disposition: attachment`) | 200 | – |

**Consistent error format** (all non-2xx responses, including 422):
```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Requested 5, available 3.", "details": null } }
```
This works through custom exceptions raised in services plus handlers registered in `main.py`. The handler for `RequestValidationError` is overridden so 422 responses use the same format.

## 4. Business rules
1. **Stock only changes through movements.** `ProductUpdate` uses `extra="forbid"` and has no `current_stock` field, so sending one returns 422.
2. **Stock never goes negative.** This is enforced in three places:
   - The service checks it first and returns a clear error message.
   - The UPDATE is conditional: `UPDATE ... SET current_stock = current_stock - :q WHERE id = :id AND current_stock >= :q`, and the code checks the affected row count.
   - The database `CHECK` constraint is the final safety net.
3. **Atomicity.** The stock update and the movement insert share one session transaction. Either both are committed or neither is (rollback on any exception).
4. Quantities are positive integers. The direction comes from `movement_type`, never from the sign of the number.
5. SKU is unique, trimmed and stored in uppercase. A duplicate returns 409, caught from `IntegrityError`.
6. Inactive products reject new movements (409), are hidden from lists by default, and are excluded from inventory monitoring.
7. All timestamps are stored and returned in UTC.

## 5. Testing strategy
- **Setup:** in-memory SQLite with `StaticPool`. Tables are created fresh for each test, and `get_db` is overridden through `app.dependency_overrides`. FastAPI's `TestClient` (built on HTTPX) sends the requests.
- **API tests:** at least one success test and the relevant failure tests per endpoint:
  - 404 for an unknown ID
  - 409 for a duplicate SKU
  - 422 for invalid input and for sending `current_stock` in PATCH
  - 409 for an OUT movement larger than the stock
  - pagination and search results
  - low-stock filtering
  - CSV header and rows
- **Service tests (`test_stock_service.py`):** atomicity. If inserting the movement fails, the stock must stay unchanged. The test forces this by making the insert raise.
- **Error format test:** checks that every error type returns the `{"error": {...}}` shape.
- **Migration check:** `alembic upgrade head` on a fresh file DB, run manually as part of the definition of done.
- Target: about 30–40 focused tests, with all business rules covered. Coverage is a side effect, not the goal.

## 6. Milestones
1. **Foundation (~½ day):** `pyproject.toml`, config, database (FK pragma), models, first Alembic migration, error handling, `/health`, test fixtures.
2. **Products (~½ day):** schemas, repository, service and routes for create/get/list/update/deactivate, plus tests.
3. **Stock movements (~½ day):** atomic IN/OUT service, POST endpoint, tests including atomicity.4. **Monitoring, reporting and polish (~½ day):** levels, low-stock, summary, CSV export, tests, README (setup, design decisions, example requests), ruff cleanup.

## 7. Technical risks
- **SQLite foreign keys are off by default.** They need `PRAGMA foreign_keys=ON` through an engine connect event, or the FK constraints do nothing.
- **SQLite has limited ALTER TABLE support.** Alembic needs `render_as_batch=True`.
- **SQLite returns naive datetimes.** The app should store UTC consistently and use a timezone-aware response format.
- **Race conditions on stock.** These are covered by the conditional UPDATE. SQLite also serializes writes, but the pattern is correct for any database.
- **Test isolation.** A shared DB state between tests would make results flaky, so each test gets fresh tables.
- **Outdated AI suggestions.** Pydantic v1 or SQLAlchemy 1.x style code (`orm_mode`, `query()`) can slip in. Stick to v2 APIs (`model_config`, `select()`, `Mapped[]`).
- **Scope creep.** Authentication, categories, suppliers and other extras stay out of the MVP and go into a "Future ideas" section of the README.

## 8. Definition of done
- All endpoints in §3 work and are documented in `/docs`.
- `pytest` passes, and every business rule in §4 has at least one test.
- `alembic upgrade head` builds the database from scratch.
- Error responses use the same format everywhere.
- `ruff check` is clean.
- The README explains setup, architecture, design decisions and example calls.
- The movement history endpoint (§9) is implemented and tested.
- The Git history has meaningful commits, roughly one per milestone step.

## 9. Movement history: `GET /products/{id}/movements`
Return the movement history of one product, newest first, with `limit`/`offset` pagination.
- 404 with the standard error format if the product doesn't exist.
- Response: a paginated list of `StockMovementRead` (the schema from milestone 3).
- Tests:
  - empty history
  - correct order after several movements
  - pagination
  - 404 for an unknown product
  - movements of other products are not included
## Five concepts for the interview
1. **Layered architecture:** why routes, services and repositories are separate, and what each layer is responsible for.
2. **Transactions and atomicity (ACID):** why the stock update and the movement record must be committed together.
3. **REST and HTTP status codes:** 201 vs 200, 404 vs 409 vs 422, and why deactivation is a POST action and not a DELETE.
4. **Layered validation:** Pydantic at the API boundary, business rules in services, and database constraints as the last safety net.
5. **Automated testing with dependency injection:** how `get_db` is swapped for an isolated test database.

## Verification
- `pytest -v`: all tests green.
- `alembic upgrade head` on a new `lagerflow.db`.
- `uvicorn app.main:app --reload`, then in `/docs`: create a product, book IN 10, try OUT 15 (expect 409), book OUT 5, check low-stock, summary and CSV download.
