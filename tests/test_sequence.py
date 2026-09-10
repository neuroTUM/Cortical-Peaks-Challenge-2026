from __future__ import annotations

import threading
import time

from shared.connection.protocol import GameType
from shared.connection.sequence import SEQUENCE, GameSequence
from shared.connection.server import Player, Viewer


class _FakeServer:
    """Minimal stand-in satisfying GameSequence's server protocol.

    Each call to ``start_game`` flips the player's game/pending_start on, and a
    background ticker clears them after ``finish_after`` seconds so the runner can
    observe the game finishing without depending on real game timing. Per-token
    delays may be supplied via ``finish_delays``.
    """

    def __init__(
        self,
        players: list[Player],
        *,
        finish_after: float = 0.1,
        finish_delays: dict[str, float] | None = None,
    ) -> None:
        self._players = players
        self.calls: list[tuple[str, GameType]] = []
        self._finish_after = finish_after
        self._finish_delays = finish_delays or {}
        self._lock = threading.Lock()

    def snapshot_players_viewers(self) -> tuple[list[Player], dict[str, Viewer]]:
        with self._lock:
            return list(self._players), {}

    def start_game(self, bci_token: str, game_type: GameType) -> None:
        with self._lock:
            self.calls.append((bci_token, game_type))
            for p in self._players:
                if p.bci_token == bci_token:
                    p.pending_start = game_type
                    p.game = game_type
                    threading.Thread(target=self._finish, args=(p,), daemon=True).start()

    def _finish(self, player: Player) -> None:
        delay = self._finish_delays.get(player.bci_token, self._finish_after)
        time.sleep(delay)
        with self._lock:
            player.pending_start = None
            player.game = None


def _player(token: str, *, connected: bool = True, in_match: bool = False) -> Player:
    p = Player(display_name=token, bci_token=token)
    p.bci.is_connected = connected
    p.in_match = in_match
    return p


def test_sequence_matches_spec() -> None:
    assert SEQUENCE == [GameType.DINO_JUMP, GameType.DINO, GameType.SKI, GameType.SKI_DYN]


def test_sequence_starts_games_in_order() -> None:
    server = _FakeServer([_player("t1")], finish_after=0.05)
    seq = GameSequence(server, delay=0.0)

    seq.start("t1")
    assert seq.is_running("t1")
    seq.join(timeout=5)
    assert not seq.is_running("t1")

    assert [gt for _, gt in server.calls] == SEQUENCE


def test_sequence_starts_independently_per_player() -> None:
    server = _FakeServer([_player("a"), _player("b")], finish_after=0.05)
    seq = GameSequence(server, delay=0.0)

    seq.start("a")
    seq.start("b")
    seq.join(timeout=5)

    # Each player should run the full sequence independently.
    calls_by_token: dict[str, list[GameType]] = {}
    for tok, gt in server.calls:
        calls_by_token.setdefault(tok, []).append(gt)
    assert set(calls_by_token) == {"a", "b"}
    assert calls_by_token["a"] == SEQUENCE
    assert calls_by_token["b"] == SEQUENCE


def test_sequence_players_progress_independently() -> None:
    """A fast player should advance through several games while a slow player is still on game 1."""
    server = _FakeServer(
        [_player("fast"), _player("slow")],
        finish_delays={"fast": 0.01, "slow": 5.0},
    )
    seq = GameSequence(server, delay=0.0)

    seq.start("fast")
    seq.start("slow")
    time.sleep(2.0)
    fast_calls = [gt for tok, gt in server.calls if tok == "fast"]
    slow_calls = [gt for tok, gt in server.calls if tok == "slow"]
    assert len(fast_calls) >= 3
    assert len(slow_calls) == 1
    seq.stop()
    seq.join(timeout=5)


def test_sequence_aborts_for_disconnected_player() -> None:
    """A disconnected player's sequence starts the first game then aborts when the disconnect is detected.

    The eligibility gate (connected + not in game) is enforced by the UI, mirroring
    the singular-game buttons. If a player is disconnected, ``_wait_until_done`` catches
    it and the sequence stops after one start_game call.
    """
    server = _FakeServer([_player("t1", connected=False)])
    seq = GameSequence(server, delay=0.0)

    seq.start("t1")
    seq.join(timeout=5)

    # First game is started, then the sequence aborts on detecting the disconnect.
    assert len(server.calls) == 1
    assert server.calls[0] == ("t1", GameType.DINO_JUMP)
    assert not seq.is_running("t1")


def test_start_is_noop_when_already_running() -> None:
    # A server whose games never finish keeps the sequence stuck in _wait_until_done.
    server = _FakeServer([_player("t1")], finish_after=10.0)
    seq = GameSequence(server, delay=0.0)

    seq.start("t1")
    time.sleep(0.2)
    first_count = len(server.calls)
    seq.start("t1")  # ignored: already running for this token
    time.sleep(0.2)

    assert len(server.calls) == first_count
    seq.stop()
    seq.join(timeout=5)


def test_start_for_different_tokens_run_concurrently() -> None:
    server = _FakeServer([_player("a"), _player("b")], finish_after=10.0)
    seq = GameSequence(server, delay=0.0)

    seq.start("a")
    seq.start("b")  # different token, should NOT be a no-op
    time.sleep(0.2)

    tokens = {tok for tok, _ in server.calls}
    assert tokens == {"a", "b"}
    seq.stop()
    seq.join(timeout=5)


def test_sequence_aborts_when_manual_start_overtakes() -> None:
    """If the operator clicks a different game button while the sequence is running,
    the sequence detects the game change, aborts, and the S button becomes available again.
    """
    player = _player("t1")
    server = _FakeServer([player], finish_after=10.0)  # long so the game is "running"
    seq = GameSequence(server, delay=0.0)

    seq.start("t1")
    time.sleep(0.2)  # let the first game (DINO_JUMP) start
    assert seq.is_running("t1")

    # Operator clicks BSDJ — overtakes the sequence's DINO_JUMP
    server.start_game("t1", GameType.DINO)
    time.sleep(0.5)  # let _wait_until_done detect the game mismatch

    # Sequence should have aborted
    assert not seq.is_running("t1"), "Sequence should abort after manual overtakes"

    # S button should be available again
    assert not seq.is_running("t1")
