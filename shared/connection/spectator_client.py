from __future__ import annotations

import socket
import threading
import time
from datetime import timedelta

from games.dino.state import GameState, GameStateAdapter
from games.pong.state import PongState, PongStateAdapter
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
        self.intent_to_connect: bool = False
        self.connected: bool = False
        self.viewer_token: str = ""
        self.last_received_time: float = time.time()
        self.address: Address = (host, port)

        self.sessions: list[SessionInfo] = []
        self.spectating_uid: str | None = None
        self.spectating_game: GameType | None = None
        self.keep_watching: bool = False  # stay with this player past the score screen

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
        self.keep_watching = False

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

    def toggle_keep_watching(self) -> None:
        """Flip whether the viewer stays with the current player after their game ends."""
        self.keep_watching = not self.keep_watching

    def await_next_game(self) -> None:
        """Drop the finished game but stay subscribed, so we wait for this player's next game."""
        self.spectating_game = None
        self.latest_dino_state = None
        self.latest_pong_state = None

    def spectate(self, target_uid: str) -> None:
        """Subscribe to a player's state stream. Clears any previous state."""
        if not self.connected:
            return
        self.spectating_uid = target_uid
        self.spectating_game = None
        self.latest_dino_state = None
        self.latest_pong_state = None
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


spectator_client = SpectatorClient()
