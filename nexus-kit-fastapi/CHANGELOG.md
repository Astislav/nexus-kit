# Changelog

## [0.2.2] — 2026-07-18

External review round; both cancellation edges reproduced before fixing.

- **A cancelled `stop()` no longer strands the port.** The cancellation
  re-raise happened before `sock.close()` — after a ServiceRunner
  `stop_grace` timeout (which cancels exactly this path) the port stayed
  taken until GC. The socket now closes in a `finally`. Regression test:
  the port is rebindable immediately after a cancelled `stop()`.
- **A cancelled `start()` leaves nothing behind.** Cancelling `start()`
  while uvicorn was still starting (e.g. a hung lifespan) left the serve
  task, the bound socket and the installed signal handlers alive. The
  startup poll now tears all three down on cancellation and re-raises.
- **Double `start()` raises** instead of silently overwriting the first
  server's task/socket/handler state.

## [0.2.1] — 2026-07-18

External review round; both findings reproduced in code before fixing.

- **Failed startup no longer leaks the bound socket.** The failed-lifespan
  path dropped the socket reference without closing it — the port stayed
  taken until garbage collection, so an in-process retry on the same port
  got `EADDRINUSE` (and `stop()` had nothing left to close). The socket is
  now closed right in the failure path. Regression test: the port is
  rebindable immediately after a failed `start()`.
- **Pre-existing signal handlers are saved and restored.** The unix path
  used `loop.add_signal_handler`, which silently clobbers whatever the
  application installed and cannot be undone (asyncio has no API to read
  the current loop handler). The bridge now uses plain `signal.signal` on
  every platform — same reasoning as uvicorn's own capture — saving
  originals on install and restoring them on `stop()`. Regression test
  included.

## [0.2.0] — 2026-07-17

External review round; every finding verified against uvicorn 0.51 sources
before fixing.

- **SIGTERM no longer kills the teardown.** uvicorn's stock signal capture
  restores previous handlers after its shutdown and re-raises the captured
  signal — with default handlers the process died before ServiceRunner
  stopped the remaining services. The bridge now disables uvicorn's capture
  (`_QuietServer`) and owns the conversion: SIGINT/SIGTERM/SIGBREAK →
  graceful drain → full teardown → clean exit; a second signal forces a
  hard stop. Opt out with `handle_signals = False`. Covered by a subprocess
  test (SIGTERM on unix, CTRL_BREAK on Windows).
- **Failed FastAPI lifespan no longer blows through the rollback.** uvicorn
  0.50+ `sys.exit(3)`s inside the serve task; SystemExit from a task
  pierces the event loop past any `except`. The serve task now translates
  it into a `RuntimeError`, so `start()` fails normally and ServiceRunner
  rolls back. Regression test included.
- `stop()` honours a cancellation of its caller instead of swallowing it
  (the server task is cancelled alongside, then the cancellation re-raises).
- `Injected` resolver is now `async` — no more per-request threadpool hop
  for a container lookup — and takes Starlette's `HTTPConnection`, so it
  works in WebSocket dependencies too. For mounted sub-apps, attach the
  container to each sub-app (`request.app` is the innermost app).

## [0.1.0] — 2026-07-17

Initial release, extracted from a production messaging gateway.

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
