from __future__ import annotations

import json
from typing import TYPE_CHECKING

from shared.audit import AuditLog

if TYPE_CHECKING:
    from pathlib import Path


def test_disabled_audit_writes_nothing(tmp_path: Path) -> None:
    audit = AuditLog(enabled=False, directory=tmp_path)
    audit.record("input", token="abc", cmd="INPUT_A")
    audit.close()
    assert list(tmp_path.glob("*.jsonl")) == []


def test_enabled_audit_writes_one_json_line_per_event(tmp_path: Path) -> None:
    audit = AuditLog(enabled=True, directory=tmp_path)
    audit.record("register", device="bci", token="abc")
    audit.record("input", token="abc", cmd="INPUT_A", game="dino")
    audit.close()

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["event"] == "register"
    assert first["device"] == "bci"
    assert first["token"] == "abc"
    assert "ts" in first

    second = json.loads(lines[1])
    assert second["event"] == "input"
    assert second["cmd"] == "INPUT_A"
    assert second["game"] == "dino"
