# SPDX-FileCopyrightText: 2026 Netbeheer Nederland
# SPDX-License-Identifier: Apache-2.0

"""The BFF's GET and PUT /api/log-level (spec 0010).

The route itself is tested in modules/common; here: that the BFF has it,
records a change as a BFF system event (the log and Diagnostics), and that
its health-check filter follows the new level.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import pytest

_tmp_connections_file = Path(tempfile.mkdtemp()) / "connections.json"
_tmp_connections_file.write_text("[]", encoding="utf-8")
os.environ.setdefault("BFF_CONNECTIONS_FILE", str(_tmp_connections_file))

from bff import bff_server  # noqa: E402 - must follow the env var default above
from fastapi.testclient import TestClient  # noqa: E402
from rti_common import log_level  # noqa: E402

pytestmark = pytest.mark.unit

LOGGERS = ("", *log_level.UVICORN_LOGGERS, *log_level.PINNED_LOGGERS)


@pytest.fixture(autouse=True)
def restore_levels():
    saved = {n: logging.getLogger(n or None).level for n in LOGGERS}
    yield
    log_level.STATE.change(None)
    for name, level in saved.items():
        logging.getLogger(name or None).setLevel(level)


@pytest.fixture
def client():
    # Not as a context manager: no lifespan, so no status monitor.
    return TestClient(bff_server.app)


def _health_record() -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", "/api/health", "1.1", 200),
        None,
    )


def test_get_log_level(client):
    body = client.get("/api/log-level").json()
    assert body["source"] == "start"
    assert body["start"]["source"] in ("LOG_LEVEL", "default")


def test_put_is_a_system_event_on_diagnostics(client, caplog):
    start = log_level.level_name(log_level.STATE.start_value).upper()
    message = f"Log level set to ERROR (was {start}) from the HMI"
    with caplog.at_level(logging.WARNING):
        assert client.put("/api/log-level", json={"level": "error"}).status_code == 200
    # Logged at WARNING before the level went to ERROR, so it is in the log.
    assert message in caplog.text
    entries = client.get("/api/diagnostics").json()["entries"]
    assert any(
        e["message"] == message and e["source"] == "BFF" and e["level"] == "warn"
        for e in entries
    )


def test_put_unknown_is_422(client):
    response = client.put("/api/log-level", json={"level": "loud"})
    assert response.status_code == 422
    assert client.get("/api/log-level").json()["source"] == "start"


def test_health_check_lines_follow_the_level(client):
    health_filter = bff_server.HealthCheckAccessFilter()
    client.put("/api/log-level", json={"level": "debug"})
    assert health_filter.filter(_health_record()) is True
    client.put("/api/log-level", json={"level": None})
    if log_level.STATE.start_value > logging.DEBUG:
        assert health_filter.filter(_health_record()) is False


def test_openapi_lists_the_route_under_diagnostics(client):
    operation = client.get("/openapi.json").json()["paths"]["/api/log-level"]["put"]
    assert operation["tags"] == ["Diagnostics"]
