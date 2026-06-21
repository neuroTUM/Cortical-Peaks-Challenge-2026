import pytest

from shared.connection.protocol import (
    AckMessage,
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
    parse_server_message,
    to_bytes,
)

_TOKEN = "deadbeef01234567"


def test_register_bci_roundtrip() -> None:
    msg = RegisterMessage(display_name="alice", device=DeviceType.BCI)
    assert parse_client_message(to_bytes(msg)) == msg


def test_register_spectator_roundtrip() -> None:
    msg = RegisterMessage(display_name="alice", device=DeviceType.SPECTATOR)
    assert parse_client_message(to_bytes(msg)) == msg


def test_ping_bci_roundtrip() -> None:
    msg = PingMessage(session_token=_TOKEN, device=DeviceType.BCI)
    assert parse_client_message(to_bytes(msg)) == msg


def test_ping_spectator_roundtrip() -> None:
    msg = PingMessage(session_token=_TOKEN, device=DeviceType.SPECTATOR)
    assert parse_client_message(to_bytes(msg)) == msg


def test_pong_bci_roundtrip() -> None:
    msg = PongMessage(session_token=_TOKEN, device=DeviceType.BCI)
    assert parse_client_message(to_bytes(msg)) == msg


def test_pong_spectator_roundtrip() -> None:
    msg = PongMessage(session_token=_TOKEN, device=DeviceType.SPECTATOR)
    assert parse_client_message(to_bytes(msg)) == msg


def test_cmd_roundtrip() -> None:
    msg = CmdMessage(session_token=_TOKEN, device=DeviceType.BCI, content="INPUT_A")
    assert parse_client_message(to_bytes(msg)) == msg


def test_spectate_roundtrip() -> None:
    msg = SpectateMessage(viewer_token=_TOKEN, target_uid="aabbccdd11223344")
    assert parse_client_message(to_bytes(msg)) == msg


def test_ack_roundtrip() -> None:
    msg = AckMessage(session_token=_TOKEN)
    assert parse_server_message(to_bytes(msg)) == msg


def test_server_ping_roundtrip() -> None:
    msg = ServerPingMessage()
    assert isinstance(parse_server_message(to_bytes(msg)), ServerPingMessage)


def test_server_pong_roundtrip() -> None:
    msg = ServerPongMessage()
    assert isinstance(parse_server_message(to_bytes(msg)), ServerPongMessage)


def test_state_message_dino_roundtrip() -> None:
    msg = StateMessage(content=b"\x01\x02\x03", game=GameType.DINO)
    result = parse_server_message(to_bytes(msg))
    assert isinstance(result, StateMessage)
    assert result.content == msg.content
    assert result.game == GameType.DINO


def test_state_message_pong_roundtrip() -> None:
    msg = StateMessage(content=b"\xab\xcd", game=GameType.PONG)
    result = parse_server_message(to_bytes(msg))
    assert isinstance(result, StateMessage)
    assert result.game == GameType.PONG
    assert result.content == msg.content


def test_state_message_pong_ai_roundtrip() -> None:
    msg = StateMessage(content=b"", game=GameType.PONG_AI)
    result = parse_server_message(to_bytes(msg))
    assert isinstance(result, StateMessage)
    assert result.game == GameType.PONG_AI
    assert result.content == msg.content


def test_sessions_message_empty_roundtrip() -> None:
    msg = SessionsMessage(sessions=[])
    result = parse_server_message(to_bytes(msg))
    assert isinstance(result, SessionsMessage)
    assert result.sessions == []


def test_sessions_message_multiple_roundtrip() -> None:
    sessions = [
        SessionInfo(uid="aabbccdd11223344", display_name="alice", game="dino", bci_connected=True),
        SessionInfo(uid="11223344aabbccdd", display_name="bob", game="", bci_connected=False),
    ]
    msg = SessionsMessage(sessions=sessions)
    result = parse_server_message(to_bytes(msg))
    assert isinstance(result, SessionsMessage)
    assert len(result.sessions) == 2
    assert result.sessions[0].display_name == "alice"
    assert result.sessions[0].game == "dino"
    assert result.sessions[0].bci_connected is True
    assert result.sessions[1].display_name == "bob"
    assert result.sessions[1].bci_connected is False


def test_sessions_message_round_trips_every_game_value() -> None:
    # Each GameType value (plus "" for no game) must survive the SESSIONS game-byte mapping, so the
    # session list shows the right game - including dino_jump.
    games = ["", *[g.value for g in GameType]]
    sessions = [
        SessionInfo(uid=f"{i:016x}", display_name=f"p{i}", game=game, bci_connected=True)
        for i, game in enumerate(games)
    ]
    result = parse_server_message(to_bytes(SessionsMessage(sessions=sessions)))
    assert isinstance(result, SessionsMessage)
    assert [s.game for s in result.sessions] == games


def test_sessions_message_multibyte_display_name_truncated_at_codepoint_boundary() -> None:
    # display_name "a"*14 + alpha + "x" encodes to 17 UTF-8 bytes; must round-trip as "a"*14 + alpha
    alpha = "α"  # noqa: RUF001 - Greek small letter alpha, two UTF-8 bytes: 0xCE 0xB1
    sessions = [SessionInfo(uid="aabbccdd11223344", display_name="a" * 14 + alpha + "x", game="", bci_connected=False)]
    msg = SessionsMessage(sessions=sessions)
    result = parse_server_message(to_bytes(msg))
    assert isinstance(result, SessionsMessage)
    assert result.sessions[0].display_name == "a" * 14 + alpha


def test_empty_bytes_raises() -> None:
    with pytest.raises(ValueError, match="Empty datagram"):
        parse_client_message(b"")


def test_one_byte_raises() -> None:
    with pytest.raises(ValueError, match="Frame too short"):
        parse_client_message(b"\x01")


def test_unknown_type_byte_raises() -> None:
    with pytest.raises(ValueError, match="Malformed"):
        parse_client_message(b"\xff\x00")


def test_ping_wrong_length_raises() -> None:
    # PING client frame must be exactly 10 bytes
    with pytest.raises(ValueError, match="10 bytes"):
        parse_client_message(b"\x03\x00\x00\x00")  # type=PING, too short


def test_pong_wrong_length_raises() -> None:
    with pytest.raises(ValueError, match="10 bytes"):
        parse_client_message(b"\x04\x00\x00\x00")  # type=PONG, too short


def test_display_name_exactly_16_ascii_roundtrips() -> None:
    name = "a" * 16
    msg = RegisterMessage(display_name=name, device=DeviceType.BCI)
    result = parse_client_message(to_bytes(msg))
    assert isinstance(result, RegisterMessage)
    assert result.display_name == name


def test_display_name_over_16_ascii_truncated() -> None:
    msg = RegisterMessage(display_name="x" * 30, device=DeviceType.BCI)
    result = parse_client_message(to_bytes(msg))
    assert isinstance(result, RegisterMessage)
    assert result.display_name == "x" * 16


def test_display_name_multibyte_truncated_at_codepoint_boundary() -> None:
    # "a" * 14 + alpha + "x" encodes to 17 UTF-8 bytes (alpha = 0xCE 0xB1, 2 bytes).
    # After truncating to 16 bytes the last complete codepoint is alpha, giving 16 bytes.
    alpha = "α"  # noqa: RUF001 - Greek small letter alpha, two UTF-8 bytes: 0xCE 0xB1
    long_name = "a" * 14 + alpha + "x"
    msg = RegisterMessage(display_name=long_name, device=DeviceType.BCI)
    result = parse_client_message(to_bytes(msg))
    assert isinstance(result, RegisterMessage)
    assert result.display_name == "a" * 14 + alpha


def test_cmd_content_over_8_bytes_truncated() -> None:
    msg = CmdMessage(session_token=_TOKEN, device=DeviceType.BCI, content="INPUT_ABCDEF")
    result = parse_client_message(to_bytes(msg))
    assert isinstance(result, CmdMessage)
    assert len(result.content) <= 8
