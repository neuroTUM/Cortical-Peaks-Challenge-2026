from games.dino.state import create_initial_state
from shared.connection.protocol import GameType, SessionInfo
from shared.connection.spectator_client import SpectatorClient


def test_toggle_keep_watching_flips() -> None:
    client = SpectatorClient()
    assert client.keep_watching is True
    client.toggle_keep_watching()
    assert client.keep_watching is False
    client.toggle_keep_watching()
    assert client.keep_watching is True


def test_await_next_game_clears_game_but_keeps_subscription() -> None:
    client = SpectatorClient()
    client.spectating_uid = "player-token"
    client.spectating_game = GameType.DINO
    client.latest_dino_state = create_initial_state("someone")

    client.await_next_game("42", "someone")

    assert client.spectating_uid == "player-token"  # still subscribed on the server
    assert client.spectating_game is None
    assert client.latest_dino_state is None
    assert client.last_score == "42"
    assert client.last_username == "someone"


def test_await_next_game_clears_ski_state() -> None:
    client = SpectatorClient()
    client.spectating_game = GameType.SKI
    client.latest_ski_state = None  # can't easily create one, just verify it's cleared

    client.await_next_game()

    assert client.spectating_game is None
    assert client.latest_ski_state is None


def test_disconnect_resets_keep_watching() -> None:
    client = SpectatorClient()
    client.toggle_keep_watching()
    assert client.keep_watching is False
    client.disconnect()
    assert client.keep_watching is True


def test_toggle_quick_switch_flips() -> None:
    client = SpectatorClient()
    assert client.quick_switch is False
    client.toggle_quick_switch()
    assert client.quick_switch is True
    client.toggle_quick_switch()
    assert client.quick_switch is False


def test_disconnect_resets_quick_switch() -> None:
    client = SpectatorClient()
    client.toggle_quick_switch()
    assert client.quick_switch is True
    client.disconnect()
    assert client.quick_switch is False


def test_spectating_display_name() -> None:
    client = SpectatorClient()
    client.sessions = [
        SessionInfo(uid="abc", display_name="alice", game="", bci_connected=True),
        SessionInfo(uid="def", display_name="bob", game="", bci_connected=True),
    ]

    assert client.spectating_display_name == ""

    client.spectating_uid = "abc"
    assert client.spectating_display_name == "alice"

    client.spectating_uid = "def"
    assert client.spectating_display_name == "bob"

    client.spectating_uid = "xyz"  # unknown uid
    assert client.spectating_display_name == ""


def test_switch_bci_cycles_through_connected_players() -> None:
    client = SpectatorClient()
    client.connected = True
    client.sessions = [
        SessionInfo(uid="a", display_name="alice", game="", bci_connected=True),
        SessionInfo(uid="b", display_name="bob", game="", bci_connected=True),
    ]

    client.spectating_uid = "a"
    client.switch_bci(1)
    assert client.spectating_uid == "b"

    client.switch_bci(1)  # wrap around
    assert client.spectating_uid == "a"

    client.switch_bci(-1)  # backward
    assert client.spectating_uid == "b"


def test_switch_bci_ignores_disconnected_players() -> None:
    client = SpectatorClient()
    client.connected = True
    client.sessions = [
        SessionInfo(uid="a", display_name="alice", game="", bci_connected=True),
        SessionInfo(uid="b", display_name="bob", game="", bci_connected=False),
    ]

    client.spectating_uid = "a"
    client.switch_bci(1)
    assert client.spectating_uid == "a"  # only one connected, stays the same


def test_switch_bci_noop_with_single_player() -> None:
    client = SpectatorClient()
    client.connected = True
    client.sessions = [SessionInfo(uid="a", display_name="alice", game="", bci_connected=True)]

    client.spectating_uid = "a"
    client.switch_bci(1)
    assert client.spectating_uid == "a"
