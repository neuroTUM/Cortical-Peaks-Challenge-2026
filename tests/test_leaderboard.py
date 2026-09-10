import json
import threading
from typing import TYPE_CHECKING

import pytest

from shared.leaderboard import Leaderboard

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_leaderboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Leaderboard, "_path", tmp_path / "leaderboard.json")


def test_record_dino_jump_creates_entry() -> None:
    Leaderboard.record_dino_jump("alice", 42)
    entries = Leaderboard.snapshot()
    assert len(entries) == 1
    assert entries[0]["name"] == "alice"
    assert entries[0]["bsj"] == 42
    assert entries[0]["total"] == 42


def test_record_dino_jump_accumulates() -> None:
    Leaderboard.record_dino_jump("alice", 10)
    Leaderboard.record_dino_jump("alice", 20)
    entries = Leaderboard.snapshot()
    assert entries[0]["bsj"] == 30


def test_record_dino_jd_creates_entry() -> None:
    Leaderboard.record_dino_jd("alice", 15)
    entries = Leaderboard.snapshot()
    assert entries[0]["bsdj"] == 15


def test_record_pong_win_ignores_com() -> None:
    Leaderboard.record_pong_win("COM")
    assert Leaderboard.snapshot() == []


def test_record_pong_win_creates_entry() -> None:
    Leaderboard.record_pong_win("bob")
    entries = Leaderboard.snapshot()
    assert entries[0]["name"] == "bob"
    assert entries[0]["pong"] == 1


def test_record_ski_static_creates_entry() -> None:
    Leaderboard.record_ski_static("charlie", 1)
    entries = Leaderboard.snapshot()
    assert entries[0]["s1"] == 1


def test_record_ski_dyn_creates_entry() -> None:
    Leaderboard.record_ski_dyn("dave", 2.5)
    entries = Leaderboard.snapshot()
    assert entries[0]["s2"] == 2


def test_clear_empties_leaderboard() -> None:
    Leaderboard.record_dino_jump("alice", 100)
    Leaderboard.clear()
    assert Leaderboard.snapshot() == []


def test_snapshot_sorted_by_total_descending() -> None:
    Leaderboard.record_dino_jump("alice", 10)
    Leaderboard.record_dino_jd("bob", 50)
    Leaderboard.record_pong_win("alice")
    entries = Leaderboard.snapshot()
    assert entries[0]["name"] == "bob"
    assert entries[1]["name"] == "alice"


def test_corrupt_json_returns_empty() -> None:
    Leaderboard._path.write_text("not valid json")  # noqa: SLF001
    assert Leaderboard.snapshot() == []


def test_missing_file_returns_empty() -> None:
    assert Leaderboard.snapshot() == []


def test_concurrent_writes_thread_safe() -> None:
    n_threads = 10
    score_per_thread = 5

    def write() -> None:
        Leaderboard.record_dino_jump("concurrent_player", score_per_thread)

    threads = [threading.Thread(target=write) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entries = Leaderboard.snapshot()
    assert entries[0]["bsj"] == n_threads * score_per_thread


def test_total_sums_all_columns() -> None:
    Leaderboard.record_dino_jump("alice", 10)
    Leaderboard.record_dino_jd("alice", 20)
    Leaderboard.record_pong_win("alice")
    Leaderboard.record_ski_static("alice", 30)
    Leaderboard.record_ski_dyn("alice", 40)
    entries = Leaderboard.snapshot()
    assert entries[0]["total"] == 101


def test_old_schema_migrates_to_new_columns() -> None:
    """Entries saved with the old dino/ski schema must load without crashing."""
    Leaderboard._path.write_text(  # noqa: SLF001
        json.dumps([{"name": "alice", "dino": 50, "pong": 2, "ski": 30, "total": 82}])
    )
    entries = Leaderboard.snapshot()
    assert len(entries) == 1
    e = entries[0]
    assert e["bsj"] == 50  # migrated from "dino"
    assert e["bsdj"] == 0
    assert e["pong"] == 2
    assert e["s1"] == 30  # migrated from "ski"
    assert e["s2"] == 0
    assert e["total"] == 82
    assert "dino" not in e
    assert "ski" not in e
