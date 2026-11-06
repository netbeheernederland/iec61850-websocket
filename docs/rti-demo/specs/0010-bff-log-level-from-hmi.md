<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# 0010. Set the BFF's log level from the HMI's Settings page

- Status: done (2026-11-03, commits 724e835 and 59e8582, decisions 0044, 0045 and 0046)
- Date: 2026-11-03
- Changes: BFF (new route), HMI (Settings page, apiService)

## Goal

Change how much the BFF logs while it runs, from the HMI's Settings page. A user looking into a problem can turn on
`debug` for the BFF, look at the log, and set it back, without restarting the container or editing
`docker-compose.yml`. The HMI's Settings page shows the level the BFF uses now, and where that level came from.

## Now

- The BFF sets its level once, at start: `LOG_LEVEL` at import (`resolve_log_level` in `bff_server.py`), then
  `--log-level` in `__main__`, which wins. An unknown or empty value is `info`. The level goes to the root logger and,
  through `uvicorn.run(log_level=...)`, to `uvicorn.error`, `uvicorn.access` and `uvicorn.asgi`, which uvicorn sets
  on their own.
- `HealthCheckAccessFilter` moves the access-log lines for `/api/status`, `/api/health` and `/api/messages` down to
  `DEBUG`. They only show when `uvicorn.access` is at `debug`.
- Changing the level means restarting the BFF: `LOG_LEVEL=debug docker compose up -d rti-bff`.
- The BFF has no route that reads or sets its log level. `/api/health` and `/api/stats` don't report it.
- The HMI's Settings page has a "BFF Server Configuration" group (host, port, "Save Settings and Test BFF
  Connection", and a connected/disconnected status). It also has a "Logging" group whose "Log level" select sets the
  HMI's own level in the browser (spec 0008). Nothing on the page shows or changes the BFF's level.
- `conn_manager.log_event` records a BFF system event, which the Diagnostics page shows (source "BFF").

## Proposal

### The BFF: `GET` and `PUT /api/log-level`

`GET /api/log-level` returns the level in use and the level the BFF started with:

```json
{
  "level": "debug",
  "value": 10,
  "source": "hmi",
  "changed_at": "2026-11-03T14:02:11Z",
  "start": {"level": "info", "value": 20, "source": "LOG_LEVEL"}
}
```

- `source` is `"start"` until the level is changed, then `"hmi"`. For `start.source` the values are `"--log-level"`,
  `"LOG_LEVEL"` or `"default"`. `__main__` records which one applied. Started without `__main__` (`uvicorn
  bff.bff_server:app`, pytest), it is `"LOG_LEVEL"` or `"default"`.
- `changed_at` is `null` until the level is changed.
- `level` is the name for `value`, as the HMI names it (decision 0043): ≤10 `debug`, ≤20 `info`, ≤30 `warning`, ≤40
  `error`, otherwise `critical`.

`PUT /api/log-level` with `{"level": "debug"}` sets the level, and returns the same body as `GET`:

- `level` takes what `resolve_log_level` takes: the six names, case-insensitive (`trace` is `debug`), or a number.
- An unknown or empty value gets a 422 that lists the names, and the level stays as it was. At start an unknown value
  is quietly `info`. Here the user typed it, so the BFF says it is wrong.
- `{"level": null}` goes back to the start level, and `source` is `"start"` again.
- The level goes to the root logger and to `uvicorn.error`, `uvicorn.access` and `uvicorn.asgi`, as at start. The
  health-check access lines then follow it: they show at `debug` and are hidden again above it.
- The change is recorded with `conn_manager.log_event(..., level="warn")`, before the new level applies, so it shows
  even when going to `error`. The message is "Log level set to DEBUG (was INFO) from the HMI". It shows in the BFF's
  log and on the Diagnostics page.
- The level isn't kept. A restart goes back to `LOG_LEVEL` / `--log-level`.

Both routes are under the "Diagnostics" tag in the BFF's OpenAPI. nginx already proxies `/api/` to the BFF.

### The HMI: Settings page, "BFF Server Configuration"

- A "BFF log level" select under the port field, before the save button, with "As started (info, from LOG_LEVEL)"
  first and then the six names. It shows the level the BFF uses now.
- Below it: "In use: debug, set from the HMI at 14:02", or "In use: info, as started (from LOG_LEVEL)".
- The select is read with `GET /api/log-level` when the page opens and after each connection check that succeeds,
  including after the BFF address changes.
- Choosing a level sends the `PUT` straight away, with no save button, as for the HMI's own level. The select is
  disabled while the request runs. On an error, the select goes back to the BFF's level and the error shows below it.
- While the BFF isn't connected, the select is disabled and says "Connect to the BFF to see its log level".
- The choice isn't kept in localStorage: the level lives in the BFF, and every tab and user sees the same one. Two
  tabs that change it: the last change wins, and the other tab shows it the next time it reads the level.
- To tell the two levels apart, the "Logging" group's select is renamed "HMI log level (this browser)".
- `apiService.js` gets `getBffLogLevel()` and `setBffLogLevel(level)`, which call the BFF directly as `/api/health`
  does (not through `/api/execute`, which is for the SO and FSPs).

## Acceptance

- The BFF is started with `LOG_LEVEL=info`. On the Settings page, "BFF log level" shows "As started (info, from
  LOG_LEVEL)".
- Choosing `debug`: the BFF's log shows debug lines, including the health-check access lines, without a restart.
  The log and Diagnostics show "Log level set to DEBUG (was INFO) from the HMI".
- Choosing "As started" goes back to `info`; the health-check lines are gone again.
- `docker compose restart rti-bff`: the level is back to `info` and the page says so after the next connection
  check.
- `--log-level warning` on the command line: the select's first option says "As started (warning, from
  --log-level)".
- `PUT /api/log-level` with `{"level": "loud"}`: 422, and the level is unchanged.
- With the BFF stopped, the select is disabled.

## Tests

- `bff/tests/test_log_level.py` (FastAPI `TestClient`):
  - `GET` at start, with and without `LOG_LEVEL`.
  - `PUT` with a name, a number, `TRACE` and mixed case: the levels of the root logger and the three uvicorn
    loggers.
  - `PUT null` goes back to the start level.
  - `PUT` with an unknown or empty value: 422, nothing changed.
  - The event is in `/api/diagnostics`, and recorded before a change to `error`.
  - `HealthCheckAccessFilter` passes health lines after a change to `debug`, and drops them after a change back.
  - A fixture puts the loggers back after each test, since the levels are global.
- `apiService.test.js`: the two calls, their URLs and bodies.
- `Settings.test.jsx`:
  - The select is read after a connection check.
  - Choosing a level sends the `PUT` and shows the answer.
  - On an error the select goes back and the error shows.
  - It is disabled while disconnected.
  - It doesn't write localStorage.

## Docs to update

- The BFF README: the route, and that the level isn't kept across a restart.
- HMI README: the Settings page.
- `docs/architecture/logging.md`: the BFF's level can change while it runs.
- The wireframe (Settings).
- [README.md](README.md): this spec's row.
- When built: a decision for the route, the 422 on unknown values and the in-memory level.

## Answered

As built (decisions [0044](../decisions/0044-log-level-while-running.md),
[0045](../decisions/0045-shared-python-package-rti-common.md) and
[0046](../decisions/0046-websockets-logger-pinned-at-start-level.md)):

- **The FSPs and SO too?** Yes: [spec 0011](0011-so-fsp-log-level-from-hmi.md) adds the same route to them, for
  the ACSI Client and ACSI Server pages. It moves `resolve_log_level` and this route into a shared package that the
  BFF uses too.
- **Keep the level across a restart?** Proposed: no. A raised level is for looking into a problem, and a restart that
  goes back to the configured level is the safer default. Keeping it would mean a file next to `connections.json`.
- **Who may change it?** The BFF has no authentication, and every client that reaches it can already add and delete
  connections. This route is no different, but `debug` writes more to the log. The BFF's own debug lines
  (`connection_manager.py`) are status checks only. The libraries under the root logger (urllib3, websockets, the
  ws61850 library) log at `debug` too, though. Before building this, check that none of them logs tokens or OAuth
  client secrets. If one does, leave its logger at its start level. **Checked:** `websockets` logs every handshake
  header at `debug`, `Authorization: Bearer <token>` among them, so a change leaves it at the start level
  (`PINNED_LOGGERS` in `rti_common.log_level`). urllib3 logs URLs only, and the ws61850 library logs no headers.
- **Go back to the start level on its own after a while** (say 30 minutes at `debug`)? Proposed: no, to keep it
  simple. The Settings page and Diagnostics show the change was made.
