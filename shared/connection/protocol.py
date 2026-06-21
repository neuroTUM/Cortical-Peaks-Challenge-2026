from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum, StrEnum

TOKEN_SIZE = 8  # bytes on wire
UID_SIZE = 16  # bytes on wire
CMD_SIZE = 8  # bytes on wire


class MessageType(IntEnum):
    REGISTER = 1
    ACK = 2
    PING = 3
    PONG = 4
    CMD = 5
    SPECTATE = 6
    STATE = 7
    SESSIONS = 8


class DeviceType(IntEnum):
    BCI = 0
    SPECTATOR = 1


class GameType(StrEnum):
    DINO = "dino"
    PONG = "pong"
    PONG_AI = "pong_ai"
    DINO_JUMP = "dino_jump"


_GAME_BYTE: dict[GameType, int] = {
    GameType.DINO: 1,
    GameType.PONG: 2,
    GameType.PONG_AI: 3,
    GameType.DINO_JUMP: 4,
}
_BYTE_GAME: dict[int, GameType] = {
    1: GameType.DINO,
    2: GameType.PONG,
    3: GameType.PONG_AI,
    4: GameType.DINO_JUMP,
}

# Session game field: "" = no game, "dino" / "pong" / "pong_ai" / "dino_jump" as stored in SessionInfo.game
_SESSION_GAME_BYTE: dict[str, int] = {"": 0, "dino": 1, "pong": 2, "pong_ai": 3, "dino_jump": 4}
_BYTE_SESSION_GAME: dict[int, str] = {0: "", 1: "dino", 2: "pong", 3: "pong_ai", 4: "dino_jump"}

_FMT_SESSION_ENTRY = "!16s16sBB"  # uid + display_name + game_byte + bci_connected = 34 bytes
_SESSION_ENTRY_SIZE = struct.calcsize(_FMT_SESSION_ENTRY)


@dataclass
class RegisterMessage:
    display_name: str
    device: DeviceType


@dataclass
class PingMessage:
    """Client-initiated heartbeat; server responds with ServerPongMessage."""

    session_token: str
    device: DeviceType


@dataclass
class PongMessage:
    """Client response to a server-initiated ServerPingMessage."""

    session_token: str
    device: DeviceType


@dataclass
class CmdMessage:
    """Game command from BCI client to server."""

    session_token: str
    device: DeviceType
    content: str


@dataclass
class SpectateMessage:
    """Renderer viewer requests to watch a specific player by uid."""

    viewer_token: str
    target_uid: str


Address = tuple[str, int]

ClientMessage = RegisterMessage | PingMessage | PongMessage | CmdMessage | SpectateMessage


@dataclass
class AckMessage:
    """Successful registration response carrying this device's session token."""

    session_token: str


@dataclass
class ServerPingMessage:
    """Server-initiated heartbeat; client responds with PongMessage."""


@dataclass
class ServerPongMessage:
    """Server response to a client-initiated PingMessage."""


@dataclass
class StateMessage:
    """Game-state broadcast to renderer viewers."""

    content: bytes
    game: GameType


@dataclass
class SessionInfo:
    """Summary of a single player session, sent to renderer viewers."""

    uid: str
    display_name: str
    game: str  # GameType value or "" if not started
    bci_connected: bool


@dataclass
class SessionsMessage:
    """Full session list pushed to all viewers whenever it changes."""

    sessions: list[SessionInfo]


ServerMessage = AckMessage | ServerPingMessage | ServerPongMessage | StateMessage | SessionsMessage


def _enc_token(token: str) -> bytes:
    return bytes.fromhex(token)


def _enc_uid(uid: str) -> bytes:
    encoded = uid.encode("utf-8")
    if len(encoded) > UID_SIZE:
        encoded = encoded[:UID_SIZE]
        while encoded:
            try:
                encoded.decode("utf-8")
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
    return encoded.ljust(UID_SIZE, b"\x00")


def _enc_cmd(content: str) -> bytes:
    return content.encode("utf-8")[:CMD_SIZE].ljust(CMD_SIZE, b"\x00")


def to_bytes(msg: ClientMessage | ServerMessage) -> bytes:  # noqa: PLR0911
    """Serialize any protocol message to bytes."""
    match msg:
        case RegisterMessage(display_name=display_name, device=device):
            return struct.pack("!BB16s", MessageType.REGISTER, int(device), _enc_uid(display_name))
        case AckMessage(session_token=token):
            return struct.pack("!B8s", MessageType.ACK, _enc_token(token))
        case PingMessage(session_token=token, device=device):
            return struct.pack("!BB8s", MessageType.PING, int(device), _enc_token(token))
        case ServerPingMessage():
            return struct.pack("!B", MessageType.PING)
        case PongMessage(session_token=token, device=device):
            return struct.pack("!BB8s", MessageType.PONG, int(device), _enc_token(token))
        case ServerPongMessage():
            return struct.pack("!B", MessageType.PONG)
        case CmdMessage(session_token=token, device=device, content=content):
            return struct.pack("!BB8s8s", MessageType.CMD, int(device), _enc_token(token), _enc_cmd(content))
        case SpectateMessage(viewer_token=token, target_uid=uid):
            return struct.pack("!B8s16s", MessageType.SPECTATE, _enc_token(token), _enc_uid(uid))
        case StateMessage(content=content, game=game):
            return struct.pack("!BB", MessageType.STATE, _GAME_BYTE[game]) + content
        case SessionsMessage(sessions=sessions):
            buf = struct.pack("!BB", MessageType.SESSIONS, len(sessions))
            for s in sessions:
                buf += struct.pack(
                    _FMT_SESSION_ENTRY,
                    _enc_uid(s.uid),
                    _enc_uid(s.display_name),
                    _SESSION_GAME_BYTE.get(s.game, 0),
                    int(s.bci_connected),
                )
            return buf


def parse_client_message(data: bytes) -> ClientMessage | ServerPingMessage | ServerPongMessage:
    """
    Deserialize raw UDP bytes into a typed client message.

    Raises
    ------
    ValueError
        If the data is empty, the type byte is unknown, the frame is the
        wrong size, or a field value is out of range.

    """
    if not data:
        msg = "Empty datagram"
        raise ValueError(msg)
    if len(data) < 2:
        msg = "Frame too short"
        raise ValueError(msg)
    try:
        msg_type = MessageType(data[0])
        match msg_type:
            case MessageType.REGISTER:
                _, device, name_bytes = struct.unpack("!BB16s", data)
                return RegisterMessage(
                    display_name=name_bytes.rstrip(b"\x00").decode("utf-8"),
                    device=DeviceType(device),
                )
            case MessageType.PING:
                if len(data) != 10:
                    msg = f"PING frame must be 10 bytes, got {len(data)}"
                    raise ValueError(msg)
                _, device, token_bytes = struct.unpack("!BB8s", data)
                return PingMessage(
                    session_token=token_bytes.hex(),
                    device=DeviceType(device),
                )
            case MessageType.PONG:
                if len(data) != 10:
                    msg = f"PONG frame must be 10 bytes, got {len(data)}"
                    raise ValueError(msg)
                _, device, token_bytes = struct.unpack("!BB8s", data)
                return PongMessage(
                    session_token=token_bytes.hex(),
                    device=DeviceType(device),
                )
            case MessageType.CMD:
                _, device, token_bytes, content_bytes = struct.unpack("!BB8s8s", data)
                return CmdMessage(
                    session_token=token_bytes.hex(),
                    device=DeviceType(device),
                    content=content_bytes.rstrip(b"\x00").decode("utf-8"),
                )
            case MessageType.SPECTATE:
                _, token_bytes, uid_bytes = struct.unpack("!B8s16s", data)
                return SpectateMessage(
                    viewer_token=token_bytes.hex(),
                    target_uid=uid_bytes.rstrip(b"\x00").decode("utf-8"),
                )
            case _:
                msg = f"Unexpected client message type: {msg_type!r}"
                raise ValueError(msg)
    except (struct.error, UnicodeDecodeError, ValueError) as exc:
        msg = f"Malformed client message: {exc}"
        raise ValueError(msg) from exc


def parse_server_message(data: bytes) -> ServerMessage:
    """
    Deserialize raw UDP bytes into a typed server message.

    Raises
    ------
    ValueError
        If the data is empty, the type byte is unknown, the frame is the
        wrong size, or a field value is out of range.

    """
    if not data:
        msg = "Empty datagram"
        raise ValueError(msg)
    try:
        msg_type = MessageType(data[0])
        match msg_type:
            case MessageType.ACK:
                _, token_bytes = struct.unpack("!B8s", data)
                return AckMessage(session_token=token_bytes.hex())
            case MessageType.PING:
                return ServerPingMessage()
            case MessageType.PONG:
                return ServerPongMessage()
            case MessageType.STATE:
                _, game_byte = struct.unpack_from("!BB", data)
                game = _BYTE_GAME.get(game_byte)
                if game is None:
                    msg = f"Unknown game type byte: {game_byte}"
                    raise ValueError(msg)
                return StateMessage(content=data[2:], game=game)
            case MessageType.SESSIONS:
                _, count = struct.unpack_from("!BB", data)
                sessions: list[SessionInfo] = []
                offset = 2
                for _ in range(count):
                    uid_b, name_b, game_b, bci_b = struct.unpack_from(_FMT_SESSION_ENTRY, data, offset)
                    offset += _SESSION_ENTRY_SIZE
                    sessions.append(
                        SessionInfo(
                            uid=uid_b.rstrip(b"\x00").decode("utf-8"),
                            display_name=name_b.rstrip(b"\x00").decode("utf-8"),
                            game=_BYTE_SESSION_GAME.get(game_b, ""),
                            bci_connected=bool(bci_b),
                        )
                    )
                return SessionsMessage(sessions=sessions)
            case _:
                msg = f"Unexpected server message type: {msg_type!r}"
                raise ValueError(msg)
    except (struct.error, UnicodeDecodeError, ValueError) as exc:
        msg = f"Malformed server message: {exc}"
        raise ValueError(msg) from exc
