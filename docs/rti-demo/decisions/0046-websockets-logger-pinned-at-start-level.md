<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# 46. A log level set while running leaves the `websockets` logger at its start level, so tokens stay out of the log

- Status: proposed
- Date: 2026-11-03

## Context

With [0044](0044-log-level-while-running.md), anyone who reaches the BFF can put the BFF, the SO or an FSP on `debug`
from the HMI. The BFF has no authentication, and neither do the SO's and FSP's APIs. A level set that way reaches every
library logging under the root logger. [Spec 0010](../specs/0010-bff-log-level-from-hmi.md) asked to check, before
building, that none of them logs tokens or OAuth client secrets at `debug`. The check (2026-11-03, `websockets` 16.1,
urllib3 and the ws61850 library in this repository):

- **`websockets`** logs every handshake header at `debug`, on both sides, `Authorization: Bearer <token>` among them.
  The FSP sends that header to the SO, and the SO receives it ([0007](0007-bff-reapplies-security-config.md)).
- **urllib3** logs the method, URL and status of each request, not headers or bodies.
- **The ws61850 library** (`ws61850.security`, `ws61850.transport`) logs no headers, tokens or secrets.

A token in a container log can be read by anyone with `docker logs`, and is kept as long as the log is.

Options considered:

1. **Leave `websockets` at its start level** when the level is changed while running (chosen).
2. **Redact the header**: a logging filter that replaces the `Authorization` value. It keeps the handshake lines, but
   depends on how `websockets` formats them, and a change in a later version would leak again without a test failing.
3. **Accept it**: the demo runs in a lab. But the tokens are real OAuth tokens from the lab's Keycloak, and a log is
   easily shared when asking for help.
4. **Require authentication on `/api/log-level`**: the lasting answer for who may change a level, left for when the
   services check tokens. It doesn't stop a permitted user from leaking tokens into the log.

## Decision

1. **`PINNED_LOGGERS = ("websockets",)`** in `rti_common.log_level`. At start, its own level is recorded. A change from
   the HMI sets it to the start level, so `websockets.client` and `websockets.server` don't follow a change to
   `debug`. Going back to the start level puts its own level back (`NOTSET`, so it follows the root logger again).
2. **Starting with `LOG_LEVEL=debug` or `--log-level debug` still logs the headers**, as before. That needs a change to
   the deployment and a restart, by someone who can read the configuration and its secrets anyway.
3. **Any library found later to log secrets at `debug`** is added to `PINNED_LOGGERS`, with a test.
4. **A test pins it:** after `PUT /api/log-level` with `debug`, `websockets.client` isn't enabled for `debug`.

## Consequences

- A level raised from the HMI can't write tokens to the log.
- The `websockets` handshake lines don't show when `debug` is set from the HMI. Looking into a handshake problem
  still means starting the service with `LOG_LEVEL=debug`, and the user should know the log then holds tokens.
- `GET /api/log-level` reports the root logger's level; it doesn't say that `websockets` is held back. The route's
  description and the READMEs say it.
- The check was made for the versions of 2026-11-03. Upgrading `websockets`, urllib3 or the ws61850 library means
  checking again what they log at `debug`.

## In the code

- `examples/rti-demo/modules/common/src/rti_common/log_level.py` (`PINNED_LOGGERS`, `LogLevelState.start`,
  `LogLevelState.change`)
- `examples/rti-demo/modules/common/tests/test_log_level.py` (`test_put_leaves_websockets_at_the_start_level`)
