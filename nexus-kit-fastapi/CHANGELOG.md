# Changelog

## [0.1.0] — 2026-07-17

Initial release, extracted from a production WhatsApp gateway.

- `HttpService(ServiceInterface)` — uvicorn as a nexus lifecycle service:
  subclass, implement `create_app()`, set host/port. `start()` returns only
  after the socket is bound (startup failures raise immediately, so
  `ServiceRunner` rolls back cleanly); graceful idempotent `stop()`;
  `wait()` blocks until the server exits; `port = 0` + `bound_port` for
  ephemeral ports.
- `Injected(cls)` — a plain FastAPI `Depends` resolving from the nexus
  container; kills the per-service `get_x()` dependency boilerplate.
- `attach_container` / `get_container` — the underlying bridge, usable
  directly in TestClient setups and hand-written dependencies.
