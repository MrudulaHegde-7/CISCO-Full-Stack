# Verification report

## Automated

Command: `python -m pytest -q`

Result: **22 passed**.

Coverage includes customer signup, username normalization and duplicate rejection, Argon2 password hashing and automatic authentication, unique dish-matched menu image URLs, public menu filters, Pydantic validation, admin-only catalog operations, permanent deletion of unreferenced dishes and archival of order-referenced dishes, order price snapshots, request idempotency, ownership checks, inventory rollback on failure, cancellation capacity restoration, persistent chat history, AI outage persistence, pending-action staging/rejection/idempotent confirmation, mandatory quantity clarification before order staging, Gemini policy-tool mode/citations, document upload/re-index versioning, and RAG chunking/file type validation.

Tests use isolated SQLite files and mocked Gemini/vector adapters. This keeps them deterministic and does not require user credentials.

## Manual preview

The local preview was run on `127.0.0.1:8002` against a temporary SQLite database because no application `.env` was configured. Verified in the browser: ten seeded menu items render; desktop/mobile layouts have no horizontal overflow; admin sign-in and knowledge controls render; a customer can place and view an order; a missing Gemini key displays a safe error while retaining the chat turn.

Alembic's initial schema migration was applied successfully to a temporary SQLite URL.

## Live credentials

MySQL connectivity succeeded using the project `.env`; the initial Alembic migration applied to MySQL, and the running API returned all ten seeded menu items from it.

Gemini embeddings succeeded with HTTP 200 and a 3072-dimensional result. The initial `gemini-3.8-flash` generation test returned provider HTTP 503 `UNAVAILABLE` due to high demand. The key's model list included `gemini-flash-lite-latest`; a minimal generation request to that model succeeded, then the running application's authenticated chat route returned HTTP 200 in `GENERAL` mode. The local app configuration now uses `gemini-flash-lite-latest`. The API key was not printed.

The first live agent attempt exposed an internal API origin mismatch: the app was running on port 8003, but tool calls defaulted to port 8000. Agent and confirmation services now receive the current request origin. A live menu search returned the MySQL-backed Idli Sambar price and current portions. Five starter TXT documents were indexed through the admin upload endpoint; a live cancellation-policy question returned `RAG` mode and four source citations.

The browser preview screenshots use a separate isolated SQLite database. Automated tests use SQLite and mocked Gemini/Chroma adapters; a real document-to-Chroma upload/index/search workflow has not yet been exercised.