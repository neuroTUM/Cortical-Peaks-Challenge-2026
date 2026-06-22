from __future__ import annotations

import threading
from typing import Self

from shared.log import log


class Player:
    """Represents a single player entity."""

    def __init__(self, user_id: str, name: str) -> None:
        self.user_id = user_id
        self.name = name
        self.is_online = True


class PlayerManager:
    """Global Singleton that manages the roster of players. Handles: connection, reconnection and overview."""

    _instance: PlayerManager | None = None
    _class_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        if PlayerManager._instance is not None:
            err = "PlayerManager is a singleton. Use PlayerManager.instance() instead."
            raise RuntimeError(err)
        self._lock = threading.Lock()
        self.players: dict[str, Player] = {}

    @classmethod
    def instance(cls) -> Self:
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance  # type: ignore[return-value]

    def handle_connect(self, user_id: str, name: str, _renderer_id: str) -> None:
        """Logic: If user exists, wake them up. If not, create new."""
        with self._lock:
            if user_id in self.players:
                log.info("Reconnection: %s is back online.", name)
                self.players[user_id].is_online = True
                self.players[user_id].name = name
            else:
                log.info("New Player: %s (ID: %s)", name, user_id)
                self.players[user_id] = Player(user_id, name)

    def handle_disconnect(self, user_id: str) -> None:
        """Logic: Don't delete, just mark offline."""
        with self._lock:
            if user_id in self.players:
                log.info("%s went offline.", self.players[user_id].name)
                self.players[user_id].is_online = False

    def get_active_count(self) -> int:
        with self._lock:
            return sum(1 for p in self.players.values() if p.is_online)
