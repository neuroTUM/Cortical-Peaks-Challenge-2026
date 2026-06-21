from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from shared.connection.server import GameServer

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def game_server() -> Generator[tuple[GameServer, int], Any]:
    GameServer.reset_for_testing()
    server = GameServer(
        host="127.0.0.1",
        port=0,
        timeout=timedelta(seconds=1),
        heartbeat_interval=timedelta(seconds=0.5),
    )
    server.start()
    port = server.server_sock.getsockname()[1]
    yield server, port
    server.stop()
    server.join()
    GameServer.reset_for_testing()
