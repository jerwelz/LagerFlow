"""Safeguards for the public demo: write rate limits, size caps and periodic resets.

Only installed when LAGERFLOW_DEMO_MODE=true. Everything is kept in memory, which
is enough for the single-process demo deployment (one uvicorn worker).
"""

import re
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.demo import reset_demo_data
from app.errors import error_response
from app.models import Product, StockMovement

WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
MOVEMENT_PATH = re.compile(r"^/products/[^/]+/movements$")
WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENTS = 10_000


class SlidingWindowLimiter:
    """Allows at most `limit` events per key within the last WINDOW_SECONDS."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, now: float) -> float | None:
        """Records an event. Returns None if allowed, otherwise seconds until retry."""
        with self._lock:
            if len(self._events) > MAX_TRACKED_CLIENTS:
                self._events.clear()  # crude, but keeps memory bounded
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - WINDOW_SECONDS:
                events.popleft()
            if len(events) >= self.limit:
                return events[0] + WINDOW_SECONDS - now
            events.append(now)
            return None


def client_ip(request: Request) -> str:
    # Render's proxy appends the real client address as the last X-Forwarded-For
    # entry; earlier entries can be set by the client and are ignored.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class DemoState:
    def __init__(self, settings: Settings, engine: Engine) -> None:
        self.settings = settings
        self.engine = engine
        self.per_client = SlidingWindowLimiter(settings.demo_write_limit_per_minute)
        self.global_writes = SlidingWindowLimiter(settings.demo_global_write_limit_per_minute)
        self.next_reset_at = datetime.now(UTC)
        self._reset_lock = threading.Lock()

    def reset(self) -> None:
        with self._reset_lock:
            self._reset_locked()

    def reset_if_due(self) -> None:
        if datetime.now(UTC) >= self.next_reset_at:
            with self._reset_lock:
                # Checked again: another request may have reset it meanwhile.
                if datetime.now(UTC) >= self.next_reset_at:
                    self._reset_locked()

    def _reset_locked(self) -> None:
        reset_demo_data(self.settings, self.engine)
        self.next_reset_at = datetime.now(UTC) + timedelta(minutes=self.settings.demo_reset_minutes)

    def count(self, model) -> int:
        with Session(self.engine) as session:
            return session.scalar(select(func.count()).select_from(model)) or 0


def install_demo_mode(app: FastAPI, settings: Settings, engine: Engine) -> DemoState:
    state = DemoState(settings, engine)
    state.reset()  # every start begins with fresh demo data
    app.state.demo = state

    @app.middleware("http")
    async def demo_guard(request: Request, call_next):
        # Database work is synchronous; run it off the event loop.
        await run_in_threadpool(state.reset_if_due)
        if request.method in WRITE_METHODS:
            now = time.monotonic()
            retry_after = state.per_client.hit(client_ip(request), now)
            if retry_after is None:
                retry_after = state.global_writes.hit("*", now)
            if retry_after is not None:
                response = error_response(
                    429,
                    "RATE_LIMITED",
                    "Too many write requests in the demo. Please wait a moment.",
                )
                response.headers["Retry-After"] = str(max(1, round(retry_after)))
                return response

            path = request.url.path
            if request.method == "POST" and path == "/products":
                if await run_in_threadpool(state.count, Product) >= settings.demo_max_products:
                    return _limit_reached("products", settings.demo_max_products)
            elif request.method == "POST" and MOVEMENT_PATH.match(path):
                if (
                    await run_in_threadpool(state.count, StockMovement)
                    >= settings.demo_max_movements
                ):
                    return _limit_reached("stock movements", settings.demo_max_movements)
        return await call_next(request)

    @app.get("/demo/info", tags=["demo"])
    def demo_info() -> dict:
        """Demo mode status: when the data is reset next and which limits apply."""
        return {
            "demo_mode": True,
            "next_reset_at": state.next_reset_at,
            "reset_interval_minutes": settings.demo_reset_minutes,
            "limits": {
                "max_products": settings.demo_max_products,
                "max_movements": settings.demo_max_movements,
                "writes_per_minute": settings.demo_write_limit_per_minute,
            },
        }

    return state


def _limit_reached(what: str, limit: int):
    return error_response(
        409,
        "DEMO_LIMIT_REACHED",
        f"The demo allows at most {limit} {what}. The data is reset regularly.",
        {"limit": limit},
    )
