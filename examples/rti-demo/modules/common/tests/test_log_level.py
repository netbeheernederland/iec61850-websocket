# SPDX-FileCopyrightText: 2026 Netbeheer Nederland
# SPDX-License-Identifier: Apache-2.0

"""The shared log level: start, change while running, and the route (specs 0010, 0011)."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rti_common import log_level
from rti_common.log_level import (
    PINNED_LOGGERS,
    UVICORN_LOGGERS,
    LogLevelState,
    level_name,
    log_level_router,
    parse_log_level,
    resolve_log_level,
    start_source,
    uvicorn_level,
)

pytestmark = pytest.mark.unit

ALL = ("", *UVICORN_LOGGERS, *PINNED_LOGGERS)


def _logger(name: str) -> logging.Logger:
    return logging.getLogger(name or None)


@pytest.fixture(autouse=True)
def restore_loggers():
    """The levels are global: put them back after each test."""
    saved = {name: _logger(name).level for name in ALL}
    yield
    for name, level in saved.items():
        _logger(name).setLevel(level)


@pytest.fixture
def state():
    s = LogLevelState()
    s.start(logging.INFO, "LOG_LEVEL")
    return s


@pytest.fixture
def api(state):
    events: list[tuple[str, int]] = []

    def on_change(message: str) -> None:
        # The level when the change is recorded: still the old one.
        events.append((message, logging.getLogger().level))

    app = FastAPI()
    app.include_router(log_level_router(on_change, state=state))
    return TestClient(app), events


# -------------------- names and numbers --------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("debug", logging.DEBUG),
        ("DEBUG", logging.DEBUG),
        (" Warning ", logging.WARNING),
        ("trace", logging.DEBUG),
        ("15", 15),
        ("loud", logging.INFO),
        ("", logging.INFO),
        (None, logging.INFO),
    ],
)
def test_resolve_log_level(value, expected):
    assert resolve_log_level(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("debug", 10),
        ("TRACE", 10),
        ("Critical", 50),
        ("15", 15),
        (15, 15),
        (1, 1),
        (50, 50),
    ],
)
def test_parse_log_level(value, expected):
    assert parse_log_level(value) == expected


@pytest.mark.parametrize("value", ["loud", "", "  ", "0", 0, 51, -1, True])
def test_parse_log_level_rejects(value):
    with pytest.raises(ValueError):
        parse_log_level(value)


@pytest.mark.parametrize(
    ("value", "name"),
    [
        (1, "debug"),
        (10, "debug"),
        (15, "info"),
        (20, "info"),
        (30, "warning"),
        (40, "error"),
        (50, "critical"),
    ],
)
def test_level_name(value, name):
    assert level_name(value) == name


def test_start_source():
    assert (
        start_source(["--log-level", "debug"], {"LOG_LEVEL": "info"}) == "--log-level"
    )
    assert start_source(["--log-level=debug"], {}) == "--log-level"
    assert start_source(["--port", "5000"], {"LOG_LEVEL": "info"}) == "LOG_LEVEL"
    assert start_source([], {"LOG_LEVEL": " "}) == "default"
    assert start_source([], {}) == "default"


def test_uvicorn_level():
    assert uvicorn_level("DEBUG", 10) == "debug"
    assert uvicorn_level("trace", 10) == "trace"
    # A number or an unknown name: the resolved number, which uvicorn takes.
    assert uvicorn_level("15", 15) == 15
    assert uvicorn_level("loud", 20) == 20


# -------------------- start --------------------


def test_start_from_env_sets_the_root_logger(monkeypatch):
    monkeypatch.setattr(log_level, "STATE", LogLevelState())
    assert log_level.start_from_env({"LOG_LEVEL": "warning"}) == logging.WARNING
    assert logging.getLogger().level == logging.WARNING
    assert log_level.STATE.as_dict()["start"] == {
        "level": "warning",
        "value": 30,
        "source": "LOG_LEVEL",
    }


def test_start_from_args(monkeypatch):
    monkeypatch.setattr(log_level, "STATE", LogLevelState())
    value = log_level.start_from_args(
        "error", ["--log-level", "error"], {"LOG_LEVEL": "debug"}
    )
    assert value == logging.ERROR
    assert log_level.STATE.as_dict()["start"]["source"] == "--log-level"


def test_start_without_anything_is_info_from_default(monkeypatch):
    monkeypatch.setattr(log_level, "STATE", LogLevelState())
    log_level.start_from_env({})
    assert log_level.STATE.as_dict()["start"] == {
        "level": "info",
        "value": 20,
        "source": "default",
    }


# -------------------- the route --------------------


def test_get_at_start(api):
    client, _ = api
    assert client.get("/api/log-level").json() == {
        "level": "info",
        "value": 20,
        "source": "start",
        "changed_at": None,
        "start": {"level": "info", "value": 20, "source": "LOG_LEVEL"},
    }


@pytest.mark.parametrize(
    ("level", "value"),
    [("debug", 10), ("TRACE", 10), ("Error", 40), (15, 15), ("15", 15)],
)
def test_put_sets_root_and_uvicorn_loggers(api, level, value):
    client, _ = api
    body = client.put("/api/log-level", json={"level": level}).json()
    assert body["value"] == value
    assert body["source"] == "hmi"
    assert body["changed_at"].endswith("Z")
    for name in ("", *UVICORN_LOGGERS):
        assert _logger(name).level == value, name


def test_put_leaves_websockets_at_the_start_level(api):
    client, _ = api
    client.put("/api/log-level", json={"level": "debug"})
    assert logging.getLogger("websockets").getEffectiveLevel() == logging.INFO
    assert not logging.getLogger("websockets.client").isEnabledFor(logging.DEBUG)
    # Back to the start level: it follows the root logger again.
    client.put("/api/log-level", json={"level": None})
    assert logging.getLogger("websockets").level == logging.NOTSET


def test_put_null_goes_back_to_the_start_level(api):
    client, _ = api
    client.put("/api/log-level", json={"level": "debug"})
    body = client.put("/api/log-level", json={"level": None}).json()
    assert body["value"] == 20
    assert body["source"] == "start"
    assert body["changed_at"] is None
    for name in ("", *UVICORN_LOGGERS):
        assert _logger(name).level == logging.INFO, name


@pytest.mark.parametrize("level", ["loud", "", 0, 99])
def test_put_unknown_is_422_and_changes_nothing(api, level):
    client, events = api
    response = client.put("/api/log-level", json={"level": level})
    assert response.status_code == 422
    assert "critical, error, warning, info, debug, trace" in response.json()["detail"]
    assert logging.getLogger().level == logging.INFO
    assert client.get("/api/log-level").json()["source"] == "start"
    assert events == []


def test_put_without_level_is_422(api):
    client, _ = api
    assert client.put("/api/log-level", json={}).status_code == 422


def test_on_change_is_called_before_the_level_applies(api):
    client, events = api
    client.put("/api/log-level", json={"level": "error"})
    assert events == [("Log level set to ERROR (was INFO) from the HMI", logging.INFO)]


def test_change_messages(api):
    client, events = api
    client.put("/api/log-level", json={"level": "debug"})
    client.put("/api/log-level", json={"level": 15})
    client.put("/api/log-level", json={"level": None})
    assert [m for m, _ in events] == [
        "Log level set to DEBUG (was INFO) from the HMI",
        "Log level set to INFO (15) (was DEBUG) from the HMI",
        "Log level set to INFO (was INFO (15), the start level) from the HMI",
    ]


def test_prefix_and_tags():
    app = FastAPI()
    app.include_router(
        log_level_router(state=LogLevelState(), prefix="", tags=["Diagnostics"])
    )
    operation = app.openapi()["paths"]["/log-level"]["put"]
    assert operation["tags"] == ["Diagnostics"]
