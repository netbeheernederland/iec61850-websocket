# SPDX-FileCopyrightText: 2026 Netbeheer Nederland
# SPDX-License-Identifier: Apache-2.0

"""The FSP's GET and PUT /api/log-level (spec 0011).

The route itself is tested in modules/common; here: that the FSP has it,
records a change in its actions log, and that its health-check filter
follows the new level.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fsp import bff_endpoint
from rti_common import log_level

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
def client_and_instance(tmp_path):
    (tmp_path / "model.py").write_text(
        "from ws61850.iec61850.data_model.ied_model import IedModel\n"
        "ied = IedModel(name='TestIED')\n",
        encoding="utf-8",
    )
    app = FastAPI()
    router, instance = bff_endpoint.create_bff_router(tmp_path)
    app.include_router(router)
    return TestClient(app), instance


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


def test_get_log_level(client_and_instance):
    client, _ = client_and_instance
    body = client.get("/api/log-level").json()
    assert set(body) == {"level", "value", "source", "changed_at", "start"}


def test_put_records_a_system_entry_in_the_actions_log(client_and_instance):
    client, instance = client_and_instance
    start = log_level.level_name(log_level.STATE.start_value).upper()
    response = client.put("/api/log-level", json={"level": "debug"})
    assert response.status_code == 200
    assert response.json()["source"] == "hmi"
    entry = list(instance.runtime.actions)[-1]
    assert entry["kind"] == "system"
    assert entry["level"] == "warn"
    assert entry["message"] == f"Log level set to DEBUG (was {start}) from the HMI"


def test_put_unknown_is_422_and_records_nothing(client_and_instance):
    client, instance = client_and_instance
    before = len(instance.runtime.actions)
    assert client.put("/api/log-level", json={"level": "loud"}).status_code == 422
    assert len(instance.runtime.actions) == before


def test_health_check_lines_follow_the_level(client_and_instance):
    client, _ = client_and_instance
    health_filter = bff_endpoint.HealthCheckAccessFilter()
    client.put("/api/log-level", json={"level": "debug"})
    assert health_filter.filter(_health_record()) is True
    client.put("/api/log-level", json={"level": "info"})
    assert health_filter.filter(_health_record()) is False


def test_apis_lists_the_route(client_and_instance):
    client, _ = client_and_instance
    paths = {e["path"] for e in client.get("/api/apis").json()["endpoints"]}
    assert "/api/log-level" in paths
