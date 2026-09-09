from __future__ import annotations

import threading
import time
from typing import Protocol

from shared.connection.protocol import GameType
from shared.connection.server import Player, Viewer, get_server
from shared.log import log

# Predefined competition sequence (see task spec):
#   Brainski 1 - Jump only   (J)   -> DINO_JUMP
#   Brainski 1 - Jump & Duck  (JD)  -> DINO
#   Brainski 2 - Static            -> SKI
#   Brainski 2 - Dynamic           -> SKI_DYN
SEQUENCE: list[GameType] = [
    GameType.DINO_JUMP,
    GameType.DINO,
    GameType.SKI,
    GameType.SKI_DYN,
]

_DEFAULT_DELAY: float = 10.0


class _SequenceServer(Protocol):
    """Minimal slice of GameServer that GameSequence depends on."""

    def snapshot_players_viewers(self) -> tuple[list[Player], dict[str, Viewer]]: ...
    def start_game(self, bci_token: str, game_type: GameType) -> None: ...


class GameSequence:
    """Run a predefined list of games back-to-back for a single BCI player.

    ``start(token)`` spawns one background thread that walks the sequence for that
    player only: it starts a game via ``server.start_game``, waits until that player's
    game ends (``player.game`` returns to ``None``), then waits ``delay`` seconds
    before starting the next game. Each call is independent per player.
    """

    def __init__(
        self,
        server: _SequenceServer,
        sequence: list[GameType] | None = None,
        delay: float = _DEFAULT_DELAY,
    ) -> None:
        self._server = server
        self._sequence = sequence if sequence is not None else SEQUENCE
        self._delay = delay
        self._threads: dict[str, threading.Thread] = {}
        self._stop = threading.Event()

    def is_running(self, token: str) -> bool:
        """Whether a sequence is currently running for the given player token."""
        thread = self._threads.get(token)
        return thread is not None and thread.is_alive()

    @property
    def any_running(self) -> bool:
        """Whether any sequence thread is alive."""
        return any(t.is_alive() for t in self._threads.values())

    def start(self, token: str) -> None:
        """Launch an independent sequence thread for a single player. No-op if already running for that player."""
        if self.is_running(token):
            return
        self._stop.clear()
        thread = threading.Thread(target=self._run_player, args=(token,), name=f"GameSequence-{token}", daemon=True)
        self._threads[token] = thread
        thread.start()
        log.info("Game sequence started for token=%s", token)

    def stop(self) -> None:
        """Signal every running sequence thread to stop after the current game."""
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        """Wait for all sequence threads to terminate (or ``timeout`` to elapse)."""
        for thread in self._threads.values():
            thread.join(timeout=timeout)

    def _run_player(self, token: str) -> None:
        for game_type in self._sequence:
            if self._stop.is_set():
                break
            log.info("Game sequence [%s]: starting %s", token, game_type)
            self._server.start_game(token, game_type)
            if not self._wait_until_done(token):
                break
            if self._stop.is_set():
                break
            log.info("Game sequence [%s]: %s finished, waiting %.0fs before next game", token, game_type, self._delay)
            self._sleep(self._delay)
        log.info("Game sequence [%s]: complete", token)

    def _wait_until_done(self, token: str) -> bool:
        """Block until the player's game has ended. Returns False if the player vanished."""
        while not self._stop.is_set():
            players, _ = self._server.snapshot_players_viewers()
            player = next((p for p in players if p.bci_token == token), None)
            if player is None or not player.bci.is_connected:
                log.warning("Game sequence [%s]: player disconnected, aborting", token)
                return False
            if player.game is None and player.pending_start is None:
                return True
            time.sleep(0.5)
        return False

    def _sleep(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while not self._stop.is_set() and time.time() < deadline:
            time.sleep(0.2)


_sequence: GameSequence | None = None


def get_sequence() -> GameSequence:
    """Return the process-wide GameSequence, bound to the singleton GameServer."""
    global _sequence  # noqa: PLW0603
    if _sequence is None:
        _sequence = GameSequence(get_server())
    return _sequence
