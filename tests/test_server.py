import socket

from shared.connection.protocol import (
    AckMessage,
    DeviceType,
    PingMessage,
    RegisterMessage,
    ServerPongMessage,
    SessionsMessage,
    parse_server_message,
    to_bytes,
)


def _udp_sock() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    return sock


def test_bci_register_gets_ack(game_server: tuple) -> None:
    _server, port = game_server
    with _udp_sock() as sock:
        sock.sendto(
            to_bytes(RegisterMessage(display_name="smoketest", device=DeviceType.BCI)),
            ("127.0.0.1", port),
        )
        data, _ = sock.recvfrom(1024)
    msg = parse_server_message(data)
    assert isinstance(msg, AckMessage)
    assert len(msg.session_token) == 16


def test_spectator_ping_gets_pong(game_server: tuple) -> None:
    _server, port = game_server
    with _udp_sock() as sock:
        sock.sendto(
            to_bytes(RegisterMessage(display_name="viewer", device=DeviceType.SPECTATOR)),
            ("127.0.0.1", port),
        )
        data, _ = sock.recvfrom(1024)
        ack = parse_server_message(data)
        assert isinstance(ack, AckMessage)
        token = ack.session_token

        # The server also sends a SessionsMessage immediately after ACK; drain it.
        sock.settimeout(0.2)
        try:
            while True:
                extra, _ = sock.recvfrom(1024)
                if not isinstance(parse_server_message(extra), SessionsMessage):
                    break
        except TimeoutError:
            pass
        sock.settimeout(2.0)

        sock.sendto(
            to_bytes(PingMessage(session_token=token, device=DeviceType.SPECTATOR)),
            ("127.0.0.1", port),
        )
        data, _ = sock.recvfrom(1024)

    msg = parse_server_message(data)
    assert isinstance(msg, ServerPongMessage)
