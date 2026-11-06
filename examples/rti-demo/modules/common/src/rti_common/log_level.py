# SPDX-FileCopyrightText: 2026 Netbeheer Nederland
# SPDX-License-Identifier: Apache-2.0

"""The log level of the BFF, SO and FSP: set at start, changed while running.

At start the level comes from ``--log-level``, then ``LOG_LEVEL``, then
``info`` (``start_from_args`` / ``start_from_env``). ``log_level_router`` adds
``GET`` and ``PUT /api/log-level``, which read and change it while the
service runs (specs 0010 and 0011). A changed level is kept in memory only: a
restart goes back to the start level.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

#: The names ``--log-level`` and ``PUT /api/log-level`` take; ``trace`` is
#: uvicorn's and means ``debug`` here.
LEVEL_NAMES = ("critical", "error", "warning", "info", "debug", "trace")

#: uvicorn sets these itself, from ``uvicorn.run(log_level=...)``; a change
#: sets them with the root logger.
UVICORN_LOGGERS = ("uvicorn.error", "uvicorn.access", "uvicorn.asgi")

#: Loggers a change leaves at the start level. At debug, ``websockets`` logs
#: every handshake header, ``Authorization: Bearer <token>`` among them.
PINNED_LOGGERS = ("websockets",)


def resolve_log_level(value: str | None, default: int = logging.INFO) -> int:
    """Map a level name (case-insensitive) to a logging constant.

    Falls back to ``default`` for unknown/empty values instead of letting
    ``basicConfig`` raise ``ValueError`` and abort startup. Also accepts a
    numeric string (e.g. "10") and uvicorn's "trace" alias.
    """
    if value is None:
        return default
    name = str(value).strip().upper()
    if not name:
        return default
    if name.isdigit():
        return int(name)
    if name == "TRACE":  # uvicorn alias, no stdlib equivalent
        return logging.DEBUG
    level = logging.getLevelName(name)  # returns int for known names, str otherwise
    return level if isinstance(level, int) else default


def parse_log_level(value: str | int) -> int:
    """Like ``resolve_log_level``, but an unknown value is an error.

    For a value someone typed, which should be told it is wrong rather than
    quietly become ``info``. Numbers are 1 to 50 (0 would log everything).
    """
    if isinstance(value, bool):
        raise ValueError(f"unknown log level {value!r}")
    if isinstance(value, int):
        number = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("the log level is empty")
        number = resolve_log_level(text, default=-1)
        if number < 0:
            raise ValueError(f"unknown log level {text!r}")
    if not 1 <= number <= logging.CRITICAL:
        raise ValueError(f"log level {number} is not between 1 and 50")
    return number


def level_name(value: int) -> str:
    """The name for a level, as the HMI names it (decision 0043)."""
    if value <= logging.DEBUG:
        return "debug"
    if value <= logging.INFO:
        return "info"
    if value <= logging.WARNING:
        return "warning"
    if value <= logging.ERROR:
        return "error"
    return "critical"


def _label(value: int) -> str:
    name = level_name(value).upper()
    return name if value == logging.getLevelName(name) else f"{name} ({value})"


def start_source(argv: Sequence[str], env: Mapping[str, str]) -> str:
    """Where the start level came from: ``--log-level``, ``LOG_LEVEL`` or ``default``."""
    if any(a == "--log-level" or a.startswith("--log-level=") for a in argv):
        return "--log-level"
    if (env.get("LOG_LEVEL") or "").strip():
        return "LOG_LEVEL"
    return "default"


def uvicorn_level(arg: str, resolved: int) -> str | int:
    """The ``log_level`` for ``uvicorn.run``: the name it knows, or the number."""
    name = str(arg).strip().lower()
    return name if name in LEVEL_NAMES else resolved


class LogLevelState:
    """The start level and the level in use, for one process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.start_value = logging.INFO
        self.start_source = "default"
        self.value = logging.INFO
        self.source = "start"
        self.changed_at: str | None = None
        self._pinned_own: dict[str, int] = {}

    def start(self, value: int, source: str) -> None:
        """Record the start level and set the root logger to it.

        The uvicorn loggers are left to ``uvicorn.run``, which sets them.
        """
        with self._lock:
            self.start_value = value
            self.start_source = source
            self.value = value
            self.source = "start"
            self.changed_at = None
            self._pinned_own = {
                name: logging.getLogger(name).level for name in PINNED_LOGGERS
            }
        logging.getLogger().setLevel(value)

    def change_message(self, value: int | None) -> str:
        """The message recorded for a change to ``value`` (None: the start level)."""
        if value is None:
            return (
                f"Log level set to {_label(self.start_value)} "
                f"(was {_label(self.value)}, the start level) from the HMI"
            )
        return (
            f"Log level set to {_label(value)} (was {_label(self.value)}) from the HMI"
        )

    def change(self, value: int | None) -> None:
        """Use ``value`` from now on; None goes back to the start level."""
        with self._lock:
            back = value is None
            new = self.start_value if back else value
            self.value = new
            self.source = "start" if back else "hmi"
            self.changed_at = (
                None if back else datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            for name in ("", *UVICORN_LOGGERS):
                logging.getLogger(name or None).setLevel(new)
            for name in PINNED_LOGGERS:
                own = self._pinned_own.get(name, logging.NOTSET)
                if back or own != logging.NOTSET:
                    logging.getLogger(name).setLevel(own)
                else:
                    logging.getLogger(name).setLevel(self.start_value)

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "level": level_name(self.value),
                "value": self.value,
                "source": self.source,
                "changed_at": self.changed_at,
                "start": {
                    "level": level_name(self.start_value),
                    "value": self.start_value,
                    "source": self.start_source,
                },
            }


#: The process's state: logging is per process, and so is this.
STATE = LogLevelState()


def start_from_env(env: Mapping[str, str] | None = None) -> int:
    """At import: the level from ``LOG_LEVEL``, or ``info``; sets the root logger."""
    env = os.environ if env is None else env
    value = resolve_log_level(env.get("LOG_LEVEL"))
    STATE.start(value, start_source((), env))
    return value


def start_from_args(
    arg: str, argv: Sequence[str], env: Mapping[str, str] | None = None
) -> int:
    """In ``__main__``: the level from ``--log-level`` (whose default is ``LOG_LEVEL``)."""
    env = os.environ if env is None else env
    value = resolve_log_level(arg)
    STATE.start(value, start_source(argv, env))
    return value


class LogLevelBody(BaseModel):
    """``PUT /api/log-level``: a name, a number, or null for the start level."""

    level: str | int | None


def log_level_router(
    on_change: Callable[[str], None] | None = None,
    *,
    state: LogLevelState = STATE,
    prefix: str = "/api",
    tags: Sequence[str] = ("Logging",),
) -> APIRouter:
    """A router with ``GET`` and ``PUT {prefix}/log-level``; see ``add_log_level_routes``."""
    router = APIRouter(prefix=prefix)
    add_log_level_routes(router, on_change, state=state, tags=tags)
    return router


def add_log_level_routes(
    router: APIRouter,
    on_change: Callable[[str], None] | None = None,
    *,
    state: LogLevelState = STATE,
    tags: Sequence[str] = ("Logging",),
) -> None:
    """Add ``GET`` and ``PUT /log-level`` to ``router`` (under its prefix).

    Added to the router itself rather than included as a router of their
    own, so they are ordinary routes of it (the SO's and FSP's ``/api/apis``
    lists those). ``on_change(message)`` is called before the new level
    applies, so a change to ``error`` is still recorded. Each service records
    it in its own way (the BFF's system events, the SO's and FSP's actions
    log).
    """

    @router.get(
        "/log-level",
        tags=list(tags),
        summary="The log level in use",
        description="The level this service logs at now, and the level it started with.",
    )
    def get_log_level() -> dict[str, Any]:
        return state.as_dict()

    @router.put(
        "/log-level",
        tags=list(tags),
        summary="Set the log level",
        description=(
            "Set the level while the service runs: one of "
            + ", ".join(LEVEL_NAMES)
            + " (any case), or a number from 1 to 50. null goes back to the start "
            "level. Kept in memory only: a restart goes back to LOG_LEVEL / "
            "--log-level. The websockets logger stays at the start level."
        ),
        responses={422: {"description": "Unknown log level; nothing changed"}},
    )
    def put_log_level(body: LogLevelBody) -> dict[str, Any]:
        value = None
        if body.level is not None:
            try:
                value = parse_log_level(body.level)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"{exc}: use one of {', '.join(LEVEL_NAMES)}, or a number from 1 to 50",
                ) from None
        message = state.change_message(value)
        if on_change is not None:
            on_change(message)
        state.change(value)
        return state.as_dict()
