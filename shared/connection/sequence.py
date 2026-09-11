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

_CONTINUE_TIMEOUT: float = 45.0


class _SequenceServer(Protocol):
    """Minimal slice of GameServer that GameSequence depends on."""

    def snapshot_players_viewers(self) -> tuple[list[Player], dict[str, Viewer]]: ...
    def start_game(self, bci_token: str, game_type: GameType) -> None: ...


class GameSequence:
    """Run a predefined list of games back-to-back for a single BCI player.

    ``start(token)`` spawns one background thread that walks the sequence for that
    player only: it starts a game via ``server.start_game``, waits until that player's
    game ends (``player.game`` returns to ``None``), then waits for a ``CONTINUE`` BCI
    command (or ``continue_timeout`` seconds) before starting the next game.
    """

    def __init__(
        self,
        server: _SequenceServer,
        sequence: list[GameType] | None = None,
        continue_timeout: float = _CONTINUE_TIMEOUT,
    ) -> None:
        self._server = server
        self._sequence = sequence if sequence is not None else SEQUENCE
        self._continue_timeout = continue_timeout
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
            if not self._wait_until_done(token, game_type):
                break
            if self._stop.is_set():
                break
            log.info("Game sequence [%s]: %s finished, waiting for CONTINUE", token, game_type)
            if not self._wait_for_continue(token):
                break
        log.info("Game sequence [%s]: complete", token)

    def _wait_for_continue(self, token: str) -> bool:
        """Wait for the BCI to send CONTINUE, or auto-continue after the timeout.

        Returns False if the sequence was stopped or the player disconnected.
        """
        players, _ = self._server.snapshot_players_viewers()
        player = next((p for p in players if p.bci_token == token), None)
        if player is None:
            return False
        player.continue_event.clear()
        deadline = time.time() + self._continue_timeout
        while not self._stop.is_set():
            remaining = max(0.0, deadline - time.time())
            if remaining <= 0:
                log.info("Game sequence [%s]: continue timeout, auto-continuing", token)
                return True
            if player.continue_event.wait(timeout=min(1.0, remaining)):
                log.info("Game sequence [%s]: CONTINUE received", token)
                return True
            players, _ = self._server.snapshot_players_viewers()
            p = next((x for x in players if x.bci_token == token), None)
            if p is None or not p.bci.is_connected:
                log.warning("Game sequence [%s]: player disconnected during continue wait", token)
                return False
        return False

    def _wait_until_done(self, token: str, expected_game: GameType) -> bool:
        """Block until the player's game has ended.

        Returns False if the player vanished or if the game was overtaken by a manual
        start (the operator clicked a different game button), so the sequence aborts
        and the S button becomes available again.
        """
        while not self._stop.is_set():
            players, _ = self._server.snapshot_players_viewers()
            player = next((p for p in players if p.bci_token == token), None)
            if player is None or not player.bci.is_connected:
                log.warning("Game sequence [%s]: player disconnected, aborting", token)
                return False
            if player.pending_start is not None and player.pending_start != expected_game:
                log.info("Game sequence [%s]: overtaken by manual start (%s), aborting", token, player.pending_start)
                return False
            if player.game is not None and player.game != expected_game:
                log.info("Game sequence [%s]: overtaken by manual start (%s), aborting", token, player.game)
                return False
            if player.game is None and player.pending_start is None:
                return True
            time.sleep(0.5)
        return False


_sequence: GameSequence | None = None


def get_sequence() -> GameSequence:
    """Return the process-wide GameSequence, bound to the singleton GameServer."""
    global _sequence  # noqa: PLW0603
    if _sequence is None:
        _sequence = GameSequence(get_server())
    return _sequence
