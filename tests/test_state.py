from shared.state import Game, GameState, Scene


def test_go_to_pushes_history_and_maps_game() -> None:
    s = GameState()
    s.go_to(Scene.DINO_GAME)
    assert s.scene == Scene.DINO_GAME
    assert s.game == Game.DINO
    assert s.scene_stack == [Scene.LAUNCHER]


def test_go_back_pops_history() -> None:
    s = GameState()
    s.go_to(Scene.LEADERBOARD)
    s.go_to(Scene.CONNECTION)
    s.go_back()
    assert s.scene == Scene.LEADERBOARD
    assert s.scene_stack == [Scene.LAUNCHER]


def test_go_back_with_empty_stack_falls_back_to_launcher() -> None:
    s = GameState()
    s.scene = Scene.CONNECTION
    s.go_back()
    assert s.scene == Scene.LAUNCHER
    assert s.game == Game.ARCADE


def test_reset_to_clears_history() -> None:
    s = GameState()
    s.go_to(Scene.LEADERBOARD)
    s.go_to(Scene.CONNECTION)
    s.reset_to(Scene.SESSION_PICKER)
    assert s.scene == Scene.SESSION_PICKER
    assert s.scene_stack == []


def test_unmapped_scene_keeps_current_game() -> None:
    s = GameState()
    s.game = Game.PONG
    s.go_to(Scene.CONNECTION)  # CONNECTION is not in any game's scene list
    assert s.game == Game.PONG


def test_wheelchair_aliased_scene_maps_to_wheelchair_game() -> None:
    s = GameState()
    s.go_to(Scene.WHEELCHAIR_GAME_OVER)
    assert s.game == Game.WHEELCHAIR
