from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TextIO

from shared.constants import AUDIT, DATA_DIR
from shared.log import log

if TYPE_CHECKING:
    from pathlib import Path


class AuditLog:
    """Facade over a JSON Lines audit sink.

    When enabled (the server's --audit flag), record() appends one JSON object per event to a
    timestamped file under data/audit/. When disabled, every call is a no-op, so callers never
    have to guard their own auditing. Thread-safe: the server fans work out across many worker
    threads that all funnel events through the singleton instance.
    """

    def __init__(self, *, enabled: bool, directory: Path) -> None:
        self._enabled = enabled
        self._directory = directory
        self._lock = threading.Lock()
        self._file: TextIO | None = None  # opened lazily on the first recorded event

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _ensure_open(self) -> TextIO:
        if self._file is None:
            self._directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
            path = self._directory / f"audit-{stamp}.jsonl"
            self._file = path.open("a", encoding="utf-8")
            log.info("Audit log writing to %s", path)
        return self._file

    def record(self, event: str, **fields: object) -> None:
        """Append one audit event. No-op unless auditing is enabled."""
        if not self._enabled:
            return
        entry = {"ts": datetime.now(tz=UTC).isoformat(), "epoch": time.time(), "event": event, **fields}
        line = json.dumps(entry, default=str)
        with self._lock:
            handle = self._ensure_open()
            handle.write(line + "\n")
            handle.flush()

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None


audit = AuditLog(enabled=AUDIT, directory=DATA_DIR / "audit")
