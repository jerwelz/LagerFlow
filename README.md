# LagerFlow

**[▶ Live demo: lagerflow-demo.onrender.com](https://lagerflow-demo.onrender.com)** · [API documentation (Swagger UI)](https://lagerflow-demo.onrender.com/docs)

> The demo uses fictional data only. Changes are temporary and are reset every 60 minutes and on every restart. It runs on Render's free plan, so the first request after a period of inactivity can take about a minute while the service wakes up.

LagerFlow is a REST API for managing the inventory of a small business. It keeps a product catalogue, records incoming and outgoing stock, and keeps a complete movement history. It also shows which products have fallen below their minimum stock level and exports the inventory as CSV.

The focus is a small backend that is correct, tested and easy to follow, rather than a large feature set. A React dashboard (in German) shows the API in action; the API can also be used directly through FastAPI's interactive documentation at `/docs`.

## Live demo

**Live demo:** https://lagerflow-demo.onrender.com — an interactive dashboard in German on top of the REST API. You can search products, create and edit them, book incoming and outgoing stock and watch the stock figures update. The Swagger UI runs on the same server at https://lagerflow-demo.onrender.com/docs, so every endpoint can also be tried directly.

The demo uses **fictional data only**, is shared by all visitors and is reset regularly. See [Demo mode](#demo-mode) for its safeguards and [Deployment](#deployment) to run your own copy.

The dashboard has four areas:

- **Übersicht:** key figures (active products, total units, low and empty stock), recent movements and a reorder list
- **Artikel:** searchable product table, details with movement history, create, edit and deactivate
- **Buchungen:** book incoming (`IN`) and outgoing (`OUT`) stock; errors such as insufficient stock are shown in plain language
- **Bestand:** stock levels against the minimum, with a filter for low stock

Links to the API documentation and the CSV export are in the header. The dashboard only calls the public REST API; stock changes always go through the movement endpoint.

## Technologies

- Python 3.12
- FastAPI (HTTP layer and OpenAPI documentation)
- SQLAlchemy 2.x ORM with SQLite
- Alembic (database migrations)
- Pydantic v2 (request validation and response schemas)
- pytest and HTTPX via FastAPI's `TestClient`
- Ruff (linting and formatting)

Dashboard (`frontend/`):

- React 19 and TypeScript, built with Vite
- Tailwind CSS (no component library, no router or state library)
- Vitest and Testing Library (unit tests), Playwright (end-to-end tests)

## Features

- **Products:** create, read, list with search and pagination, partial update, deactivate (soft delete)
- **Stock movements:** record incoming (`IN`) and outgoing (`OUT`) stock with an optional reason
- **Movement history** per product, newest first, paginated
- **Inventory monitoring:** current stock levels, products below their minimum, summary totals
- **CSV export** of the current inventory
- **One error format** for every error response, also documented in `/docs`

Rules the API guarantees:

- Stock only changes through stock movements. Product endpoints reject `current_stock` with 422.
- Stock can never become negative, even under concurrent requests (see [Data integrity](#data-integrity)).
- The stock update and its movement record are saved in one transaction: either both or neither.
- SKUs are unique. They are trimmed and stored in upper case, so `abc-1` and `ABC-1` are the same SKU.
- Products are never deleted, only deactivated. Their movement history stays available.
- Inactive products cannot receive stock movements and are excluded from lists, monitoring and the CSV export.

## Architecture

```
app/
├── main.py            FastAPI app: routers, error handlers, serves the built dashboard
├── config.py          Settings (database URL, demo mode) from environment variables
├── database.py        Engine, session factory, get_db dependency, SQLite foreign keys
├── models.py          SQLAlchemy models: Product, StockMovement
├── schemas.py         Pydantic request and response models
├── errors.py          Application errors and the JSON error format
├── api/               HTTP layer: routes, status codes, parameters
├── services/          Business rules and transaction handling
├── repositories/      Database queries only
├── demo.py            Fictional demo data and the guarded reset
└── demo_guard.py      Demo safeguards: rate limits, size caps, periodic reset
alembic/               Database migrations
tests/                 pytest test suite
frontend/              React dashboard (Vite project)
├── src/api.ts         Typed API client and German error messages
├── src/views/         Übersicht, Artikel, Buchungen, Bestand
└── e2e/               Playwright end-to-end tests
render.yaml            Deployment blueprint for Render
```

FastAPI serves the built dashboard from `frontend/dist` (`/` and `/assets`) when it exists. Browser and API share one origin, so no CORS configuration is needed. Unknown paths still return the JSON error format.

Each request passes through three layers:

| Layer | Responsibility | Example |
|---|---|---|
| `api/` | Parse the request, call the service, return the response | `POST /products/{id}/movements` |
| `services/` | Apply business rules, decide when to commit | "An `OUT` movement may not exceed the stock" |
| `repositories/` | Run SQL queries, never commit | The conditional `UPDATE` of the stock |

Only services call `commit()`, so one service function equals one transaction. Services raise exceptions such as `NotFoundError` or `ConflictError`. Central handlers in `errors.py` turn them into JSON responses, so routes never build error responses themselves.

### Database schema

```
products                                stock_movements
─────────────────────────────           ──────────────────────────────────
id             INTEGER PK               id             INTEGER PK
sku            VARCHAR(50) UNIQUE       product_id     INTEGER FK → products.id
name           VARCHAR(200)                            (ON DELETE RESTRICT)
description    TEXT NULL                movement_type  'IN' | 'OUT' (CHECK)
current_stock  INTEGER CHECK >= 0       quantity       INTEGER CHECK > 0
min_stock      INTEGER CHECK >= 0       reason         VARCHAR(255) NULL
is_active      BOOLEAN                  created_at     DATETIME (UTC)
created_at     DATETIME (UTC)
```

Indexes: unique index on `products.sku`, an index on `products.name`, and an index on `stock_movements(product_id, created_at)` for the movement history.

### Data integrity

Negative stock is prevented at three levels:

1. **Service check.** The service compares the requested quantity with the stock and returns a clear `409 INSUFFICIENT_STOCK` error.
2. **Conditional UPDATE.** The stock is changed with
   `UPDATE products SET current_stock = current_stock + :delta WHERE id = :id AND is_active AND current_stock + :delta >= 0 RETURNING current_stock`.
   The database checks and changes the value in one statement. If two requests compete for the last items, only one UPDATE matches the row. The other request gets a 409.
3. **Database constraint.** `CHECK (current_stock >= 0)` is the final safety net.

The stock UPDATE and the insert of the `StockMovement` happen in the same transaction. Any failure rolls back both. The test suite simulates failures at both points, and starts 20 threads that try to withdraw stock at the same moment.

## Installation

Requirements: Python 3.12 or newer.

```bash
git clone <repository-url> lager-flow
cd lager-flow
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

The `dev` extra installs pytest, HTTPX and Ruff. To install only what the application needs to run, use `pip install -e .`.

### Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `LAGERFLOW_DATABASE_URL` | `sqlite:///./lagerflow.db` | SQLAlchemy database URL |
| `LAGERFLOW_DEMO_MODE` | `false` | Enables the public demo safeguards and seed data (see [Demo mode](#demo-mode)) |
| `LAGERFLOW_DEMO_RESET_MINUTES` | `60` | Demo only: interval of the automatic reset |
| `LAGERFLOW_DEMO_MAX_PRODUCTS` / `LAGERFLOW_DEMO_MAX_MOVEMENTS` | `60` / `2000` | Demo only: size caps |
| `LAGERFLOW_DEMO_WRITE_LIMIT_PER_MINUTE` / `LAGERFLOW_DEMO_GLOBAL_WRITE_LIMIT_PER_MINUTE` | `20` / `120` | Demo only: write requests per client / in total |

The variable can also be set in a `.env` file in the project root. Git ignores that file.

## Database migrations

Create or upgrade the database schema:

```bash
alembic upgrade head
```

After changing a model, create a new migration and review it before applying:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The test suite checks that the migrations and the models describe the same schema.

## Running the application

```bash
uvicorn app.main:app --reload
```

- Interactive documentation: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

### Dashboard

Requirements: Node.js 20.19 or newer.

```bash
cd frontend
npm ci
npm run dev       # http://localhost:5173, forwards API requests to uvicorn on port 8000
```

Keep `uvicorn` running in a second terminal. Alternatively, build once with `npm run build`; uvicorn then serves the dashboard itself at http://127.0.0.1:8000/.

Locally the dashboard works on your normal `lagerflow.db`. To try it with the demo data instead, use a separate database file whose name contains `demo`:

```bash
# Linux / macOS (Windows PowerShell: $env:LAGERFLOW_DEMO_MODE="true"; ...)
export LAGERFLOW_DEMO_MODE=true LAGERFLOW_DATABASE_URL=sqlite:///./lagerflow-demo.db
alembic upgrade head
uvicorn app.main:app
```

## API endpoints

| Method | Path | Description | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | Liveness check | 200 | – |
| POST | `/products` | Create a product (stock starts at 0) | 201 | 409, 422 |
| GET | `/products` | List products. Query: `search`, `limit` (1–100, default 20), `offset`, `include_inactive` | 200 | 422 |
| GET | `/products/{id}` | Get one product (also inactive ones) | 200 | 404, 422 |
| PATCH | `/products/{id}` | Update `sku`, `name`, `description`, `min_stock` | 200 | 404, 409, 422 |
| POST | `/products/{id}/deactivate` | Deactivate a product (idempotent) | 200 | 404, 422 |
| POST | `/products/{id}/movements` | Record an `IN` or `OUT` movement | 201 | 404, 409, 422 |
| GET | `/products/{id}/movements` | Movement history, newest first. Query: `limit`, `offset` | 200 | 404, 422 |
| GET | `/inventory/levels` | Stock of all active products with an `is_low` flag | 200 | – |
| GET | `/inventory/low-stock` | Active products with `current_stock < min_stock` | 200 | – |
| GET | `/inventory/summary` | Totals over all active products | 200 | – |
| GET | `/reports/inventory.csv` | CSV download of all active products | 200 | – |

Paginated endpoints return `{"items": [...], "total": n, "limit": n, "offset": n}`. `total` counts all matching items, not only the current page.

### Error format

Every error response has the same shape:

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Insufficient stock: requested 15, available 10.", "details": { "requested": 15, "available": 10 } } }
```

| Status | Code | Meaning |
|---|---|---|
| 400 | `HTTP_ERROR` | Request body could not be decoded (e.g. not UTF-8) |
| 404 | `PRODUCT_NOT_FOUND` | No product with this ID |
| 404 / 405 | `HTTP_ERROR` | Unknown route or wrong HTTP method |
| 409 | `DUPLICATE_SKU` | Another product already uses this SKU |
| 409 | `INSUFFICIENT_STOCK` | `OUT` quantity exceeds the current stock |
| 409 | `PRODUCT_INACTIVE` | Movements on a deactivated product |
| 409 | `CONFLICT` | Stock changed concurrently in an unexpected way. The request can be retried |
| 422 | `VALIDATION_ERROR` | Invalid input. `details` lists every problem |
| 500 | `INTERNAL_ERROR` | Unexpected server error. No internal details are exposed |

## Examples

These responses were recorded against a fresh database.

**Create a product.** The SKU is normalised to upper case:

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H "Content-Type: application/json" \
  -d '{"sku": "scr-4x40", "name": "Wood screw 4x40", "description": "Box of 100", "min_stock": 8}'
```
```json
201 Created
{"id": 1, "sku": "SCR-4X40", "name": "Wood screw 4x40", "description": "Box of 100",
 "current_stock": 0, "min_stock": 8, "is_active": true, "created_at": "2026-10-27T10:17:53.057723Z"}
```

**Book incoming stock:**

```bash
curl -X POST http://127.0.0.1:8000/products/1/movements \
  -H "Content-Type: application/json" \
  -d '{"movement_type": "IN", "quantity": 10, "reason": "Delivery 2026-10-27"}'
```
```json
201 Created
{"id": 1, "product_id": 1, "movement_type": "IN", "quantity": 10,
 "reason": "Delivery 2026-10-27", "created_at": "2026-10-27T10:17:53.572459Z"}
```

**Try to withdraw more than is available:**

```bash
curl -X POST http://127.0.0.1:8000/products/1/movements \
  -H "Content-Type: application/json" \
  -d '{"movement_type": "OUT", "quantity": 15}'
```
```json
409 Conflict
{"error": {"code": "INSUFFICIENT_STOCK", "message": "Insufficient stock: requested 15, available 10.",
           "details": {"requested": 15, "available": 10}}}
```

**Try to set the stock directly:**

```bash
curl -X PATCH http://127.0.0.1:8000/products/1 \
  -H "Content-Type: application/json" -d '{"current_stock": 999}'
```
```json
422 Unprocessable Content
{"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.",
           "details": [{"type": "extra_forbidden", "loc": ["body", "current_stock"],
                        "msg": "Extra inputs are not permitted", "input": 999}]}}
```

**Movement history,** after an additional `OUT` of 5:

```bash
curl "http://127.0.0.1:8000/products/1/movements?limit=2"
```
```json
200 OK
{"items": [
   {"id": 2, "product_id": 1, "movement_type": "OUT", "quantity": 5, "reason": "Order 1001",
    "created_at": "2026-10-27T10:17:54.098172Z"},
   {"id": 1, "product_id": 1, "movement_type": "IN", "quantity": 10, "reason": "Delivery 2026-10-27",
    "created_at": "2026-10-27T10:17:53.572459Z"}],
 "total": 2, "limit": 2, "offset": 0}
```

**Low stock and summary:**

```bash
curl http://127.0.0.1:8000/inventory/low-stock
curl http://127.0.0.1:8000/inventory/summary
```
```json
[{"id": 1, "sku": "SCR-4X40", "name": "Wood screw 4x40", "current_stock": 5, "min_stock": 8, "is_low": true}]

{"active_products": 1, "total_units": 5, "low_stock_products": 1, "out_of_stock_products": 0}
```

**CSV export:**

```bash
curl -OJ http://127.0.0.1:8000/reports/inventory.csv   # saves inventory-YYYY-MM-DD.csv
```
```csv
id,sku,name,description,current_stock,min_stock,is_low
1,SCR-4X40,Wood screw 4x40,Box of 100,5,8,true
```

The file is UTF-8 with a byte-order mark, so Excel displays umlauts correctly. Text cells that start with `=`, `+`, `-` or `@` get a leading `'`, so spreadsheet programs do not run them as formulas.

> On Windows, send request bodies with non-ASCII characters as UTF-8, for example `--data-binary @body.json`. Some terminals send another encoding, which the API rejects with `400`.

## Demo mode

The public demo has no login, so `LAGERFLOW_DEMO_MODE=true` adds a few safeguards. They are off by default and do not change the API when disabled.

- **Separate, fictional data.** The demo uses its own database file. The reset refuses to run unless demo mode is on **and** the database file name contains `demo`, so it can never wipe `lagerflow.db`. The seed data (`app/demo.py`) contains 15 invented products (electrical parts, fasteners, tools, packaging, workshop supplies) with normal, low and zero stock and one inactive product. Their stock is calculated from their movement history, and a test checks that both agree.
- **Reset.** The data is replaced with the seed data on every start and every 60 minutes, in one transaction. `python -m app.demo reset` does the same manually.
- **Rate limits.** At most 20 write requests per minute per client and 120 in total. Further writes get `429 RATE_LIMITED` with a `Retry-After` header. Reads are not limited. A client is identified by the `CF-Connecting-IP` header that Cloudflare sets in front of Render, otherwise by the last `X-Forwarded-For` hop.
- **Size caps.** At most 60 products and 2000 movements; further creates get `409 DEMO_LIMIT_REACHED`.
- **Integrity unchanged.** All writes go through the normal services and database constraints, so negative stock stays impossible.
- `GET /demo/info` shows the next reset time and the limits; it exists only in demo mode.

The limits are kept in memory. That is enough for one server process, which is how the demo runs.

## Deployment

The repository contains a [Render](https://render.com) Blueprint (`render.yaml`) for a free web service. A single process serves the API, `/docs` and the dashboard:

- Build: `pip install -e . && cd frontend && npm ci && npm run build`
- Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment: `LAGERFLOW_DEMO_MODE=true`, `LAGERFLOW_DATABASE_URL=sqlite:///./lagerflow-demo.db`
- Python 3.12 (`.python-version`), Node.js from `frontend/package.json`

To deploy your own copy: in the Render dashboard choose **New → Blueprint**, connect the repository and confirm the `lagerflow-demo` service. No secrets are needed.

Free Render services have an ephemeral filesystem and stop after 15 minutes without traffic. That fits the demo: every start begins with fresh seed data. The first request after a pause takes about a minute.

## Testing

```bash
pytest            # run the test suite
ruff check .      # lint
ruff format --check .
```

Dashboard:

```bash
cd frontend
npm run lint      # TypeScript type check
npm test          # Vitest unit tests
npm run build
npx playwright install chromium   # once
npm run e2e       # Playwright: starts the API in demo mode on a temporary database
BASE_URL=https://<your-demo-url> npm run e2e   # same tests against a deployed demo
```

Each test runs against a fresh in-memory SQLite database. The `get_db` dependency is replaced in `tests/conftest.py`, so the tests never touch `lagerflow.db`. The suite covers:

- every endpoint, including success and failure cases
- the standardised error format and its OpenAPI documentation
- the database constraints, independently of the application code
- transaction rollback when saving the movement fails, including a real foreign-key failure during commit
- race conditions, including 20 threads withdrawing stock concurrently from a file-based database
- consistency between the stock level and the movement history
- the Alembic migrations (upgrade, downgrade, and agreement with the models)
- demo mode: seed data consistency, idempotent reset, the reset guard, rate limits, size caps, and that nothing changes when demo mode is off
- serving the dashboard without exposing other files

The frontend unit tests cover the API client and its German error messages. The end-to-end tests drive a real browser through the dashboard: search, create, `IN` and `OUT` movements, the insufficient-stock error, editing, deactivation, stock filters, the CSV export and the `/docs` link.

## Known limitations

- **No authentication or authorisation.** Anyone who can reach the API can change data.
- **The live demo is a shared sandbox, not a production setup.** All visitors see the same data; changes disappear on the next reset. Rate limits and caps reduce abuse, but they are simple in-memory counters for a single process. There is no multi-user support.
- **Cold starts.** The free hosting plan stops the demo when idle; the first request afterwards takes about a minute.
- The dashboard's **recent activity** is assembled from the per-product movement history (one request per product), because the API has no global movement list. That is fine for the demo's 15 products, not for large inventories.
- **SQLite** allows only one writer at a time. Under heavy concurrent load, a request that waits longer than SQLite's 5-second lock timeout fails with a 500. The conditional-UPDATE pattern also works on PostgreSQL, but the project has only been tested with SQLite. The UPDATE uses `RETURNING`, which needs SQLite 3.35+ or PostgreSQL.
- **Deactivation is one-way.** There is no endpoint to reactivate a product.
- **Movements are append-only.** A wrong booking is corrected with an opposite movement, not by editing or deleting.
- `/inventory/levels`, `/inventory/low-stock` and the CSV export are **not paginated**. That is fine for a small catalogue, not for tens of thousands of products.
- **Product search** uses `LIKE '%term%'`, which cannot use an index.
- The **CSV export** is comma-separated. A German Excel installation may expect semicolons and show everything in one column; use *Data → From Text/CSV* to import it.
- All **timestamps are UTC.**
- pytest shows one **deprecation warning** from Starlette, which recommends `httpx2` instead of `httpx` for the test client. The project keeps `httpx` as planned.

## License

MIT. See [LICENSE](LICENSE).
