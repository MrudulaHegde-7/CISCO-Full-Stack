# NetPulse

NetPulse is a small modular FastAPI network-device monitoring API. It stores devices and offline-transition alerts in a local SQLite database at `netpulse.db` in the project working directory. Data persists when the server restarts. The simulated probe does not contact devices.

Activate the project's existing virtual environment and install the dependencies, then run these commands from this directory:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
python -m pytest -q
```

Open http://127.0.0.1:8000/docs for the API documentation.

Run the isolated CRUD demonstration with `python -m examples.sqlite_crud_demo`. It creates a temporary SQLite database, demonstrates Create, Read, Update, and Delete, and removes that database when it exits. It does not modify `netpulse.db` or add a public DELETE endpoint.

FastAPI generates `/openapi.json` from the declared routes, request and response models, status codes, and documentation metadata. Swagger UI at `/docs` reads that schema to display the interactive API reference.

The routes handle HTTP requests and translate service errors to HTTP responses. The service applies registration and status-transition rules. The repository owns database reads and writes, and the event function records an alert when an existing device first changes from online to offline. The request-scoped SQLAlchemy session commits once after a successful request and rolls back if an exception occurs, so the status change and its alert are atomic.

Uvicorn is the ASGI server that runs the FastAPI ASGI application. ASGI supports asynchronous endpoints such as the simulated probe. The database routes use synchronous SQLAlchemy sessions and synchronous route handlers, allowing FastAPI to run those database operations in its thread pool rather than blocking the async event loop. This differs from the older synchronous WSGI interface, which does not provide ASGI's native async request model.

Application events are appended as one JSON object per line to `logs/netpulse.jsonl`; Uvicorn startup and access messages remain plain text in the server terminal. The request ID correlates events from one HTTP request, while the device ID identifies the affected network device. INFO records successful workflow events, WARNING records handled 404/409 domain errors, and ERROR records unexpected failures with a stack trace that omits exception messages. The log rotates at 5 MB and retains three backups.

Do not log request bodies, credentials, personal data, or whole exception messages. A final redaction processor masks exact top-level fields named `password`, `token`, `api_key`, `authorization`, and `secret` (case-insensitive); it is only a safety net and does not inspect nested objects. Clients may supply a 1-64 character request ID using letters, numbers, `_`, or `-`; invalid values are replaced with a generated ID.