from __future__ import annotations

import logging
import socket
import sys
import threading
import time
from datetime import timedelta
from uuid import uuid4

import pygame

from shared.connection.protocol import (
    AckMessage,
    CmdMessage,
    DeviceType,
    PingMessage,
    PongMessage,
    RegisterMessage,
    ServerMessage,
    ServerPingMessage,
    ServerPongMessage,
    StateMessage,
    parse_server_message,
    to_bytes,
)

SERVER_ADDRESS: tuple[str, int] = ("127.0.0.1", 5000)
BCI_UID: str = "uid-" + str(uuid4())[:4]
BUFFER_SIZE: int = 65535
TIMEOUT: timedelta = timedelta(seconds=3)
SOCKET_TIMEOUT: timedelta = timedelta(seconds=2)

log = logging.getLogger(__name__)


class BCINetworkClient:
    def __init__(self) -> None:
        self.sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(SOCKET_TIMEOUT.total_seconds())

        self.connected: bool = False
        self.session_token: str = ""
        self.last_received_time: float = time.time()

        self._listener_thread = threading.Thread(target=self._network_listener, daemon=True)
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self._listener_thread.start()
        self._heartbeat_thread.start()

    def send_command(self, cmd: str) -> None:
        if self.connected:
            msg = CmdMessage(session_token=self.session_token, device=DeviceType.BCI, content=cmd)
            self.sock.sendto(to_bytes(msg), SERVER_ADDRESS)

    def _network_listener(self) -> None:
        while True:
            if not self.connected:
                reg = RegisterMessage(display_name=BCI_UID, device=DeviceType.BCI)
                self.sock.sendto(to_bytes(reg), SERVER_ADDRESS)
                time.sleep(1.0)

            try:
                data, _ = self.sock.recvfrom(BUFFER_SIZE)
                msg = parse_server_message(data)
                self._handle_server_message(msg)
            except TimeoutError:
                pass
            except ValueError:
                log.debug("Dropped malformed server packet")
            except OSError:
                time.sleep(0.1)

    def _handle_server_message(self, msg: ServerMessage) -> None:
        match msg:
            case AckMessage(session_token=token):
                self.session_token = token
                self.connected = True
                self.last_received_time = time.time()
                log.info("Authenticated with token %s", token)

            case ServerPingMessage():
                self.last_received_time = time.time()
                pong = PongMessage(session_token=self.session_token, device=DeviceType.BCI)
                self.sock.sendto(to_bytes(pong), SERVER_ADDRESS)

            case ServerPongMessage():
                self.last_received_time = time.time()

            case StateMessage():
                pass  # BCI clients do not get game state messages

    def _heartbeat_worker(self) -> None:
        while True:
            if self.connected:
                ping = PingMessage(session_token=self.session_token, device=DeviceType.BCI)
                self.sock.sendto(to_bytes(ping), SERVER_ADDRESS)

                if time.time() - self.last_received_time > TIMEOUT.total_seconds():
                    log.warning("Server timed out — reconnecting")
                    self.connected = False
                    self.session_token = ""

            time.sleep(1.0)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pygame.init()
    screen: pygame.Surface = pygame.display.set_mode((200, 200))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    bci = BCINetworkClient()

    running = True
    prev_cmd = ""
    while running:
        cmd: str | None = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    cmd = "INPUT_A"
                elif event.key == pygame.K_DOWN:
                    cmd = "INPUT_B"
                if cmd:
                    bci.send_command(cmd)
                    prev_cmd = cmd

        screen.fill((50, 0, 0) if not bci.connected else (0, 50, 0))
        status = "Connecting..." if not bci.connected else f"Connected: {prev_cmd}"
        screen.blit(font.render(status, True, (255, 255, 255)), (20, 90))
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
