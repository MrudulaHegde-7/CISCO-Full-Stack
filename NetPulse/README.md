# NetPulse

NetPulse is a small modular FastAPI network-device monitoring API. It stores devices and offline-transition alerts in memory; it does not contact devices or use a database. Data resets when the process restarts.

Activate the project's existing virtual environment, then run these commands from this directory:

```bash
python -m uvicorn app.main:app --reload
python -m pytest -q
```

Open http://127.0.0.1:8000/docs for the API documentation.

FastAPI generates `/openapi.json` from the declared routes, request and response models, status codes, and documentation metadata. Swagger UI at `/docs` reads that schema to display the interactive API reference.

The routes handle HTTP requests and translate service errors to HTTP responses. The service applies registration and status-transition rules. The repository owns in-memory storage, and the event function records an alert when an existing device first changes from online to offline. The repository can later be replaced with a database-backed implementation without changing those service rules.