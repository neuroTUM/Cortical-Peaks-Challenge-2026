from __future__ import annotations

import random
import struct
from dataclasses import dataclass, field
from typing import Literal

from games.dino.config import dino_config
from shared.constants import FPS
from shared.ui import Grid

# Wire formats (network byte order).
# DinoState  : base_x base_y hitbox_x hitbox_y width height is_jumping is_ducking
#              duck_timer frame_count y_speed invuln_timer
_FMT_DINO_STATE = "!hhhhHHBBHHfH"  # 24 bytes
# ObstacleState: hitbox_x hitbox_y width height type frame_count
_FMT_OBSTACLE = "!hhHHBH"  # 11 bytes
# GameState fixed header: username time_left obstacle_count current_speed game_timer score
#   game_over countdown clouds_offset track_offset spawn_timer is_paused lives
_FMT_GAME_HEADER = "!16sfBHHHBfhhfBB"

_DINO_STATE_SIZE = struct.calcsize(_FMT_DINO_STATE)
_OBSTACLE_SIZE = struct.calcsize(_FMT_OBSTACLE)
_GAME_HEADER_SIZE = struct.calcsize(_FMT_GAME_HEADER)

ObstacleType = Literal["cactus", "bird"]

_OBS_TYPE_BYTE: dict[ObstacleType, int] = {"cactus": 0, "bird": 1}
_BYTE_OBS_TYPE: dict[int, ObstacleType] = {0: "cactus", 1: "bird"}


@dataclass
class DinoState:
    base_x: int
    base_y: int
    hitbox_x: int
    hitbox_y: int
    width: int
    height: int
    is_jumping: bool
    is_ducking: bool
    duck_timer: int
    frame_count: int
    y_speed: float = 0.0
    invuln_timer: int = 0


@dataclass
class ObstacleState:
    hitbox_x: int
    hitbox_y: int
    width: int
    height: int
    type: ObstacleType
    frame_count: int = 0


@dataclass
class GameState:
    username: str
    dino: DinoState
    time_left: float
    obstacles: list[ObstacleState]
    current_speed: int
    game_timer: int
    score: int = 0
    game_over: bool = False
    countdown: float = 0.0
    clouds_offset: int = 0
    track_offset: int = 0
    spawn_timer: float = 0
    is_paused: bool = False
    lives: int = 0
    # Server-side only (never serialised): the pre-generated obstacle sequence and how far into it
    # we have spawned. Built from a fixed seed so every run is identical for all competitors.
    obstacle_plan: list[ObstacleState] = field(default_factory=list)
    spawn_index: int = 0


class _GameStateAdapter:
    @staticmethod
    def dump_bytes(state: GameState) -> bytes:
        dino = state.dino
        dino_bytes = struct.pack(
            _FMT_DINO_STATE,
            dino.base_x,
            dino.base_y,
            dino.hitbox_x,
            dino.hitbox_y,
            dino.width,
            dino.height,
            int(dino.is_jumping),
            int(dino.is_ducking),
            dino.duck_timer,
            dino.frame_count,
            dino.y_speed,
            dino.invuln_timer,
        )
        obs_bytes = b"".join(
            struct.pack(
                _FMT_OBSTACLE,
                o.hitbox_x,
                o.hitbox_y,
                o.width,
                o.height,
                _OBS_TYPE_BYTE[o.type],
                o.frame_count,
            )
            for o in state.obstacles
        )
        header = struct.pack(
            _FMT_GAME_HEADER,
            state.username.encode("utf-8")[:16].ljust(16, b"\x00"),
            state.time_left,
            len(state.obstacles),
            state.current_speed,
            state.game_timer,
            state.score,
            int(state.game_over),
            state.countdown,
            state.clouds_offset,
            state.track_offset,
            state.spawn_timer,
            int(state.is_paused),
            state.lives,
        )
        return header + dino_bytes + obs_bytes

    @staticmethod
    def validate_bytes(data: bytes) -> GameState:
        (
            username_b,
            time_left,
            obstacle_count,
            current_speed,
            game_timer,
            score,
            game_over_b,
            countdown,
            clouds_offset,
            track_offset,
            spawn_timer,
            is_paused_b,
            lives,
        ) = struct.unpack_from(_FMT_GAME_HEADER, data, 0)

        dino_off = _GAME_HEADER_SIZE
        (
            base_x,
            base_y,
            hitbox_x,
            hitbox_y,
            width,
            height,
            is_jumping_b,
            is_ducking_b,
            duck_timer,
            frame_count,
            y_speed,
            invuln_timer,
        ) = struct.unpack_from(_FMT_DINO_STATE, data, dino_off)

        obstacles: list[ObstacleState] = []
        off = dino_off + _DINO_STATE_SIZE
        for _ in range(obstacle_count):
            hx, hy, w, h, type_b, fc = struct.unpack_from(_FMT_OBSTACLE, data, off)
            off += _OBSTACLE_SIZE
            obstacles.append(
                ObstacleState(
                    hitbox_x=hx,
                    hitbox_y=hy,
                    width=w,
                    height=h,
                    type=_BYTE_OBS_TYPE[type_b],
                    frame_count=fc,
                )
            )

        return GameState(
            username=username_b.rstrip(b"\x00").decode("utf-8"),
            dino=DinoState(
                base_x=base_x,
                base_y=base_y,
                hitbox_x=hitbox_x,
                hitbox_y=hitbox_y,
                width=width,
                height=height,
                is_jumping=bool(is_jumping_b),
                is_ducking=bool(is_ducking_b),
                duck_timer=duck_timer,
                frame_count=frame_count,
                y_speed=y_speed,
                invuln_timer=invuln_timer,
            ),
            time_left=time_left,
            obstacles=obstacles,
            current_speed=current_speed,
            game_timer=game_timer,
            score=score,
            game_over=bool(game_over_b),
            countdown=countdown,
            clouds_offset=clouds_offset,
            track_offset=track_offset,
            spawn_timer=spawn_timer,
            is_paused=bool(is_paused_b),
            lives=lives,
        )


GameStateAdapter = _GameStateAdapter()


_SPAWN_X = Grid.x(12) + Grid.x(2)  # just off the right edge; every obstacle enters here


def spawn_cactus(x: int) -> ObstacleState:
    """Build a ground-anchored cactus obstacle centered horizontally on x."""
    width = Grid.x(dino_config.cactus_width)
    height = Grid.y(dino_config.cactus_height)
    top_left_y = Grid.y(dino_config.ground_y) - height
    return ObstacleState(x - (width // 2), top_left_y, width, height, "cactus")


def spawn_bird(x: int, rng: random.Random) -> ObstacleState:
    """Build a bird obstacle at x, placed (via rng) to hit a standing dino but clear a ducking one."""
    width = Grid.x(dino_config.bird_width)
    height = Grid.y(dino_config.bird_height)
    half_h = height // 2
    ground = Grid.y(dino_config.ground_y)

    # bird_bottom > dino_standing_top  =>  center_y > ground - dino_height - half_h
    # bird_bottom <= dino_ducking_top  =>  center_y <= ground - dino_duck_height - half_h
    center_y_min = ground - Grid.y(dino_config.dino_height) - half_h + 1
    center_y_max = ground - Grid.y(dino_config.dino_duck_height) - half_h
    center_y = rng.randint(center_y_min, center_y_max)
    return ObstacleState(x - (width // 2), center_y - half_h, width, height, "bird")


def generate_obstacle_plan(*, jump_only: bool, seed: int) -> list[ObstacleState]:
    """Build the full, deterministic obstacle sequence for one run from a fixed seed.

    Jump & Duck runs get an equal number of jump (cactus) and duck (bird) obstacles in a
    seeded-random order; Jump Only runs are all cacti. Bird heights are also drawn from the seeded
    RNG, so a given seed yields a byte-identical run for every competitor. The spawn spacing
    (spawn_interval) comfortably exceeds the jump/duck recovery windows, so any order is clearable.
    """
    rng = random.Random(seed)
    count = dino_config.time_limit // dino_config.spawn_interval
    if jump_only:
        return [spawn_cactus(_SPAWN_X) for _ in range(count)]
    count -= count % 2  # keep jump/duck counts equal
    cactus: ObstacleType = "cactus"
    bird: ObstacleType = "bird"
    types = [cactus] * (count // 2) + [bird] * (count // 2)
    rng.shuffle(types)
    return [spawn_cactus(_SPAWN_X) if t == cactus else spawn_bird(_SPAWN_X, rng) for t in types]


def create_initial_state(username: str, *, jump_only: bool = False, seed: int | None = None) -> GameState:
    dino_start_x = Grid.x(2)
    dino_start_y = Grid.y(dino_config.ground_y)

    dino_w = Grid.x(dino_config.dino_width)
    dino_h = Grid.y(dino_config.dino_height)

    return GameState(
        username=username,
        score=0,
        lives=dino_config.lives,
        time_left=float(dino_config.time_limit) / FPS,
        clouds_offset=0,
        track_offset=0,
        dino=DinoState(
            base_x=dino_start_x,
            base_y=dino_start_y,
            hitbox_x=dino_start_x - (dino_w // 2),
            hitbox_y=dino_start_y - dino_h,
            width=dino_w,
            height=dino_h,
            is_jumping=False,
            is_ducking=False,
            duck_timer=0,
            frame_count=0,
            y_speed=0.0,
        ),
        obstacles=[],
        obstacle_plan=generate_obstacle_plan(
            jump_only=jump_only,
            seed=dino_config.obstacle_seed if seed is None else seed,
        ),
        current_speed=dino_config.game_speed,
        game_timer=0,
        spawn_timer=0,
        is_paused=True,
    )
