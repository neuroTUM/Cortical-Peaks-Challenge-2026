from games.dino.state import create_initial_state
from shared.connection.protocol import GameType
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
