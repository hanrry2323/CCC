"""旁路执行结果事件存储与校验。

This module deliberately owns no card state or gate transitions.  It only
validates and appends observation events, leaving the file chain authoritative.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable

MAX_BODY_BYTES = 16 * 1024
MAX_EVENTS_PER_WORK_MINUTE = 30
EVENTS = frozenset(
    {
        "executor_started",
        "executor_completed",
        "executor_failed",
        "executor_suspended",
    }
)
PAYLOAD_FIELDS = frozenset(
    {
        "executor_rc",
        "card_title",
        "result_path",
        "duration_s",
        "probe_status",
        "selftest_status",
        "maintenance",
    }
)
MAINTENANCE_FIELDS = frozenset({"plan_sync", "lesson", "readme", "roadmap"})
STATUS_FIELDS = frozenset({"pass", "fail", "unknown"})
YES_NO = frozenset({"yes", "no"})


class ResultReportError(Exception):
    """A client-visible validation or storage error."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class ResultReportStore:
    """Thread-safe JSONL append store with process-local idempotency/rate limits."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._seen: set[tuple[str, str, str]] = set()
        self._rate: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def token() -> str:
        value = os.environ.get("CCC_RESULT_REPORT_TOKEN", "")
        if value:
            return value
        try:
            from server.config.loader import load_config

            cfg = load_config(str(Path(__file__).resolve().parents[2] / "server" / "config" / "config.env"))
            return str(cfg.get("CCC_RESULT_REPORT_TOKEN", ""))
        except Exception:
            return ""

    @staticmethod
    def events_path() -> Path:
        raw = os.environ.get("CCC_RESULT_REPORT_EVENTS_PATH", "")
        if not raw:
            try:
                from server.config.loader import load_config

                cfg = load_config(
                    str(Path(__file__).resolve().parents[2] / "server" / "config" / "config.env")
                )
                raw = str(cfg.get("CCC_RESULT_REPORT_EVENTS_PATH", ""))
            except Exception:
                raw = ""
        return Path(raw).expanduser() if raw else Path.home() / ".ccc" / "data" / "board-events.jsonl"

    def _check_auth(self, supplied: str) -> None:
        expected = self.token()
        if not expected:
            raise ResultReportError(503, "result report endpoint is not configured")
        if not supplied or not hmac.compare_digest(supplied, expected):
            raise ResultReportError(401, "unauthorized")

    @staticmethod
    def _validate_string(value: Any, name: str, max_len: int) -> str:
        if not isinstance(value, str):
            raise ResultReportError(400, f"{name} must be a string")
        if len(value) > max_len:
            raise ResultReportError(400, f"{name} exceeds {max_len} characters")
        return value

    @classmethod
    def validate_body(cls, body: Any) -> tuple[str, str, str, dict[str, Any]]:
        if not isinstance(body, dict):
            raise ResultReportError(400, "request body must be an object")
        work_id = cls._validate_string(body.get("work_id"), "work_id", 200)
        event = cls._validate_string(body.get("event"), "event", 64)
        if event not in EVENTS:
            raise ResultReportError(400, "event must be one of the supported values")
        event_id = body.get("event_id")
        if event_id is None:
            event_id = str(uuid.uuid4())
        else:
            event_id = cls._validate_string(event_id, "event_id", 200)
        payload = body.get("payload", {})
        if not isinstance(payload, dict):
            raise ResultReportError(400, "payload must be an object")
        unknown = sorted(set(payload) - PAYLOAD_FIELDS)
        if unknown:
            raise ResultReportError(400, f"unknown payload field: {unknown[0]}")
        out: dict[str, Any] = {}
        for name in ("executor_rc", "duration_s"):
            if name in payload:
                value = payload[name]
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ResultReportError(400, f"{name} must be an integer")
                out[name] = value
        for name in ("card_title", "result_path"):
            if name in payload:
                out[name] = cls._validate_string(payload[name], name, 200)
        for name in ("probe_status", "selftest_status"):
            if name in payload:
                value = payload[name]
                if value not in STATUS_FIELDS:
                    raise ResultReportError(400, f"{name} must be pass, fail, or unknown")
                out[name] = value
        if "maintenance" in payload:
            maintenance = payload["maintenance"]
            if not isinstance(maintenance, dict):
                raise ResultReportError(400, "maintenance must be an object")
            unknown = sorted(set(maintenance) - MAINTENANCE_FIELDS)
            if unknown:
                raise ResultReportError(400, f"unknown maintenance field: {unknown[0]}")
            if set(maintenance) != MAINTENANCE_FIELDS:
                missing = sorted(MAINTENANCE_FIELDS - set(maintenance))[0]
                raise ResultReportError(400, f"maintenance field required: {missing}")
            for name, value in maintenance.items():
                if value not in YES_NO:
                    raise ResultReportError(400, f"maintenance.{name} must be yes or no")
            out["maintenance"] = dict(maintenance)
        return work_id, event, event_id, out

    def append(
        self,
        body: Any,
        supplied_token: str,
        work_exists: Callable[[str], bool],
    ) -> dict[str, Any]:
        self._check_auth(supplied_token)
        work_id, event, event_id, payload = self.validate_body(body)
        if not work_exists(work_id):
            raise ResultReportError(404, "unknown work_id")
        key = (work_id, event, event_id)
        now = time.time()
        with self._lock:
            if key in self._seen:
                return {"deduped": True}
            window = self._rate[work_id]
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= MAX_EVENTS_PER_WORK_MINUTE:
                raise ResultReportError(429, "result report rate limit exceeded")
            record = {
                "ts": time.time(),
                "work_id": work_id,
                "event": event,
                "event_id": event_id,
                "payload": payload,
            }
            path = self.events_path()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            except OSError as exc:
                raise ResultReportError(503, "result report storage unavailable") from exc
            self._seen.add(key)
            window.append(now)
        return {"deduped": False}

    def read(self, work_id: str | None, limit: int) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        path = self.events_path()
        try:
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if work_id and row.get("work_id") != work_id:
                        continue
                    events.append(row)
        except FileNotFoundError:
            pass
        except OSError:
            raise ResultReportError(503, "result report storage unavailable")
        events.sort(key=lambda row: float(row.get("ts", 0)), reverse=True)
        total = len(events)
        return {"events": events[:limit], "total": total}


STORE = ResultReportStore()
