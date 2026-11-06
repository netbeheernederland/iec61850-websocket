<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# 0011. Set the SO's and FSPs' log level from the HMI's panels

- Status: done (2026-11-03, commits 724e835 and 59e8582, decisions 0044, 0045 and 0046)
- Date: 2026-11-03
- Changes: SO, FSP (new route, shared with the BFF), HMI (ACSI Client and ACSI Server pages)

## Goal

Change how much an SO or FSP logs while it runs, from its own page in the HMI. A user looking into a problem with one
instance, say `rti-fsp02`, can turn on `debug` for that instance only, read its log, and set it back. No restart, and
no change to `docker-compose.yml`. This is spec 0010 for the BFF, applied to the SO and the FSPs, with the same route
and the same behaviour.

## Now

- The SO and each FSP set their level once, at start, as the BFF does. `LOG_LEVEL` is read at import, then
  `--log-level` in `__main__` wins (`resolve_log_level` in `so/bff_endpoint.py` and `fsp/bff_endpoint.py`). The level
  goes to the root logger and, through `uvicorn.run(log_level=...)`, to the three uvicorn loggers.
- `resolve_log_level` is written three times: in the BFF, the SO and the FSP. So is `HealthCheckAccessFilter`, with a
  different `QUIET_PATHS` in each.
- Changing an instance's level means restarting its container: `LOG_LEVEL=debug docker compose up -d rti-fsp02`.
  `LOG_LEVEL` in `docker-compose.yml` is one value for the whole stack.
- The SO and FSP have no route that reads or sets their log level. `/api/status` and `/api/properties` don't report
  it.
- The HMI reaches the SO and FSPs only through the BFF's `POST /api/execute` (decision 0004). `apiService.js` lists
  each call. When the instance answers with an error, `/api/execute` returns a 500 that includes the instance's
  reason (`_upstream_error`).
- The ACSI Server page (FSP) and ACSI Client page (SO) each have an instance selector at the top. Then come
  Connection Status, the model, the Plugins panel and Monitoring. Monitoring's buttons (Start Monitor, Stop Monitor,
  Clear Logs) are disabled while no instance is selected. Its Activity Log shows the instance's actions log
  (`_log_action`), which is kept apart from the Python log: the log level doesn't filter it.
- A `kind="system"` entry in an instance's actions log also shows on the Diagnostics page.

## Proposal

### Shared code for the BFF, SO and FSP

A small workspace package, `modules/common` (`rti-common`, import `rti_common`), holds what the three services now
copy, plus the route of spec 0010:

- `rti_common.log_level.resolve_log_level`: the function as it is.
- `LogLevelState`: the start level and its source (`"--log-level"`, `"LOG_LEVEL"` or `"default"`), the level in use,
  when it was changed, and `apply(level)`. `apply` sets the root logger and `uvicorn.error`, `uvicorn.access` and
  `uvicorn.asgi`.
- `log_level_router(state, on_change)`: an `APIRouter` with `GET` and `PUT /api/log-level`, the bodies and the 422 of
  spec 0010. `on_change(old, new)` is called before the new level applies. Each service records the change in its own
  way there.
- The BFF, SO and FSP use it, and their three `resolve_log_level` copies go. `HealthCheckAccessFilter` stays in each
  service, since the quiet paths differ.

If 0010 is built first, it builds this package and 0011 only adds the SO and FSP to it. If the two specs are built
together, they share one commit for the package.

### The SO and FSP: `GET` and `PUT /api/log-level`

The same route and bodies as the BFF in spec 0010:

```json
{
  "level": "debug",
  "value": 10,
  "source": "hmi",
  "changed_at": "2026-11-03T14:02:11Z",
  "start": {"level": "info", "value": 20, "source": "LOG_LEVEL"}
}
```

- `PUT` with `{"level": "debug"}`, a number or `trace` sets the level. `{"level": null}` goes back to the start
  level. An unknown or empty value is a 422, and nothing changes.
- The change is written to the actions log before it applies, with `_log_action(..., "warn", kind="system")` and the
  message "Log level set to DEBUG (was INFO) from the HMI". The Activity Log and the Diagnostics page then show it,
  and it is written even when the new level is `error`. The container's log also gets a WARNING line with the same
  text.
- The level is only kept in memory. A restart goes back to `LOG_LEVEL` / `--log-level`.
- The level is per instance: setting `rti-fsp02` to `debug` leaves `rti-fsp01`, the SO and the BFF as they are.
- The route is under the same tag as the rest of each service's API. The plugins don't get it: they are services of
  their own (decision 0029), and their log level is outside this spec.

### The HMI: ACSI Server and ACSI Client pages

- In Monitoring, after Clear Logs, a "Log level" select for the instance chosen at the top of the page. Its first
  option is "As started (info, from LOG_LEVEL)", then come the six names. A short line under the buttons says what it
  sets: "The container log of rti-fsp02 (`docker logs`); the Activity Log below shows every entry at any level." The
  select doesn't filter the Activity Log. Its severity filter does that.
- A line next to it says "In use: debug, set from the HMI at 14:02".
- The level is read with `GET /api/log-level` through `/api/execute`:
  - when the page opens,
  - when another instance is selected,
  - and after a change.

  It isn't read on every status poll.
- Choosing a level sends the `PUT` straight away, with no save button. The select is disabled while the request runs.
  On an error the select goes back to the instance's level, and the page's message bar shows the instance's reason.
- While no instance is selected or the instance can't be reached, the select is disabled, as the Monitoring buttons
  are.
- The choice isn't kept in localStorage: the level lives in the instance, and every tab and user sees the same one.
  The last change wins.
- `apiService.js` gets `log-level` (`GET /api/log-level`) and `log-level-set` (`PUT /api/log-level`) in
  `API_DEFINITIONS`, called with `executeApiCall` as the other calls are.
- A `LogLevelSelect` component is shared by both pages. Spec 0010's select on the Settings page uses it too, if it
  is built in the same change or later.

### What the BFF changes

Nothing. `/api/execute` already forwards `GET` and `PUT` to any path on a registered target.

## Acceptance

- The stack is started with `LOG_LEVEL=info`. On ACSI Server with `rti-fsp02` selected, Monitoring's "Log level" says
  "As started (info, from LOG_LEVEL)".
- Choosing `debug` makes `docker logs rti-fsp02` show debug lines, with no restart, including the health-check access
  lines and the ws61850 library's. `rti-fsp01`'s log doesn't change.
- The Activity Log of `rti-fsp02` and the Diagnostics page show "Log level set to DEBUG (was INFO) from the HMI".
- Selecting `rti-fsp01` shows `info`, and selecting `rti-fsp02` again shows `debug`.
- "As started" goes back to `info`.
- On ACSI Client the same works for the SO.
- `docker compose restart rti-fsp02` brings back `info`.
- Started with `--log-level warning`, the first option says "As started (warning, from --log-level)".
- `PUT /api/log-level` with `{"level": "loud"}` on an FSP is a 422 and leaves the level as it was. Through the HMI,
  the message bar shows the reason.
- With no instance selected, or the instance stopped, the select is disabled.

## Tests

- `modules/common/tests/test_log_level.py`: `resolve_log_level` (moved from the three services' tests), and
  `LogLevelState.apply` on the root logger and the three uvicorn loggers. The router on a bare `FastAPI` app:
  - `GET` at start,
  - `PUT` with a name, a number, `TRACE` and mixed case,
  - `PUT null`,
  - the 422,
  - `on_change` called before the level applies.

  A fixture restores the loggers after each test.
- `fsp/tests` and `so/tests`: `PUT /api/log-level` writes the `kind="system"` entry to the actions log, and
  `HealthCheckAccessFilter` follows the new level.
- `apiService.test.js`: the two definitions.
- `LogLevelSelect.test.jsx`:
  - reads the level,
  - sends the `PUT` on a change,
  - goes back on an error,
  - is disabled without a target,
  - doesn't write localStorage.
- `ACSIServer.test.jsx`, `ACSIClient.test.jsx`: the level is read again when another instance is selected.

## Docs to update

- The SO and FSP READMEs: the route, and that the level isn't kept across a restart.
- HMI README: the Monitoring panel.
- `docs/architecture/logging.md`: each service's level can change while it runs; the actions log isn't filtered by
  it.
- The wireframe: ACSI Server and ACSI Client, Monitoring.
- [README.md](README.md): this spec's row.
- When built: one decision for 0010 and 0011 together (the route, the shared package, the 422, a level kept in memory
  only).

## Answered

As built (decisions [0044](../decisions/0044-log-level-while-running.md),
[0045](../decisions/0045-shared-python-package-rti-common.md) and
[0046](../decisions/0046-websockets-logger-pinned-at-start-level.md)):

- **Where the select goes.** Built as proposed, in Monitoring's button row (`ActionLogPanel`'s `toolbar`). Proposed:
  in Monitoring, since that is where a user looks at logs. The downside is that Monitoring's Activity Log isn't
  affected by it, which the line under the buttons has to explain. Another place would be the Connection Status panel,
  next to the instance's address.
- **A shared package or three copies?** Built: the package, `modules/common`. On the SO and FSP the routes are added
  to their `/api` router (`add_log_level_routes`), not included as a router, so `/api/apis` lists them. Proposed: the
  package, since a third service is getting the route and the code is already copied three times. The cost is one more
  workspace member and an extra `COPY` in each Dockerfile. The alternative is to put it in `acsi-plugins`, which the
  SO and FSP already depend on. The BFF doesn't, though, and the code has nothing to do with plugins.
- **All instances at once?** A "set for every instance" action, on Settings or Diagnostics, that goes through the BFF
  to every SO and FSP. Proposed: not now. One `LOG_LEVEL` in `docker-compose.yml` already does that at start.
- **Keep the level across a restart, and who may change it:** as in spec 0010 (no, and anyone who reaches the BFF).
  The check that no library logs tokens or OAuth client secrets at `debug` matters more here. The FSP and SO do the
  TLS and OAuth handshakes themselves (`ws61850.security`, `ws61850.transport`). **Checked:** `websockets` logs the
  `Authorization` header at `debug`, so a change leaves it at the start level, as for the BFF.
