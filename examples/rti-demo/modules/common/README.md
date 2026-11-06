<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# rti-common

Code the RTI demo's BFF, SO and FSP share. A uv workspace member (`rti-common`, import `rti_common`); each of the
three depends on it, and their Dockerfiles copy it in whole.

## `rti_common.log_level`

The services' log level, at start and while they run (specs
[0010](../../../../docs/rti-demo/specs/0010-bff-log-level-from-hmi.md) and
[0011](../../../../docs/rti-demo/specs/0011-so-fsp-log-level-from-hmi.md)).

- `resolve_log_level(value)`: `critical`, `error`, `warning`, `info`, `debug`, `trace` (as `debug`) or a number, in
  any case; an unknown or empty value is `info`. For `LOG_LEVEL` and `--log-level` at start.
- `start_from_env()` at import and `start_from_args(args.log_level, sys.argv[1:])` in `__main__`: set the root
  logger, and record the start level and where it came from (`--log-level`, `LOG_LEVEL` or `default`).
- `uvicorn_level(arg, resolved)`: the `log_level` for `uvicorn.run`, the name it knows or the number.
- `add_log_level_routes(router, on_change)` (the SO and FSP, on their `/api` router) and
  `log_level_router(on_change)` (the BFF): `GET` and `PUT /api/log-level`.

`PUT /api/log-level` with `{"level": "debug"}` sets the root logger and `uvicorn.error`, `uvicorn.access` and
`uvicorn.asgi`; `{"level": null}` goes back to the start level. It takes the names above or a number from 1 to 50; an
unknown value is a 422, with the names, and changes nothing. `on_change(message)` is called before the new level
applies, so a change to `error` is still recorded; each service records it its own way. `websockets` stays at the
start level (`PINNED_LOGGERS`): at debug it logs every WebSocket handshake header, `Authorization: Bearer <token>`
among them. The level is kept in memory only.

```json
{"level": "debug", "value": 10, "source": "hmi", "changed_at": "2026-11-03T14:02:11Z",
 "start": {"level": "info", "value": 20, "source": "LOG_LEVEL"}}
```

`level` names `value` as the HMI does (decision 0043): up to 10 `debug`, 20 `info`, 30 `warning`, 40 `error`, above
that `critical`.

## Tests

```bash
uv run --package rti-common pytest examples/rti-demo/modules/common/tests -m unit -q
```
