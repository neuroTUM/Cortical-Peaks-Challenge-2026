from enum import StrEnum


class Game(StrEnum):
    DINO = "dino"
    PONG = "pong"
    WHEELCHAIR = "wheelchair"
    ARCADE = "arcade"


class Scene(StrEnum):
    LAUNCHER = "launcher"
    DINO_GAME = "dino_game"
    PONG_GAME = "pong_game"
    WHEELCHAIR_INPUT_USERNAME = "wheelchair_input_username"
    WHEELCHAIR_GAME = "wheelchair_game"
    WHEELCHAIR_GAME_OVER = "wheelchair_game_over"
    LEADERBOARD = "leaderboard"
    CONNECTION = "connection"
    SPECTATOR_CONNECTION = "spectator_connection"
    SESSION_PICKER = "session_picker"
    QUIT = "quit"


# Single source of truth: (Game, [primary_scene, *aliased_scenes])
_GAME_SCENE_MAP: list[tuple[Game, list[Scene]]] = [
    (Game.DINO, [Scene.DINO_GAME]),
    (Game.PONG, [Scene.PONG_GAME]),
    (Game.WHEELCHAIR, [Scene.WHEELCHAIR_INPUT_USERNAME, Scene.WHEELCHAIR_GAME, Scene.WHEELCHAIR_GAME_OVER]),
    (Game.ARCADE, [Scene.LAUNCHER]),
]

_SCENE_TO_GAME: dict[Scene, Game] = {scene: game for game, scenes in _GAME_SCENE_MAP for scene in scenes}


class GameState:
    def __init__(self) -> None:
        self.scene = Scene.LAUNCHER
        self.scene_stack: list[Scene] = []
        self.game = Game.ARCADE

        self.username_one = ""
        self.username_two = ""
        self.score_one = 0
        self.score_two = 0
        self.winner = 0  # 0 = no winner, 1 = player one, 2 = player two

    def _get_game_from_scene(self, scene: Scene) -> Game:
        return _SCENE_TO_GAME.get(scene, self.game)

    def go_to(self, scene: Scene) -> None:
        self.scene_stack.append(self.scene)
        self.scene = scene
        self.game = self._get_game_from_scene(scene)

    def reset_to(self, scene: Scene) -> None:
        self.scene_stack.clear()
        self.scene = scene
        self.game = self._get_game_from_scene(scene)

    def go_back(self) -> None:
        if self.scene_stack:
            self.scene = self.scene_stack.pop()
            self.game = self._get_game_from_scene(self.scene)
        else:
            self.scene = Scene.LAUNCHER
            self.game = Game.ARCADE


state = GameState()
