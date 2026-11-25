# Bowl & Bloom Food Assistant

A fictional, single-deployable FastAPI application for menu browsing, simulated orders, persistent chat, Gemini function calling, and document-grounded policy answers. It uses MySQL for business and conversation data, ChromaDB for document vectors, and a same-origin HTML/CSS/JavaScript client. It makes no real payments and does not contact a delivery provider.

## Configure and run

1. Create a MySQL database and user (or use an existing local MySQL account):

```sql
CREATE DATABASE food_assistant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'food_app'@'localhost' IDENTIFIED BY 'choose-a-local-password';
GRANT ALL PRIVILEGES ON food_assistant.* TO 'food_app'@'localhost';
```

2. Copy `.env.example` to `.env`. Set `DATABASE_URL` to your MySQL credentials and add your Google AI Studio `GEMINI_API_KEY`. Set new demo passwords before starting. Never commit `.env` or paste secrets into chat.

3. Activate your existing Python environment. If it is in this project, use `source .venv/bin/activate`; if you are reusing the workspace environment one directory above, use `source ../.venv/bin/activate`. Install the project dependencies from this directory:

```bash
pip install -r requirements.txt
```

4. Start from this project directory:

```bash
alembic upgrade head
uvicorn main:app --reload
```

The app creates missing tables and demo data at startup. Browse the application at http://127.0.0.1:8000, Swagger at `/docs`, and OpenAPI at `/openapi.json`. The seeded usernames and their passwords are configured by `DEMO_*` values in `.env`; passwords are Argon2-hashed in MySQL.

To change the password for the already-seeded admin account, run `../.venv/bin/python -m app.reset_admin_password` from this directory and enter the new password twice at the hidden terminal prompts. The command updates the existing MySQL password hash; changing `DEMO_ADMIN_PASSWORD` alone does not reset an existing account.

`DATABASE_URL`, `GEMINI_API_KEY`, and the three demo passwords must be set for a useful local run. The server can start without a Gemini key, but chat and document embedding return a safe 503 until one is configured. MySQL must be running and the configured database must exist.

## Layers and patterns

- `app/api`: HTTP request/response validation, authentication dependencies, and API routes.
- `app/services`: catalog rules, transactional order behavior, chat orchestration, action confirmation, and RAG workflows.
- `app/repositories`: protocols and SQLAlchemy data-access implementations.
- `app/models.py`: MySQL entities and relational constraints; `app/schemas.py`: Pydantic API contracts.
- `app/agents`: one Gemini agent and an allowlisted tool adapter. Read tools use fixed local API paths and forward the authenticated request identity. Create/cancel tools only create pending actions.
- `app/rag`: safe file extraction and overlapping chunks; `ChromaVectorStore` persists embeddings and source metadata.
- `app/frontend`: responsive customer/admin interface served from the same origin.

The code uses Repository and Adapter patterns, constructor/dependency injection, and a request-scoped SQLAlchemy Unit of Work. Services own business rules; routers own HTTP behavior; the Gemini agent cannot bypass those APIs. Order creation locks inventory rows, snapshots server prices, updates stock and creates order lines in one transaction. Per-user idempotency keys protect confirmed order submissions. Customer order/session reads are ownership-scoped; administrators manage catalog, documents, and valid order status transitions.

## API workflows

Public signup is `POST /api/auth/signup` with a 3-32 character username and a password of at least 12 characters. New accounts are normalized to lowercase, Argon2-hashed, and always assigned the `USER` role. The endpoint returns 409 for an existing username; sign-in uses HTTP Basic at `/api/auth/me`.

Public catalog: `GET /api/menu_items` supports `category`, `vegetarian`, `max_price`, and `keyword`; public detail is `GET /api/menu_items/{id}`. Admin catalog operations are `POST`, `PUT /api/menu_items/{id}`, and `DELETE /api/menu_items/{id}`. Delete permanently removes a dish with no order references; otherwise it archives the dish and keeps historical order lines intact. Archived dishes are hidden from the active menu.

Authenticated order operations are `POST /api/orders` with an `Idempotency-Key` header and `{ "lines": [{"item_id": 1, "quantity": 1}] }`, `GET /api/orders`, `GET /api/orders/{id}`, and `POST /api/orders/{id}/cancel`. Admin status updates use `PATCH /api/admin/orders/{id}/status`.

Chat sessions and messages are under `/api/chat/sessions`. The message API returns `GENERAL`, `RAG`, `AGENT`, or `MIXED` mode, source citations, and a pending action if confirmation is needed. Confirm or reject through `POST /api/chat/actions/{id}/confirm` with `{ "confirm": true }` or `{ "confirm": false }`. Pending actions expire after ten minutes and survive app restarts. Confirmations re-use a persisted idempotency key.

Admins upload PDF, DOCX, or TXT policy files to `POST /api/documents`; `POST /api/documents/{id}/reindex` reindexes a stored upload. Chunks target 750 characters with 100-character overlap. The retriever returns at most four active-version chunks and citations; if no relevant evidence is found, the assistant says the policy cannot be verified. Treat document content as untrusted data.

The Gemini API key and database password stay server-side. The browser keeps Basic credentials in memory only, uses `textContent` for chat/catalog text, and the API applies request limits and stable `{code, message, request_id}` error responses. Basic auth requires HTTPS outside localhost. This capstone's demo passwords must be changed, and production deployment would need TLS, stronger secret management, observability, and formal migration review.

## Demo accounts and seed data

Startup seeds ten fictional menu items, two customer accounts, one admin, and three sample orders only when the corresponding tables are empty. Change the `.env` demo passwords before the first run. The admin can add/edit/disable items, upload policy files, and advance an order through `CONFIRMED` → `PREPARING` → `READY` → `COMPLETED`. Customers can browse without login, then sign in to create/view/cancel their own orders and retain their chat history.

Upload the starter files in `app/knowledge_base` from the admin account to populate the RAG knowledge base. Declared allergen information is not a safety guarantee; cross-contact cannot be ruled out.

## Tests

Tests use a temporary SQLite database for deterministic service/API behavior; the application runtime remains configured for MySQL. Gemini HTTP calls are mocked. Run from this directory:

```bash
pytest -q
```