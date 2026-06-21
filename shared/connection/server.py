from __future__ import annotations

import contextlib
import os
import queue
import socket
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from queue import Queue
from typing import Self

from games.dino.state import GameState as DinoState
from games.dino.state import GameStateAdapter as DinoAdapter
from games.dino.state import create_initial_state as create_dino_state
from games.dino.update import update_game_state as update_dino_state
from games.pong.state import PongState, PongStateAdapter
from games.pong.state import create_initial_state as create_pong_state
from games.pong.update import PongInput
from games.pong.update import update_game_state as update_pong_state
from shared.audit import audit
from shared.connection.protocol import (
    AckMessage,
    Address,
    CmdMessage,
    DeviceType,
    GameType,
    PingMessage,
    PongMessage,
    RegisterMessage,
    ServerPingMessage,
    ServerPongMessage,
    SessionInfo,
    SessionsMessage,
    SpectateMessage,
    StateMessage,
    parse_client_message,
    to_bytes,
)
from shared.constants import FPS
from shared.leaderboard import Leaderboard
from shared.log import log

_DINO_INPUT: dict[str, str] = {"INPUT_A": "jump", "INPUT_B": "duck"}
_PONG_INPUT: dict[str, str] = {"INPUT_A": "up", "INPUT_B": "down"}


@dataclass
class GameConnection:
    is_connected: bool
    last_seen: float
    address: Address | None


@dataclass
class Viewer:
    """An anonymous renderer client that spectates one player at a time."""

    token: str
    address: Address
    last_seen: float
    is_connected: bool
    watching: str | None  # bci_token of the player being watched, or None


class Player:
    def __init__(self, display_name: str, bci_token: str) -> None:
        self.display_name: str = display_name
        self.bci_token: str = bci_token

        self.bci = GameConnection(is_connected=False, last_seen=time.time(), address=None)

        self.queue: Queue[tuple[str, str]] = Queue()
        self.game: GameType | None = None
        self.in_match: bool = False
        self.pending_start: GameType | None = None  # set by server operator, cleared by worker

    @property
    def is_ready(self) -> bool:
        return self.bci.is_connected


class GameServer(threading.Thread):
    _instance: Self | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        del args, kwargs  # unused
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        buffer_size: int = 65535,
        timeout: timedelta = timedelta(seconds=3),
        heartbeat_interval: timedelta = timedelta(seconds=1),
    ) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        super().__init__(name="GameServer", daemon=True)
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.timeout = timeout
        self.heartbeat_interval = heartbeat_interval

        self.players: dict[str, Player] = {}  # bci_token → Player
        self.viewers: dict[str, Viewer] = {}  # viewer_token → Viewer
        self.workers: dict[str, GameServer._Worker] = {}  # bci_token → _Worker
        self._pong_lobby: list[Player] = []

        self._state_lock: threading.RLock = threading.RLock()

        self._is_running = threading.Event()
        self._is_running.set()

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.settimeout(1.0)
        self.server_sock.bind((host, port))

        log.info("Server listening on %s:%s", host, port)

    @classmethod
    def reset_for_testing(cls) -> None:
        """Clear the singleton so tests can create a fresh instance."""
        with cls._lock:
            if cls._instance is not None and cls._instance.is_alive():
                msg = "reset_for_testing() called while server thread is still running - call stop() and join() first"
                raise RuntimeError(msg)
            cls._instance = None

    def run(self) -> None:
        while self._is_running.is_set():
            try:
                data, addr = self.server_sock.recvfrom(self.buffer_size)
            except TimeoutError:
                continue
            except OSError:
                break

            try:
                msg = parse_client_message(data)
            except ValueError:
                log.debug("Dropped malformed packet from %s", addr)
                continue

            with self._state_lock:
                try:
                    match msg:
                        case RegisterMessage(display_name=display_name, device=DeviceType.BCI):
                            player = self._register_player(display_name)
                            player.bci.is_connected = True
                            player.bci.address = addr
                            player.bci.last_seen = time.time()
                            self.server_sock.sendto(to_bytes(AckMessage(session_token=player.bci_token)), addr)
                            log.info("BCI registered display_name=%s token=%s", display_name, player.bci_token)
                            audit.record("register", device="bci", display_name=display_name, token=player.bci_token)
                            self.push_sessions()

                        case RegisterMessage(display_name=_, device=DeviceType.SPECTATOR):
                            token = os.urandom(8).hex()
                            viewer = Viewer(
                                token=token,
                                address=addr,
                                last_seen=time.time(),
                                is_connected=True,
                                watching=None,
                            )
                            self.viewers[token] = viewer
                            self.server_sock.sendto(to_bytes(AckMessage(session_token=token)), addr)
                            log.info("Viewer registered token=%s", token)
                            audit.record("register", device="spectator", token=token)
                            self.push_sessions(addrs=[addr])

                        case SpectateMessage(viewer_token=token, target_uid=bci_token):
                            viewer = self.viewers.get(token)
                            if viewer:
                                viewer.address = addr
                                viewer.last_seen = time.time()
                                if bci_token == "":
                                    viewer.watching = None
                                    self.push_sessions()
                                    log.info("Viewer %s stopped watching", token)
                                    audit.record("stop_watching", viewer_token=token)
                                elif bci_token in self.players:
                                    viewer.watching = bci_token
                                    log.info("Viewer %s now watching token=%s", token, bci_token)
                                    audit.record("spectate", viewer_token=token, target_uid=bci_token)

                        case PingMessage(session_token=token, device=DeviceType.BCI):
                            if player := self.players.get(token):
                                player.bci.last_seen = time.time()
                                player.bci.address = addr
                                if not player.bci.is_connected:
                                    player.bci.is_connected = True
                                    self.push_sessions()
                                    log.info("[%s] BCI reconnected via PING", token)
                                self.server_sock.sendto(to_bytes(ServerPongMessage()), addr)

                        case PingMessage(session_token=token, device=DeviceType.SPECTATOR):
                            if viewer := self.viewers.get(token):
                                viewer.last_seen = time.time()
                                viewer.address = addr
                                self.server_sock.sendto(to_bytes(ServerPongMessage()), addr)

                        case PongMessage(session_token=token, device=DeviceType.BCI):
                            if player := self.players.get(token):
                                player.bci.last_seen = time.time()
                                player.bci.address = addr
                                if not player.bci.is_connected:
                                    player.bci.is_connected = True
                                    self.push_sessions()
                                    log.info("[%s] BCI reconnected via PONG", token)

                        case PongMessage(session_token=token, device=DeviceType.SPECTATOR):
                            if viewer := self.viewers.get(token):
                                viewer.last_seen = time.time()

                        case CmdMessage(session_token=token, device=DeviceType.BCI, content=content):
                            if player := self.players.get(token):
                                player.bci.last_seen = time.time()
                                player.bci.address = addr
                                if not player.bci.is_connected:
                                    player.bci.is_connected = True
                                    self.push_sessions()
                                    log.info("[%s] BCI reconnected via CMD", token)
                                game_label = player.game.value if player.game else None
                                audit.record("input", token=token, cmd=content, game=game_label)
                                player.queue.put(("bci", content))

                except Exception:
                    log.exception("Error handling message from %s", addr)

    def start_game(self, bci_token: str, game_type: GameType) -> None:
        """Called by the server UI to start or switch a player's game."""
        with self._state_lock:
            player = self.players.get(bci_token)
            if not player:
                return
            if game_type == GameType.PONG:
                self._handle_pong_lobby(player)
            else:
                player.pending_start = game_type  # DINO and PONG_AI start immediately
                log.info("Server queued %s for token=%s", game_type, bci_token)
            self.push_sessions()

    _VIEWER_CLEANUP_TIMEOUT: timedelta = timedelta(seconds=30)

    def push_sessions(self, addrs: list[Address] | None = None) -> None:
        """Broadcast the current session list to viewers. If addrs is given, only send to those."""
        with self._state_lock:
            now = time.time()
            stale = [
                t for t, v in self.viewers.items() if now - v.last_seen > self._VIEWER_CLEANUP_TIMEOUT.total_seconds()
            ]
            for token in stale:
                log.info("Viewer %s removed after inactivity", token)
                del self.viewers[token]
            for v in self.viewers.values():
                v.is_connected = now - v.last_seen <= self.timeout.total_seconds()

            sessions = [
                SessionInfo(
                    uid=p.bci_token,
                    display_name=p.display_name,
                    game=p.game.value if p.game else "",
                    bci_connected=p.bci.is_connected,
                )
                for p in self.players.values()
            ]
            msg = to_bytes(SessionsMessage(sessions=sessions))
            targets = addrs if addrs is not None else [v.address for v in self.viewers.values() if v.is_connected]
        for addr in targets:
            with contextlib.suppress(OSError):
                self.server_sock.sendto(msg, addr)

    def viewers_for(self, bci_token: str) -> list[Viewer]:
        """Return all connected viewers currently watching the given player."""
        with self._state_lock:
            now = time.time()
            result = []
            for v in self.viewers.values():
                if v.watching == bci_token:
                    if v.is_connected and now - v.last_seen <= self.timeout.total_seconds():
                        result.append(v)
                    else:
                        v.is_connected = False
            return result

    def _register_player(self, display_name: str) -> Player:
        with self._state_lock:
            existing = next((p for p in self.players.values() if p.display_name == display_name), None)
            if existing is not None:
                log.info("Re-registering display_name=%s with existing token=%s", display_name, existing.bci_token)
                return existing
            bci_token = os.urandom(8).hex()
            player = Player(display_name=display_name, bci_token=bci_token)
            self.players[bci_token] = player
            worker = GameServer._Worker(player, self._is_running, self, self.timeout, self.heartbeat_interval)
            self.workers[bci_token] = worker
            worker.start()
            log.info("Created player display_name=%s bci_token=%s", display_name, bci_token)
            return player

    def _handle_pong_lobby(self, player: Player) -> None:
        with self._state_lock:
            if player in self._pong_lobby or player.in_match:
                return
            self._pong_lobby = [p for p in self._pong_lobby if p.bci.is_connected]
            if self._pong_lobby:
                opponent = self._pong_lobby.pop(0)
                player.in_match = True
                opponent.in_match = True
                match_worker = GameServer._PongMatchWorker(
                    player, opponent, self._is_running, self, self.timeout, self.heartbeat_interval
                )
                match_worker.start()
                audit.record("pong_match_start", player1=player.bci_token, player2=opponent.bci_token)
                log.info("Pong match started: %s vs %s", player.bci_token, opponent.bci_token)
            else:
                self._pong_lobby.append(player)
                log.info("Player %s waiting in pong lobby", player.bci_token)

    def snapshot_players_viewers(self) -> tuple[list[Player], dict[str, Viewer]]:
        """Return a consistent point-in-time copy of players and viewers under the state lock."""
        with self._state_lock:
            return list(self.players.values()), dict(self.viewers)

    def mark_bci_disconnected(self, player: Player) -> None:
        """Set player.bci.is_connected to False under the state lock."""
        with self._state_lock:
            player.bci.is_connected = False

    def remove_player(self, bci_token: str) -> None:
        """Remove a player session and broadcast the updated session list."""
        with self._state_lock:
            self.players.pop(bci_token, None)
            self.workers.pop(bci_token, None)
            self.push_sessions()
            audit.record("player_removed", token=bci_token)
            log.info("[%s] Player removed after inactivity", bci_token)

    def stop(self) -> None:
        self._is_running.clear()
        self.server_sock.close()
        for worker in list(self.workers.values()):
            worker.join(timeout=2.0)

    class _Worker(threading.Thread):
        _GAME_OVER_LINGER: timedelta = timedelta(seconds=5)
        _CLEANUP_TIMEOUT: timedelta = timedelta(seconds=30)
        _COUNTDOWN: timedelta = timedelta(seconds=10)

        def __init__(
            self,
            player: Player,
            is_running: threading.Event,
            server: GameServer,
            timeout: timedelta,
            heartbeat_interval: timedelta,
        ) -> None:
            super().__init__(name=f"Worker-{player.bci_token}", daemon=True)
            self.player = player
            self.is_running = is_running
            self.server = server
            self.timeout = timeout
            self.heartbeat_interval = heartbeat_interval
            self.outbound_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            self._active_game: GameType = GameType.DINO
            self._dino_state: DinoState | None = None
            self._pong_state: PongState | None = None
            self._has_started: bool = False
            self._last_heartbeat: float = time.time()
            self._game_over_at: float | None = None
            self._bci_disconnected_at: float | None = None

        def run(self) -> None:
            tick_duration = 1.0 / FPS
            try:
                while self.is_running.is_set():
                    if self.player.in_match:
                        time.sleep(tick_duration)
                        continue
                    loop_start = time.time()
                    bci_eviction_due = (
                        self._bci_disconnected_at is not None
                        and loop_start - self._bci_disconnected_at > self._CLEANUP_TIMEOUT.total_seconds()
                    )
                    if bci_eviction_due:
                        self._cleanup()
                        return
                    game_over_linger_expired = (
                        self._game_over_at is not None
                        and loop_start - self._game_over_at > self._GAME_OVER_LINGER.total_seconds()
                    )
                    if game_over_linger_expired:
                        self._has_started = False
                        self._dino_state = None
                        self._pong_state = None
                        self._game_over_at = None
                    self._tick_connections(loop_start)
                    game_input = self._process_commands()
                    self._tick_game(game_input)
                    self._broadcast_state()
                    elapsed = time.time() - loop_start
                    time.sleep(max(0.0, tick_duration - elapsed))
            finally:
                self.outbound_sock.close()

        def _tick_connections(self, now: float) -> None:
            bci = self.player.bci
            if bci.is_connected:
                if now - bci.last_seen > self.timeout.total_seconds():
                    self.server.mark_bci_disconnected(self.player)
                    if self._bci_disconnected_at is None:
                        self._bci_disconnected_at = now
                    log.info("[%s] BCI timed out", self.player.bci_token)
                    audit.record("bci_timeout", token=self.player.bci_token)
                    self.server.push_sessions()
                elif self._bci_disconnected_at is not None:
                    self._bci_disconnected_at = None  # reconnected
            elif self._bci_disconnected_at is None:
                self._bci_disconnected_at = now

            if now - self._last_heartbeat >= self.heartbeat_interval.total_seconds():
                ping = to_bytes(ServerPingMessage())
                if bci.is_connected and bci.address:
                    self.outbound_sock.sendto(ping, bci.address)
                for viewer in self.server.viewers_for(self.player.bci_token):
                    self.outbound_sock.sendto(ping, viewer.address)
                self._last_heartbeat = now

        def _process_commands(self) -> str | None:
            if self.player.pending_start is not None:
                game_type = self.player.pending_start
                self.player.pending_start = None
                self._start_game(game_type)

            if self._dino_state:
                self._dino_state.is_paused = self._dino_state.countdown > 0 or not self.player.is_ready
            if self._pong_state:
                self._pong_state.is_paused = self._pong_state.countdown > 0 or not self.player.is_ready

            game_input: str | None = None
            try:
                source, cmd = self.player.queue.get_nowait()
                if source == "bci" and self._has_started:
                    if self._active_game in (GameType.DINO, GameType.DINO_JUMP):
                        game_input = _DINO_INPUT.get(cmd)
                    elif self._active_game in (GameType.PONG, GameType.PONG_AI):
                        game_input = _PONG_INPUT.get(cmd)
            except queue.Empty:
                pass

            return game_input

        def _start_game(self, game_type: GameType) -> None:
            self._game_over_at = None
            self._active_game = game_type
            self._has_started = True
            self.player.game = game_type
            match game_type:
                case GameType.DINO | GameType.DINO_JUMP:
                    jump_only = game_type == GameType.DINO_JUMP
                    self._dino_state = create_dino_state(self.player.display_name, jump_only=jump_only)
                    self._dino_state.countdown = self._COUNTDOWN.total_seconds()
                    self._dino_state.is_paused = True
                case GameType.PONG | GameType.PONG_AI:
                    self._pong_state = create_pong_state(self.player.display_name)
                    self._pong_state.countdown = self._COUNTDOWN.total_seconds()
                    self._pong_state.is_paused = True
            self.server.push_sessions()
            audit.record("game_start", token=self.player.bci_token, game=game_type.value)
            log.info("[%s] Game started: %s", self.player.bci_token, game_type)

        def _cleanup(self) -> None:
            self.server.remove_player(self.player.bci_token)

        def _tick_dino(self, game_input: str | None) -> None:
            if self._dino_state is None:
                return
            if self._dino_state.countdown > 0:
                self._dino_state.countdown = max(0.0, self._dino_state.countdown - 1.0 / FPS)
                return
            if self._dino_state.is_paused:
                return

            dino_input = game_input if game_input in ("jump", "duck") else None
            self._dino_state = update_dino_state(self._dino_state, dino_input)  # type: ignore[arg-type]
            if not (self._dino_state.game_over or self._dino_state.time_left <= 0):
                return

            self._game_over_at = time.time()
            self.player.game = None
            self.server.push_sessions()
            Leaderboard.record_dino(self.player.display_name, self._dino_state.score)
            audit.record("game_over", token=self.player.bci_token, game="dino", score=self._dino_state.score)
            log.info("[%s] Dino game over (score=%d)", self.player.bci_token, self._dino_state.score)

        def _tick_game(self, game_input: str | None) -> None:
            if not self._has_started or self._game_over_at is not None:
                return
            match self._active_game:
                case GameType.DINO | GameType.DINO_JUMP:
                    self._tick_dino(game_input)
                case GameType.PONG | GameType.PONG_AI:
                    if self._pong_state:
                        if self._pong_state.countdown > 0:
                            self._pong_state.countdown = max(0.0, self._pong_state.countdown - 1.0 / FPS)
                            if self._pong_state.countdown <= 0:
                                self._pong_state.game_started = True
                            return
                        if not self._pong_state.is_paused:
                            pong_input: PongInput = game_input if game_input in ("up", "down") else None  # type: ignore[assignment]
                            pvp = self._active_game == GameType.PONG
                            self._pong_state = update_pong_state(self._pong_state, pong_input, pvp=pvp)
                            if self._pong_state.game_over:
                                self._game_over_at = time.time()
                                self.player.game = None
                                self.server.push_sessions()
                                if self._pong_state.winner == 1:
                                    Leaderboard.record_pong_win(self._pong_state.player1_name)
                                audit.record(
                                    "game_over",
                                    token=self.player.bci_token,
                                    game=self._active_game.value,
                                    winner=self._pong_state.winner,
                                )
                                log.info(
                                    "[%s] Pong game over (winner=%d)", self.player.bci_token, self._pong_state.winner
                                )

        def _broadcast_state(self) -> None:
            viewers = self.server.viewers_for(self.player.bci_token)
            if not viewers:
                return
            state_bytes: bytes | None = None
            game_type: GameType | None = None
            match self._active_game:
                case GameType.DINO | GameType.DINO_JUMP if self._dino_state:
                    state_bytes = DinoAdapter.dump_bytes(self._dino_state)
                    game_type = self._active_game
                case GameType.PONG | GameType.PONG_AI if self._pong_state:
                    state_bytes = PongStateAdapter.dump_bytes(self._pong_state)
                    game_type = self._active_game
            if state_bytes and game_type:
                msg = to_bytes(StateMessage(content=state_bytes, game=game_type))
                for viewer in viewers:
                    self.outbound_sock.sendto(msg, viewer.address)

    class _PongMatchWorker(threading.Thread):
        """Runs a shared PongState for two matched players, broadcasts to all their viewers."""

        _COUNTDOWN: timedelta = timedelta(seconds=10)
        _GAME_OVER_LINGER: timedelta = timedelta(seconds=3)

        def __init__(
            self,
            player1: Player,
            player2: Player,
            is_running: threading.Event,
            server: GameServer,
            timeout: timedelta,
            heartbeat_interval: timedelta,
        ) -> None:
            super().__init__(name=f"PongMatch-{player1.bci_token}-vs-{player2.bci_token}", daemon=True)
            self.player1 = player1
            self.player2 = player2
            self.is_running = is_running
            self.server = server
            self.timeout = timeout
            self.heartbeat_interval = heartbeat_interval
            self.outbound_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._state: PongState = create_pong_state(player1.display_name, player2.display_name)
            self._state.countdown = self._COUNTDOWN.total_seconds()
            self._state.is_paused = True
            self._last_heartbeat: float = time.time()
            self._game_over_at: float | None = None

            player1.game = GameType.PONG
            player2.game = GameType.PONG

        def run(self) -> None:
            tick_duration = 1.0 / FPS
            try:
                while self.is_running.is_set():
                    loop_start = time.time()
                    self._tick_connections(loop_start)
                    p1_input, p2_input = self._process_commands()
                    self._tick_game(p1_input, p2_input)
                    self._broadcast_state()
                    if self._state.game_over:
                        if self._game_over_at is None:
                            self._game_over_at = time.time()
                        elif time.time() - self._game_over_at > self._GAME_OVER_LINGER.total_seconds():
                            break
                    elapsed = time.time() - loop_start
                    time.sleep(max(0.0, tick_duration - elapsed))
            finally:
                self.outbound_sock.close()
                if self._state.game_over and self._state.winner in (1, 2):
                    winner_name = self._state.player1_name if self._state.winner == 1 else self._state.player2_name
                    Leaderboard.record_pong_win(winner_name)
                self.player1.in_match = False
                self.player2.in_match = False
                self.player1.game = None
                self.player2.game = None
                audit.record(
                    "pong_match_end",
                    player1=self.player1.bci_token,
                    player2=self.player2.bci_token,
                    winner=self._state.winner,
                )
                log.info("Pong match ended: %s vs %s", self.player1.bci_token, self.player2.bci_token)
                self.server.push_sessions()

        def _is_fully_connected(self) -> bool:
            return self.player1.bci.is_connected and self.player2.bci.is_connected

        def _tick_connections(self, now: float) -> None:
            for player in (self.player1, self.player2):
                if player.bci.is_connected and now - player.bci.last_seen > self.timeout.total_seconds():
                    self.server.mark_bci_disconnected(player)
                    self.server.push_sessions()

            if now - self._last_heartbeat >= self.heartbeat_interval.total_seconds():
                ping = to_bytes(ServerPingMessage())
                for player in (self.player1, self.player2):
                    if player.bci.is_connected and player.bci.address:
                        self.outbound_sock.sendto(ping, player.bci.address)
                    for viewer in self.server.viewers_for(player.bci_token):
                        self.outbound_sock.sendto(ping, viewer.address)
                self._last_heartbeat = now

        def _process_commands(self) -> tuple[PongInput, PongInput]:
            self._state.is_paused = self._state.countdown > 0 or not self._is_fully_connected()
            p1_input: PongInput = None
            p2_input: PongInput = None
            for player, is_p1 in ((self.player1, True), (self.player2, False)):
                try:
                    source, cmd = player.queue.get_nowait()
                    translated = _PONG_INPUT.get(cmd) if source == "bci" else None
                    if translated:
                        if is_p1:
                            p1_input = translated  # type: ignore[assignment]
                        else:
                            p2_input = translated  # type: ignore[assignment]
                except queue.Empty:
                    pass
            return p1_input, p2_input

        def _tick_game(self, p1_input: PongInput, p2_input: PongInput) -> None:
            if self._state.countdown > 0:
                self._state.countdown = max(0.0, self._state.countdown - 1.0 / FPS)
                if self._state.countdown <= 0:
                    self._state.game_started = True
                return
            self._state = update_pong_state(self._state, p1_input, p2_input, pvp=True)

        def _broadcast_state(self) -> None:
            msg = to_bytes(StateMessage(content=PongStateAdapter.dump_bytes(self._state), game=GameType.PONG))
            for player in (self.player1, self.player2):
                for viewer in self.server.viewers_for(player.bci_token):
                    self.outbound_sock.sendto(msg, viewer.address)


def get_server() -> GameServer:
    """Return the singleton GameServer, starting it on first call."""
    server = GameServer()
    if not server.is_alive():
        server.start()
    return server
