import threading
from typing import TYPE_CHECKING

import pytest

from shared.leaderboard import Leaderboard

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_leaderboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Leaderboard, "_path", tmp_path / "leaderboard.json")


def test_record_dino_creates_entry() -> None:
    Leaderboard.record_dino("alice", 42)
    entries = Leaderboard.snapshot()
    assert len(entries) == 1
    assert entries[0]["name"] == "alice"
    assert entries[0]["dino"] == 42


def test_record_dino_accumulates() -> None:
    Leaderboard.record_dino("alice", 10)
    Leaderboard.record_dino("alice", 20)
    entries = Leaderboard.snapshot()
    assert entries[0]["dino"] == 30


def test_record_pong_win_ignores_com() -> None:
    Leaderboard.record_pong_win("COM")
    assert Leaderboard.snapshot() == []


def test_record_pong_win_creates_entry() -> None:
    Leaderboard.record_pong_win("bob")
    entries = Leaderboard.snapshot()
    assert entries[0]["name"] == "bob"
    assert entries[0]["pong"] == 1


def test_record_wheelchair_creates_entry() -> None:
    Leaderboard.record_wheelchair("charlie", 1)
    entries = Leaderboard.snapshot()
    assert entries[0]["name"] == "charlie"
    assert entries[0]["wheelchair"] == 1


def test_clear_empties_leaderboard() -> None:
    Leaderboard.record_dino("alice", 100)
    Leaderboard.clear()
    assert Leaderboard.snapshot() == []


def test_snapshot_sorted_by_total_descending() -> None:
    Leaderboard.record_dino("alice", 10)
    Leaderboard.record_dino("bob", 50)
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
        Leaderboard.record_dino("concurrent_player", score_per_thread)

    threads = [threading.Thread(target=write) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entries = Leaderboard.snapshot()
    assert entries[0]["dino"] == n_threads * score_per_thread
