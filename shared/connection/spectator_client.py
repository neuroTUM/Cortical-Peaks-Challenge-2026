from __future__ import annotations

import socket
import threading
import time
from datetime import timedelta

from games.dino.state import GameState, GameStateAdapter
from games.pong.state import PongState, PongStateAdapter
from games.ski.state import SkiState, SkiStateAdapter
from shared.connection.protocol import (
    AckMessage,
    Address,
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
    parse_server_message,
    to_bytes,
)
from shared.log import log

# Maps each game type to its column in the sequence score table.
_SEQUENCE_GAME_COLUMNS: dict[GameType, str] = {
    GameType.DINO_JUMP: "dino_jump",
    GameType.DINO: "dino",
    GameType.SKI: "ski",
    GameType.SKI_DYN: "ski_dyn",
}


class SpectatorClient:
    """Manages viewer registration, session subscription, heartbeats, and state deserialization."""

    _RETRY_SLEEP: timedelta = timedelta(seconds=0.1)

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        buffer_size: int = 65535,
        timeout: timedelta = timedelta(seconds=3),
        socket_timeout: timedelta = timedelta(seconds=0.5),
        heartbeat_interval: timedelta = timedelta(seconds=1),
        register_interval: timedelta = timedelta(seconds=1),
    ) -> None:
        self._buffer_size = buffer_size
        self._timeout = timeout
        self._heartbeat_interval = heartbeat_interval
        self._register_interval = register_interval

        self.sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(socket_timeout.total_seconds())

        self.latest_dino_state: GameState | None = None
        self.latest_pong_state: PongState | None = None
        self.latest_ski_state: SkiState | None = None
        self.intent_to_connect: bool = False
        self.connected: bool = False
        self.viewer_token: str = ""
        self.last_received_time: float = time.time()
        self.address: Address = (host, port)

        self.sessions: list[SessionInfo] = []
        self.spectating_uid: str | None = None
        self.spectating_game: GameType | None = None
        self.keep_watching: bool = True  # stay with this player past the score screen
        self.last_score: str = ""  # score from the most recently finished game
        self.last_username: str = ""  # player name from the most recently finished game
        self.quick_switch: bool = False  # arrow-key switching between connected BCI players
        self.admin_mode: bool = False  # admin spectator: shows sequence leaderboard overlay
        self.sequence_scores: dict[str, dict[str, str | float]] = {}  # uid -> per-game scores

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def connect(self) -> None:
        """Triggered by GUI to begin the registration loop."""
        self.connected = False
        self.viewer_token = ""
        self.sessions = []
        self.spectating_uid = None
        self.spectating_game = None
        self.intent_to_connect = True
        self.last_received_time = time.time()

    def disconnect(self) -> None:
        """Stop trying to connect and clear all session state."""
        self.intent_to_connect = False
        self.connected = False
        self.viewer_token = ""
        self.sessions = []
        self.spectating_uid = None
        self.spectating_game = None
        self.latest_dino_state = None
        self.latest_pong_state = None
        self.latest_ski_state = None
        self.keep_watching = True
        self.last_score = ""
        self.last_username = ""
        self.quick_switch = False
        self.sequence_scores = {}

    def send_command(self, cmd: str) -> None:
        """No-op stub kept for compatibility. Server ignores spectator CMDs."""
        del cmd

    def stop_watching(self) -> None:
        """Unsubscribe from the current player; clears server-side viewer.watching immediately."""
        if self.connected and self.viewer_token and self.spectating_uid:
            self.sock.sendto(
                to_bytes(SpectateMessage(viewer_token=self.viewer_token, target_uid="")),
                self.address,
            )
        self.spectating_uid = None
        self.spectating_game = None
        self.latest_dino_state = None
        self.latest_pong_state = None
        self.latest_ski_state = None

    def toggle_keep_watching(self) -> None:
        """Flip whether the viewer stays with the current player after their game ends."""
        self.keep_watching = not self.keep_watching

    def toggle_quick_switch(self) -> None:
        """Flip whether arrow-key switching between connected BCI players is enabled."""
        self.quick_switch = not self.quick_switch

    def switch_bci(self, direction: int) -> None:
        """Switch to the next (direction=1) or previous (direction=-1) connected BCI player."""
        bci_sessions = [s for s in self.sessions if s.bci_connected]
        if len(bci_sessions) < 2:
            return
        current_idx = next((i for i, s in enumerate(bci_sessions) if s.uid == self.spectating_uid), None)
        if current_idx is None:
            self.spectate(bci_sessions[0].uid)
            return
        new_idx = (current_idx + direction) % len(bci_sessions)
        self.spectate(bci_sessions[new_idx].uid)

    @property
    def spectating_display_name(self) -> str:
        """Display name of the currently spectated player, or empty string if unknown."""
        if not self.spectating_uid:
            return ""
        return next((s.display_name for s in self.sessions if s.uid == self.spectating_uid), "")

    def await_next_game(
        self, score: str = "", username: str = "", game: GameType | None = None, uid: str | None = None
    ) -> None:
        """Drop the finished game but stay subscribed, storing the score for the waiting screen."""
        self.last_score = score
        self.last_username = username
        if self.admin_mode and game is not None and uid is not None:
            self._record_sequence_score(uid, username, game, score)
        self.spectating_game = None
        self.latest_dino_state = None
        self.latest_pong_state = None
        self.latest_ski_state = None

    def _record_sequence_score(self, uid: str, name: str, game: GameType, score: str) -> None:
        """Accumulate per-player sequence scores for the admin leaderboard."""
        column = _SEQUENCE_GAME_COLUMNS.get(game)
        if column is None:
            return
        try:
            value = float(score)
        except ValueError:
            return
        entry = self.sequence_scores.setdefault(
            uid, {"name": name, "dino_jump": 0.0, "dino": 0.0, "ski": 0.0, "ski_dyn": 0.0, "total": 0.0}
        )
        entry["name"] = name
        entry[column] = value
        entry["total"] = (
            float(entry["dino_jump"]) + float(entry["dino"]) + float(entry["ski"]) + float(entry["ski_dyn"])
        )

    @property
    def sequence_leaderboard(self) -> list[dict[str, float | str]]:
        """Sequence scores sorted by total descending, only for connected BCI players."""
        connected_uids = {s.uid for s in self.sessions if s.bci_connected}
        entries = [dict(self.sequence_scores[uid]) for uid in self.sequence_scores if uid in connected_uids]
        entries.sort(key=lambda e: -e["total"])
        return entries

    def spectate(self, target_uid: str) -> None:
        """Subscribe to a player's state stream. Clears any previous state."""
        if not self.connected:
            return
        self.spectating_uid = target_uid
        self.spectating_game = None
        self.latest_dino_state = None
        self.latest_pong_state = None
        self.latest_ski_state = None
        msg = SpectateMessage(viewer_token=self.viewer_token, target_uid=target_uid)
        self.sock.sendto(to_bytes(msg), self.address)

    def update_server_address(self, ip: str, port: int) -> None:
        self.address = (ip, port)

    def _run(self) -> None:
        last_heartbeat: float = time.time()
        last_register: float = 0.0

        while True:
            now = time.time()

            if (
                self.intent_to_connect
                and not self.connected
                and now - last_register >= self._register_interval.total_seconds()
            ):
                self.sock.sendto(to_bytes(RegisterMessage(display_name="", device=DeviceType.SPECTATOR)), self.address)
                last_register = now

            try:
                data, _ = self.sock.recvfrom(self._buffer_size)
                msg = parse_server_message(data)
                self._handle_server_message(msg)
            except TimeoutError:
                pass
            except ValueError:
                log.debug("Dropped malformed server packet")
            except OSError:
                time.sleep(self._RETRY_SLEEP.total_seconds())
                continue

            now = time.time()

            if self.connected and now - self.last_received_time > self._timeout.total_seconds():
                log.warning("Server timed out - reconnecting")
                self.connected = False
                self.viewer_token = ""
                self.spectating_uid = None
                self.spectating_game = None

            if self.connected and now - last_heartbeat >= self._heartbeat_interval.total_seconds():
                ping = PingMessage(session_token=self.viewer_token, device=DeviceType.SPECTATOR)
                self.sock.sendto(to_bytes(ping), self.address)
                last_heartbeat = now

    def _handle_server_message(
        self, msg: AckMessage | ServerPingMessage | ServerPongMessage | StateMessage | SessionsMessage
    ) -> None:
        match msg:
            case AckMessage(session_token=token):
                self.viewer_token = token
                self.connected = True
                self.last_received_time = time.time()
                log.info("Viewer authenticated with token %s", token)

            case ServerPingMessage():
                self.last_received_time = time.time()
                pong = PongMessage(session_token=self.viewer_token, device=DeviceType.SPECTATOR)
                self.sock.sendto(to_bytes(pong), self.address)

            case ServerPongMessage():
                self.last_received_time = time.time()

            case SessionsMessage(sessions=sessions):
                self.last_received_time = time.time()
                self.sessions = sessions

            case StateMessage(content=content, game=game):
                self.last_received_time = time.time()
                self.spectating_game = game
                match game:
                    case GameType.DINO | GameType.DINO_JUMP:
                        self.latest_dino_state = GameStateAdapter.validate_bytes(content)
                    case GameType.PONG | GameType.PONG_AI:
                        self.latest_pong_state = PongStateAdapter.validate_bytes(content)
                    case GameType.SKI | GameType.SKI_DYN:
                        self.latest_ski_state = SkiStateAdapter.validate_bytes(content)


spectator_client = SpectatorClient()
